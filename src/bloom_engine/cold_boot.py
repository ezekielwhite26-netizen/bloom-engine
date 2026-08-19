from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class BackfillState(str, Enum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class ThreadState:
    key: str
    status: str
    attention: int = 0
    matured_trigger: bool = False


@dataclass(frozen=True, slots=True)
class TemporalFact:
    key: str
    valid_from_year: int
    value: Any


@dataclass(frozen=True, slots=True)
class ColdBootSnapshot:
    threads: Sequence[ThreadState] = field(default_factory=tuple)
    obligations: Mapping[str, Any] = field(default_factory=dict)
    possessions: Mapping[str, Any] = field(default_factory=dict)
    subsystem_rows: Mapping[str, Sequence[Mapping[str, Any]]] = field(default_factory=dict)
    temporal_facts: Sequence[TemporalFact] = field(default_factory=tuple)


def opening_thread_candidates(snapshot: ColdBootSnapshot) -> tuple[str, ...]:
    """Return only threads with a matured causal trigger.

    Attention and mere unresolved/dormant existence never make a thread eligible.
    """
    return tuple(
        thread.key
        for thread in snapshot.threads
        if thread.matured_trigger and thread.status.upper() not in {"DORMANT", "BACKGROUND"}
    )


def compile_minimal_packet(
    records_by_id: Mapping[str, Mapping[str, Any]],
    relevant_ids: Sequence[str],
) -> dict[str, Mapping[str, Any]]:
    """Compile only explicitly relevant records; missing records remain absent/unknown."""
    return {record_id: records_by_id[record_id] for record_id in relevant_ids if record_id in records_by_id}


def reconstruct_mutable_state(snapshot: ColdBootSnapshot) -> dict[str, dict[str, Any]]:
    """Preserve obligations and possession state exactly as stored."""
    return {
        "obligations": dict(snapshot.obligations),
        "possessions": dict(snapshot.possessions),
    }


def subsystem_backfill_state(snapshot: ColdBootSnapshot, subsystem: str) -> BackfillState:
    """An empty structured subsystem means unknown/unbackfilled, never nonexistence."""
    rows = snapshot.subsystem_rows.get(subsystem)
    return BackfillState.KNOWN if rows else BackfillState.UNKNOWN


def temporally_valid_facts(
    snapshot: ColdBootSnapshot,
    scene_year: int,
    *,
    author_cross_book: bool = False,
) -> tuple[TemporalFact, ...]:
    """Prevent later-saga facts from leaking backward into an earlier scene.

    Author-side cross-book analysis may opt in to the full set; ordinary scene boot may not.
    """
    if author_cross_book:
        return tuple(snapshot.temporal_facts)
    return tuple(fact for fact in snapshot.temporal_facts if fact.valid_from_year <= scene_year)
