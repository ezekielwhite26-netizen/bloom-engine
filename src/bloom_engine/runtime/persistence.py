from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

from bloom_engine.runtime.models import ClioHandoff, ClioResult, ProposedDelta


EVENTS_TABLE = "tblXERwP6Fuc2ofox"
CURRENT_SCENE_TABLE = "tblipTnwAEA05zs9v"
CONTEXT_PACKETS_TABLE = "tblXISSlaPbjJCSti"

EVENT_F = {
    "stable_id": "fldEKj1Iih2AE7HhM",
    "event_key": "fldb82ATprvlOcqLU",
    "arc": "fldG8YWqMLpL7mBne",
    "time": "fldV0jmCDfS8d6CtR",
    "location": "fld0ru1KCfd8L7ojt",
    "type": "fldlyUAED5NiOqNx1",
    "summary": "fld9qYxHlJoDbyyFm",
    "participants": "flddRWhenNTIlrUV2",
    "consequences": "fldBAuNTjm91KZTcf",
    "provenance": "fldJXxcM4QNOmeLRK",
}
CURRENT_SCENE_F = {
    "key": "fldPweqNPJwM8e5FC",
    "time": "fldyHoqnqks2VaoDg",
    "location": "fld1msBDbtVudey4P",
    "present": "fld5VWkQcajUDmDVh",
    "last_beat": "fldO8KBpPV8DT1m4m",
}
CONTEXT_PACKET_F = {
    "key": "fldQswxWbYRJbn7GB",
    "status": "fldzRlmHGmXO4hV2c",
    "notes": "fldcvFPKGPRhJh676",
}


class AirtableTransport(Protocol):
    def list_all(self, table_id: str) -> list[dict[str, Any]]: ...
    def create(self, table_id: str, fields: Mapping[str, Any]) -> dict[str, Any]: ...
    def update(self, table_id: str, record_id: str, fields: Mapping[str, Any]) -> dict[str, Any]: ...


class StableIdentityResolver(Protocol):
    def resolve_exact(self, stable_id: str) -> str: ...


class EventIdAllocator(Protocol):
    def reserve_next(self) -> str: ...


class DeltaHandler(Protocol):
    def preflight(self, delta: ProposedDelta) -> None: ...
    def apply(self, delta: ProposedDelta) -> str: ...
    def verify(self, delta: ProposedDelta) -> bool: ...


@dataclass(slots=True)
class DeltaRegistry:
    handlers: dict[tuple[str, str], DeltaHandler] = field(default_factory=dict)

    def register(self, owner: str, kind: str, handler: DeltaHandler) -> None:
        self.handlers[(owner, kind)] = handler

    def handler_for(self, delta: ProposedDelta) -> DeltaHandler:
        handler = self.handlers.get((delta.owner, delta.kind))
        if handler is None:
            raise ValueError(f"No sovereign delta handler registered for {delta.owner}/{delta.kind}.")
        return handler


@dataclass(slots=True)
class ExactRecordPatchHandler:
    transport: AirtableTransport
    table_id: str
    allowed_fields: frozenset[str]

    def _payload(self, delta: ProposedDelta) -> tuple[str, Mapping[str, Any], Mapping[str, Any]]:
        record_id = str(delta.payload.get("record_id", ""))
        expected = delta.payload.get("expected", {})
        desired = delta.payload.get("desired", {})
        if not record_id or not isinstance(expected, Mapping) or not isinstance(desired, Mapping):
            raise ValueError("Exact patch requires record_id, expected, and desired mappings.")
        if not set(desired).issubset(self.allowed_fields):
            raise ValueError("Delta attempted to write a field outside its registered sovereign allowance.")
        return record_id, expected, desired

    def _record(self, record_id: str) -> dict[str, Any]:
        matches = [r for r in self.transport.list_all(self.table_id) if r.get("id") == record_id]
        if len(matches) != 1:
            raise ValueError("Exact target record did not resolve uniquely.")
        return matches[0]

    def preflight(self, delta: ProposedDelta) -> None:
        record_id, expected, desired = self._payload(delta)
        fields = self._record(record_id).get("fields", {})
        if all(fields.get(k) == v for k, v in desired.items()):
            return
        if not all(fields.get(k) == v for k, v in expected.items()):
            raise ValueError("Expected pre-state mismatch; refusing stale overwrite.")

    def apply(self, delta: ProposedDelta) -> str:
        record_id, _expected, desired = self._payload(delta)
        fields = self._record(record_id).get("fields", {})
        if not all(fields.get(k) == v for k, v in desired.items()):
            self.transport.update(self.table_id, record_id, desired)
        return delta.key

    def verify(self, delta: ProposedDelta) -> bool:
        record_id, _expected, desired = self._payload(delta)
        fields = self._record(record_id).get("fields", {})
        return all(fields.get(k) == v for k, v in desired.items())


