from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence

from bloom_engine.contracts.resolution import Resolution
from bloom_engine.pantheon.registry import owner_for


@dataclass(frozen=True, slots=True)
class CoreRequest:
    predicate: str
    subject_refs: Sequence[str] = field(default_factory=tuple)
    inputs: Mapping[str, Any] = field(default_factory=dict)
    evidence: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    permission_mode: str = "READ"


class SovereignCore(Protocol):
    name: str

    def resolve(self, request: CoreRequest) -> Resolution:
        ...


def assert_core_may_answer(core_name: str, predicate: str) -> None:
    owner = owner_for(predicate)
    if owner.name != core_name:
        raise PermissionError(
            f"{core_name} may not answer {predicate!r}; sovereign owner is {owner.name}"
        )


def resolve_with_owner_guard(core: SovereignCore, request: CoreRequest) -> Resolution:
    assert_core_may_answer(core.name, request.predicate)
    result = core.resolve(request)
    if result.owner != core.name:
        raise ValueError(
            f"resolver returned owner={result.owner!r}; expected {core.name!r}"
        )
    if result.predicate != request.predicate:
        raise ValueError("resolver changed the requested predicate")
    result.require_evidence_for_decisive_status()
    return result
