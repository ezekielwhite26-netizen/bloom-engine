from __future__ import annotations

from dataclasses import dataclass, field

from bloom_engine.runtime.clio import GatedClio
from bloom_engine.runtime.models import ClioEvent, ClioHandoff, ClioManifest, ProposedDelta
from bloom_engine.runtime.persistence import (
    CONTEXT_PACKET_F,
    CONTEXT_PACKETS_TABLE,
    CURRENT_SCENE_F,
    CURRENT_SCENE_TABLE,
    EVENT_F,
    EVENTS_TABLE,
    CanonicalAirtableStore,
    DeltaRegistry,
    ExactRecordPatchHandler,
)


@dataclass
class FaultOnceAirtable:
    tables: dict[str, list[dict]] = field(default_factory=dict)
    fail_list_once_for: set[str] = field(default_factory=set)
    fail_update_once_for: set[str] = field(default_factory=set)
    list_failures: set[str] = field(default_factory=set)
    update_failures: set[str] = field(default_factory=set)
    creates: int = 0
    updates: int = 0

    def list_all(self, table_id: str):
        if table_id in self.fail_list_once_for and table_id not in self.list_failures:
            self.list_failures.add(table_id)
            raise RuntimeError(f"fixture list failure for {table_id}")
        return self.tables.setdefault(table_id, [])

    def create(self, table_id: str, fields):
        self.creates += 1
        row = {
            "id": f"rec-{table_id}-{len(self.tables.setdefault(table_id, [])) + 1}",
            "fields": dict(fields),
        }
        self.tables[table_id].append(row)
        return row

    def update(self, table_id: str, record_id: str, fields):
        if table_id in self.fail_update_once_for and table_id not in self.update_failures:
            self.update_failures.add(table_id)
            raise RuntimeError(f"fixture update failure for {table_id}")
        self.updates += 1
        row = next(r for r in self.tables.setdefault(table_id, []) if r["id"] == record_id)
        row["fields"].update(dict(fields))
        return row


@dataclass
class ExactIdentities:
    allowed: set[str]

    def resolve_exact(self, stable_id: str) -> str:
        if stable_id not in self.allowed:
            raise ValueError(f"unresolved exact identity: {stable_id}")
        return stable_id


@dataclass
class FixtureEventIds:
    next_serial: int = 900001
    reservations: int = 0

    def reserve_next(self) -> str:
        value = f"FIX-EVT-{self.next_serial:06d}"
        self.next_serial += 1
        self.reservations += 1
        return value


def make_store(
    *,
    fail_list_once_for: set[str] | None = None,
    fail_update_once_for: set[str] | None = None,
):
    air = FaultOnceAirtable(
        fail_list_once_for=set(fail_list_once_for or ()),
        fail_update_once_for=set(fail_update_once_for or ()),
    )
    air.tables[CURRENT_SCENE_TABLE] = [
        {
            "id": "rec-scene",
            "fields": {
                CURRENT_SCENE_F["key"]: "SCENE-FIXTURE-OLD",
                CURRENT_SCENE_F["time"]: "1:00 PM",
                CURRENT_SCENE_F["location"]: "Fixture Green",
                CURRENT_SCENE_F["present"]: "BLM-CHR-FLO",
                CURRENT_SCENE_F["last_beat"]: "fixture old beat",
            },
        }
    ]
    air.tables[CONTEXT_PACKETS_TABLE] = [
        {
            "id": "rec-packet",
            "fields": {
                CONTEXT_PACKET_F["key"]: "PACKET-FIXTURE",
                CONTEXT_PACKET_F["status"]: "In Use",
                CONTEXT_PACKET_F["notes"]: "",
            },
        }
    ]
    registry = DeltaRegistry()
    registry.register(
        "CONNECTIVE",
        "CURRENT_SCENE_PROJECTION",
        ExactRecordPatchHandler(
            air,
            CURRENT_SCENE_TABLE,
            frozenset(CURRENT_SCENE_F.values()),
        ),
    )
    allocator = FixtureEventIds()
    store = CanonicalAirtableStore(
        air,
        ExactIdentities({
            "Aster Hollow / Fixture Arc",
            "BLM-LOC-FIXTURE",
            "BLM-CHR-FLO",
        }),
        allocator,
        registry,
    )
    return air, allocator, store


