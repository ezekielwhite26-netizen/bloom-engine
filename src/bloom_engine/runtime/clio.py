from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from bloom_engine.runtime.models import ClioHandoff, ClioResult


class ClioTransactionStore(Protocol):
    def get(self, transaction_key: str) -> ClioResult | None: ...

    def put(self, transaction_key: str, result: ClioResult, handoff: ClioHandoff) -> None: ...

    def append_structured_event(self, handoff: ClioHandoff) -> str | None: ...

    def apply_deltas(self, handoff: ClioHandoff) -> tuple[str, ...]: ...

    def verify_readback(
        self,
        handoff: ClioHandoff,
        event_ids: tuple[str, ...],
        delta_keys: tuple[str, ...],
    ) -> bool: ...


@dataclass(slots=True)
class InMemoryClioTransactionStore:
    transactions: dict[str, ClioResult] = field(default_factory=dict)
    structured_events: dict[str, object] = field(default_factory=dict)
    _serial: int = 1

    def get(self, transaction_key: str) -> ClioResult | None:
        return self.transactions.get(transaction_key)

    def put(self, transaction_key: str, result: ClioResult, handoff: ClioHandoff) -> None:
        self.transactions[transaction_key] = result

    def append_structured_event(self, handoff: ClioHandoff) -> str | None:
        event = handoff.manifest.event
        if event is None:
            return None
        event_id = f"MEM-EVT-{self._serial:04d}"
        self._serial += 1
        self.structured_events[event_id] = event
        return event_id

    def apply_deltas(self, handoff: ClioHandoff) -> tuple[str, ...]:
        return tuple(delta.key for delta in handoff.manifest.deltas)

    def verify_readback(
        self,
        handoff: ClioHandoff,
        event_ids: tuple[str, ...],
        delta_keys: tuple[str, ...],
    ) -> bool:
        if handoff.manifest.event is not None:
            if len(event_ids) != 1 or event_ids[0] not in self.structured_events:
                return False
        expected_delta_keys = tuple(delta.key for delta in handoff.manifest.deltas)
        return delta_keys == expected_delta_keys


class GatedClio:
    """Capability-gated, idempotent CLIO port.

    This is the safe in-process transaction behavior ported from Runtime v0.3.1.
    It intentionally contains no production Airtable writer. A real store must
    separately certify stable-ID reservation, pre-state checking, owner-specific
    deltas, invalidation, and readback before it can replace the in-memory store.
    """

    def __init__(self, store: ClioTransactionStore):
        self.store = store

    def commit(self, handoff: ClioHandoff) -> ClioResult:
        prior = self.store.get(handoff.transaction_key)
        if prior is not None:
            return prior

        if not handoff.realized or not handoff.persistence_authorized:
            result = ClioResult(
                status="NO_OP",
                transaction_key=handoff.transaction_key,
                readback_verified=True,
                message="Candidate was preview-only or unrealized; CLIO made no durable change.",
            )
            self.store.put(handoff.transaction_key, result, handoff)
            return result

        if not handoff.authorization_token or not handoff.authorization_token.startswith("AMA-CAP::"):
            result = ClioResult(
                status="BLOCKED",
                transaction_key=handoff.transaction_key,
                readback_verified=False,
                message="Persistence requested without a valid Ama capability token.",
            )
            self.store.put(handoff.transaction_key, result, handoff)
            return result

        if (
            handoff.manifest.event is None
            and not handoff.manifest.deltas
            and not handoff.manifest.invalidations
        ):
            result = ClioResult(
                status="NO_OP",
                transaction_key=handoff.transaction_key,
                readback_verified=True,
                message="Authorized transaction contains no structured writes; CLIO made no durable change.",
            )
            self.store.put(handoff.transaction_key, result, handoff)
            return result

        event_ids: tuple[str, ...] = ()
        event_id = self.store.append_structured_event(handoff)
        if event_id:
            event_ids = (event_id,)

        delta_keys = self.store.apply_deltas(handoff)
        verified = self.store.verify_readback(handoff, event_ids, delta_keys)
        result = ClioResult(
            status="COMMITTED" if verified else "FAILED",
            transaction_key=handoff.transaction_key,
            committed_event_ids=event_ids,
            applied_delta_keys=delta_keys,
            readback_verified=verified,
            message=(
                "Authorized structured transaction committed exactly once and read back."
                if verified
                else "Transaction write could not be verified by readback."
            ),
        )
        self.store.put(handoff.transaction_key, result, handoff)
        return result
