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
class FakeAirtable:
    tables: dict[str, list[dict]] = field(default_factory=dict)
    updates: int = 0
    creates: int = 0

    def list_all(self, table_id: str):
        return self.tables.setdefault(table_id, [])

    def create(self, table_id: str, fields):
        self.creates += 1
        row = {"id": f"rec-{table_id}-{len(self.list_all(table_id))+1}", "fields": dict(fields)}
        self.list_all(table_id).append(row)
        return row

    def update(self, table_id: str, record_id: str, fields):
        self.updates += 1
        row = next(r for r in self.list_all(table_id) if r["id"] == record_id)
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
class SequentialEventIds:
    next_serial: int = 20
    reservations: int = 0

    def reserve_next(self) -> str:
        value = f"BLM-EVT-{self.next_serial:06d}"
        self.next_serial += 1
        self.reservations += 1
        return value


def make_store(*, fail_after_event_once=False):
    air = FakeAirtable()
    air.tables[CURRENT_SCENE_TABLE] = [
        {
            "id": "rec-scene",
            "fields": {
                CURRENT_SCENE_F["key"]: "SCENE-1218",
                CURRENT_SCENE_F["time"]: "12:18 PM",
                CURRENT_SCENE_F["location"]: "The Green",
                CURRENT_SCENE_F["present"]: "BLM-CHR-FLO; BLM-CHR-TEDDY",
                CURRENT_SCENE_F["last_beat"]: "old beat",
            },
        }
    ]
    air.tables[CONTEXT_PACKETS_TABLE] = [
        {
            "id": "rec-packet",
            "fields": {
                CONTEXT_PACKET_F["key"]: "PACKET-1218",
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
    ids = ExactIdentities({
        "Aster Hollow / At the Threshold",
        "BLM-LOC-000004",
        "BLM-CHR-FLO",
        "BLM-CHR-TEDDY",
    })
    allocator = SequentialEventIds()
    store = CanonicalAirtableStore(
        air,
        ids,
        allocator,
        registry,
        fail_after_event_once=fail_after_event_once,
    )
    return air, allocator, store


def handoff(*, location_ref="BLM-LOC-000004", packet="PACKET-1218"):
    projection = ProposedDelta(
        owner="CONNECTIVE",
        kind="CURRENT_SCENE_PROJECTION",
        key="SCENE::1218->1220",
        payload={
            "record_id": "rec-scene",
            "expected": {
                CURRENT_SCENE_F["key"]: "SCENE-1218",
                CURRENT_SCENE_F["time"]: "12:18 PM",
            },
            "desired": {
                CURRENT_SCENE_F["key"]: "SCENE-1220",
                CURRENT_SCENE_F["time"]: "12:20 PM",
                CURRENT_SCENE_F["location"]: "The Green",
                CURRENT_SCENE_F["present"]: "BLM-CHR-FLO; BLM-CHR-TEDDY",
                CURRENT_SCENE_F["last_beat"]: "Teddy finishes an ordinary remark.",
            },
        },
    )
    return ClioHandoff(
        transaction_key="TXN::E7::1220",
        packet_key=packet,
        arc="Aster Hollow / At the Threshold",
        source_run="RUN::E7::1220",
        expected_pre_state_digest="scene=1218",
        manifest=ClioManifest(
            event=ClioEvent(
                event_key="ASTER-S1E7-GREEN-1220-FIXTURE",
                arc="Aster Hollow / At the Threshold",
                in_world_time="Monday, 7 September 2009 — 12:20 PM",
                location_ref=location_ref,
                location_name="The Green",
                event_type="ordinary life",
                summary="Teddy finishes an ordinary remark while the group remains on The Green.",
                participant_refs=("BLM-CHR-FLO", "BLM-CHR-TEDDY"),
                source_provenance=("noncanon persistence fixture",),
            ),
            deltas=(projection,),
            invalidations=(packet,),
            readback_assertions=("Event exists", "Current Scene refreshed", "packet stale"),
        ),
        realized=True,
        persistence_authorized=True,
        authorization_token="AMA-CAP::fixture",
    )


def test_event_projection_and_packet_invalidation_commit_exactly_once():
    air, allocator, store = make_store()
    clio = GatedClio(store)
    first = clio.commit(handoff())
    second = clio.commit(handoff())
    assert first.status == "COMMITTED"
    assert second == first
    assert first.committed_event_ids == ("BLM-EVT-000020",)
    assert len(air.list_all(EVENTS_TABLE)) == 1
    assert allocator.reservations == 1
    assert air.list_all(CURRENT_SCENE_TABLE)[0]["fields"][CURRENT_SCENE_F["key"]] == "SCENE-1220"
    assert air.list_all(CONTEXT_PACKETS_TABLE)[0]["fields"][CONTEXT_PACKET_F["status"]] == "Stale"


def test_missing_exact_identity_blocks_before_event_and_allocator_use():
    air, allocator, store = make_store()
    result = GatedClio(store).commit(handoff(location_ref="BLM-LOC-NOT-REAL"))
    assert result.status == "FAILED"
    assert not air.list_all(EVENTS_TABLE)
    assert allocator.reservations == 0


def test_unregistered_sovereign_delta_fails_closed_before_event():
    air, allocator, store = make_store()
    h = handoff()
    bad = ProposedDelta(owner="HEPHAESTUS", kind="OBJECT_PATCH", key="OBJ", payload={})
    h = ClioHandoff(
        transaction_key=h.transaction_key,
        packet_key=h.packet_key,
        arc=h.arc,
        source_run=h.source_run,
        expected_pre_state_digest=h.expected_pre_state_digest,
        manifest=ClioManifest(event=h.manifest.event, deltas=(bad,), invalidations=h.manifest.invalidations),
        realized=True,
        persistence_authorized=True,
        authorization_token=h.authorization_token,
    )
    result = GatedClio(store).commit(h)
    assert result.status == "FAILED"
    assert not air.list_all(EVENTS_TABLE)
    assert allocator.reservations == 0


def test_stale_current_scene_prestate_blocks_before_event():
    air, allocator, store = make_store()
    air.list_all(CURRENT_SCENE_TABLE)[0]["fields"][CURRENT_SCENE_F["key"]] = "SCENE-NEWER"
    result = GatedClio(store).commit(handoff())
    assert result.status == "FAILED"
    assert not air.list_all(EVENTS_TABLE)
    assert allocator.reservations == 0
    assert air.list_all(CURRENT_SCENE_TABLE)[0]["fields"][CURRENT_SCENE_F["key"]] == "SCENE-NEWER"


def test_missing_packet_invalidation_blocks_before_event():
    air, allocator, store = make_store()
    result = GatedClio(store).commit(handoff(packet="MISSING-PACKET"))
    assert result.status == "FAILED"
    assert not air.list_all(EVENTS_TABLE)
    assert allocator.reservations == 0


def test_crash_after_event_retry_finishes_without_duplicate_event():
    air, allocator, store = make_store(fail_after_event_once=True)
    clio = GatedClio(store)
    first = clio.commit(handoff())
    assert first.status == "FAILED"
    assert first.committed_event_ids == ("BLM-EVT-000020",)
    assert len(air.list_all(EVENTS_TABLE)) == 1
    second = clio.commit(handoff())
    assert second.status == "COMMITTED"
    assert second.committed_event_ids == ("BLM-EVT-000020",)
    assert len(air.list_all(EVENTS_TABLE)) == 1
    assert allocator.reservations == 1
    assert air.list_all(CURRENT_SCENE_TABLE)[0]["fields"][CURRENT_SCENE_F["key"]] == "SCENE-1220"
    assert air.list_all(CONTEXT_PACKETS_TABLE)[0]["fields"][CONTEXT_PACKET_F["status"]] == "Stale"