def handoff() -> ClioHandoff:
    projection = ProposedDelta(
        owner="CONNECTIVE",
        kind="CURRENT_SCENE_PROJECTION",
        key="FIXTURE::SCENE-PROJECTION",
        payload={
            "record_id": "rec-scene",
            "expected": {
                CURRENT_SCENE_F["key"]: "SCENE-FIXTURE-OLD",
                CURRENT_SCENE_F["time"]: "1:00 PM",
            },
            "desired": {
                CURRENT_SCENE_F["key"]: "SCENE-FIXTURE-NEW",
                CURRENT_SCENE_F["time"]: "1:02 PM",
                CURRENT_SCENE_F["location"]: "Fixture Green",
                CURRENT_SCENE_F["present"]: "BLM-CHR-FLO",
                CURRENT_SCENE_F["last_beat"]: "fixture new beat",
            },
        },
    )
    return ClioHandoff(
        transaction_key="TXN::FIXTURE::RECOVERY",
        packet_key="PACKET-FIXTURE",
        arc="Aster Hollow / Fixture Arc",
        source_run="RUN::FIXTURE::RECOVERY",
        expected_pre_state_digest="fixture-old",
        manifest=ClioManifest(
            event=ClioEvent(
                event_key="FIXTURE-RECOVERY-EVENT",
                arc="Aster Hollow / Fixture Arc",
                in_world_time="Fixture time",
                location_ref="BLM-LOC-FIXTURE",
                location_name="Fixture Green",
                event_type="fixture",
                summary="Non-canon recovery fixture.",
                participant_refs=("BLM-CHR-FLO",),
                source_provenance=("mock-only transport recovery fixture",),
            ),
            deltas=(projection,),
            invalidations=("PACKET-FIXTURE",),
        ),
        realized=True,
        persistence_authorized=True,
        authorization_token="AMA-CAP::fixture-only",
    )


def test_transient_preflight_read_failure_retries_without_event_or_id_loss():
    air, allocator, store = make_store(fail_list_once_for={CURRENT_SCENE_TABLE})
    clio = GatedClio(store)

    first = clio.commit(handoff())
    assert first.status == "FAILED"
    assert allocator.reservations == 0
    assert air.tables.get(EVENTS_TABLE, []) == []

    second = clio.commit(handoff())
    assert second.status == "COMMITTED"
    assert allocator.reservations == 1
    assert len(air.tables[EVENTS_TABLE]) == 1


def test_transient_scene_update_failure_reuses_existing_event_on_retry():
    air, allocator, store = make_store(fail_update_once_for={CURRENT_SCENE_TABLE})
    clio = GatedClio(store)

    first = clio.commit(handoff())
    assert first.status == "FAILED"
    assert len(air.tables[EVENTS_TABLE]) == 1
    persisted_id = air.tables[EVENTS_TABLE][0]["fields"][EVENT_F["stable_id"]]
    assert first.committed_event_ids == (persisted_id,)
    assert allocator.reservations == 1

    second = clio.commit(handoff())
    assert second.status == "COMMITTED"
    assert second.committed_event_ids == (persisted_id,)
    assert allocator.reservations == 1
    assert len(air.tables[EVENTS_TABLE]) == 1
    assert air.tables[CURRENT_SCENE_TABLE][0]["fields"][CURRENT_SCENE_F["key"]] == "SCENE-FIXTURE-NEW"


def test_transient_packet_invalidation_failure_recovers_from_partial_delta_state():
    air, allocator, store = make_store(fail_update_once_for={CONTEXT_PACKETS_TABLE})
    clio = GatedClio(store)

    first = clio.commit(handoff())
    assert first.status == "FAILED"
    assert allocator.reservations == 1
    assert len(air.tables[EVENTS_TABLE]) == 1
    assert air.tables[CURRENT_SCENE_TABLE][0]["fields"][CURRENT_SCENE_F["key"]] == "SCENE-FIXTURE-NEW"
    assert air.tables[CONTEXT_PACKETS_TABLE][0]["fields"][CONTEXT_PACKET_F["status"]] == "In Use"

    second = clio.commit(handoff())
    assert second.status == "COMMITTED"
    assert allocator.reservations == 1
    assert len(air.tables[EVENTS_TABLE]) == 1
    assert air.tables[CONTEXT_PACKETS_TABLE][0]["fields"][CONTEXT_PACKET_F["status"]] == "Stale"