@dataclass(slots=True)
class CanonicalAirtableStore:
    """CLIO canonical operations over a zero-semantics Airtable transport.

    Exact entity resolution and EVT allocation are injected so this store cannot
    invent identity. Current Scene is maintained only through a CONNECTIVE
    projection delta; Context Packets are invalidated by exact packet key.
    """

    transport: AirtableTransport
    identities: StableIdentityResolver
    event_ids: EventIdAllocator
    deltas: DeltaRegistry
    transactions: dict[str, ClioResult] = field(default_factory=dict)
    fail_after_event_once: bool = False
    _failed_once: bool = False

    def get(self, transaction_key: str) -> ClioResult | None:
        return self.transactions.get(transaction_key)

    def put(self, transaction_key: str, result: ClioResult, handoff: ClioHandoff) -> None:
        self.transactions[transaction_key] = result

    def checkpoint(
        self,
        handoff: ClioHandoff,
        *,
        status: str,
        event_ids: tuple[str, ...] = (),
        delta_keys: tuple[str, ...] = (),
        message: str = "",
    ) -> None:
        self.transactions[handoff.transaction_key] = ClioResult(
            status=status,
            transaction_key=handoff.transaction_key,
            committed_event_ids=event_ids,
            applied_delta_keys=delta_keys,
            readback_verified=False,
            message=message,
        )

    def _event_by_key(self, event_key: str) -> dict[str, Any] | None:
        matches = [
            r for r in self.transport.list_all(EVENTS_TABLE)
            if r.get("fields", {}).get(EVENT_F["event_key"]) == event_key
        ]
        if len(matches) > 1:
            raise ValueError("Event Key resolved to multiple canonical Events.")
        return matches[0] if matches else None

    def _packet(self, packet_key: str) -> dict[str, Any]:
        matches = [
            r for r in self.transport.list_all(CONTEXT_PACKETS_TABLE)
            if r.get("fields", {}).get(CONTEXT_PACKET_F["key"]) == packet_key
        ]
        if len(matches) != 1:
            raise ValueError(f"Context Packet {packet_key} did not resolve exactly once.")
        return matches[0]

    def preflight(self, handoff: ClioHandoff) -> None:
        event = handoff.manifest.event
        if event is not None:
            self.identities.resolve_exact(event.arc)
            self.identities.resolve_exact(event.location_ref)
            for participant in event.participant_refs:
                self.identities.resolve_exact(participant)
        for delta in handoff.manifest.deltas:
            self.deltas.handler_for(delta).preflight(delta)
        for packet_key in handoff.manifest.invalidations:
            self._packet(packet_key)

    def append_structured_event(self, handoff: ClioHandoff) -> str | None:
        event = handoff.manifest.event
        if event is None:
            return None
        existing = self._event_by_key(event.event_key)
        if existing is not None:
            return str(existing.get("fields", {}).get(EVENT_F["stable_id"], ""))
        stable_event_id = self.event_ids.reserve_next()
        fields = {
            EVENT_F["stable_id"]: stable_event_id,
            EVENT_F["event_key"]: event.event_key,
            EVENT_F["arc"]: event.arc,
            EVENT_F["time"]: event.in_world_time,
            EVENT_F["location"]: event.location_name,
            EVENT_F["type"]: event.event_type,
            EVENT_F["summary"]: event.summary,
            EVENT_F["participants"]: "; ".join(event.participant_refs),
            EVENT_F["consequences"]: "; ".join(event.consequences),
            EVENT_F["provenance"]: "; ".join(event.source_provenance),
        }
        self.transport.create(EVENTS_TABLE, fields)
        return stable_event_id

    def apply_deltas(self, handoff: ClioHandoff) -> tuple[str, ...]:
        if self.fail_after_event_once and not self._failed_once:
            self._failed_once = True
            raise RuntimeError("injected crash after Event append")
        applied: list[str] = []
        for delta in handoff.manifest.deltas:
            handler = self.deltas.handler_for(delta)
            applied.append(handler.apply(delta))
        for packet_key in handoff.manifest.invalidations:
            packet = self._packet(packet_key)
            fields = packet.get("fields", {})
            if fields.get(CONTEXT_PACKET_F["status"]) != "Stale":
                self.transport.update(
                    CONTEXT_PACKETS_TABLE,
                    str(packet["id"]),
                    {
                        CONTEXT_PACKET_F["status"]: "Stale",
                        CONTEXT_PACKET_F["notes"]: f"Invalidated by CLIO transaction {handoff.transaction_key}.",
                    },
                )
            applied.append(f"CTX_INVALIDATE::{packet_key}")
        return tuple(applied)

    def verify_readback(
        self,
        handoff: ClioHandoff,
        event_ids: tuple[str, ...],
        delta_keys: tuple[str, ...],
    ) -> bool:
        event = handoff.manifest.event
        if event is not None:
            existing = self._event_by_key(event.event_key)
            if existing is None or not event_ids:
                return False
            if existing.get("fields", {}).get(EVENT_F["stable_id"]) != event_ids[0]:
                return False
        for delta in handoff.manifest.deltas:
            if not self.deltas.handler_for(delta).verify(delta):
                return False
        for packet_key in handoff.manifest.invalidations:
            packet = self._packet(packet_key)
            if packet.get("fields", {}).get(CONTEXT_PACKET_F["status"]) != "Stale":
                return False
        expected = len(handoff.manifest.deltas) + len(handoff.manifest.invalidations)
        return len(delta_keys) == expected
