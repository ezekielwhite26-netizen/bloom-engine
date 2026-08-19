from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from bloom_engine.pantheon.protocol import CoreRequest
from bloom_engine.pantheon.registry import owner_for


@dataclass(frozen=True, slots=True)
class SimulationBoundary:
    """A material boundary already established by sovereign/runtime state.

    The World Simulator may orchestrate evaluation around this boundary, but it
    does not establish the boundary's truth, timing, location, or participants.
    """

    boundary_key: str
    kind: str
    evidence: Sequence[Mapping[str, Any]] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SimulationPlan:
    boundary: SimulationBoundary
    requests: tuple[CoreRequest, ...]
    requires_athena: bool = False
    notes: tuple[str, ...] = ()

    @property
    def owners(self) -> tuple[str, ...]:
        return tuple(owner_for(request.predicate).name for request in self.requests)


class WorldSimulatorOrchestrator:
    """Builds owner-routed evaluation plans for off-screen/boundary advancement.

    This class is deliberately non-sovereign. It does not answer any predicate,
    mutate canon, select narrative outcomes, or persist state. It may only turn
    an already-established material boundary plus requested predicates into a
    deterministic owner-routed query plan.
    """

    def plan(
        self,
        *,
        boundary: SimulationBoundary,
        requests: Iterable[CoreRequest],
        genuine_discretion: bool = False,
    ) -> SimulationPlan:
        ordered = tuple(requests)
        if not boundary.evidence:
            raise ValueError("simulation boundary requires evidence")
        if not ordered:
            raise ValueError("simulation plan requires at least one sovereign request")

        seen_predicates: set[tuple[str, tuple[str, ...]]] = set()
        for request in ordered:
            owner_for(request.predicate)  # fail closed on missing/ambiguous ownership
            key = (request.predicate, tuple(request.subject_refs))
            if key in seen_predicates:
                raise ValueError(
                    "duplicate sovereign query in one simulation plan: "
                    f"{request.predicate!r} {tuple(request.subject_refs)!r}"
                )
            seen_predicates.add(key)

        has_athena_query = any(owner_for(request.predicate).name == "ATHENA" for request in ordered)
        if has_athena_query and not genuine_discretion:
            raise PermissionError(
                "ATHENA may only be included when the boundary exposes genuine discretion; "
                "deterministic state advancement must not be turned into a decision"
            )
        if genuine_discretion and not has_athena_query:
            raise ValueError(
                "genuine_discretion=True requires an explicit ATHENA request; "
                "the World Simulator cannot make the discretionary choice itself"
            )

        return SimulationPlan(
            boundary=boundary,
            requests=ordered,
            requires_athena=genuine_discretion,
            notes=(
                "World Simulator is connective only; sovereign cores answer substantive predicates.",
                "CLIO persistence is a downstream handoff after realized/authorized deltas only.",
            ),
        )
