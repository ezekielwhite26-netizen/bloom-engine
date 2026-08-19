from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from bloom_engine.contracts.resolution import Resolution, ResolutionStatus
from bloom_engine.pantheon.registry import owner_for


class InvariantViolation(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class InvariantSpec:
    stable_id: str
    key: str
    summary: str


PANTHEON_INVARIANTS: tuple[InvariantSpec, ...] = (
    InvariantSpec("BLM-TST-000107", "RUNTIME-ONE-OWNER-SOVEREIGNTY-001", "Every substantive predicate has exactly one sovereign owner."),
    InvariantSpec("BLM-TST-000108", "RUNTIME-COMPILER-NO-TRUTH-001", "Context Compiler routes/assembles but does not originate truth."),
    InvariantSpec("BLM-TST-000109", "RUNTIME-UNKNOWN-FAIL-CLOSED-001", "UNKNOWN cannot satisfy a required positive gate."),
    InvariantSpec("BLM-TST-000110", "RUNTIME-ATHENA-NO-ELIGIBILITY-INVENTION-001", "ATHENA chooses only among upstream-eligible options."),
    InvariantSpec("BLM-TST-000111", "RUNTIME-CALLIOPE-NO-REALITY-CHANGE-001", "CALLIOPE may render but may not mutate reality."),
    InvariantSpec("BLM-TST-000112", "RUNTIME-CLIO-REALIZED-ONLY-001", "CLIO persists only realized, authorized deltas."),
    InvariantSpec("BLM-TST-000113", "RUNTIME-ADRASTEIA-INDEPENDENT-GATE-001", "ADRASTEIA validates independently of the producer."),
    InvariantSpec("BLM-TST-000114", "RUNTIME-WORLD-SIMULATOR-NON-SOVEREIGN-001", "World Simulator orchestrates sovereign cores and owns no truth."),
    InvariantSpec("BLM-TST-000115", "RUNTIME-CURRENT-SCENE-PROJECTION-001", "Current Scene is a projection/cache, never authority."),
)


NON_SOVEREIGN_STAGES = frozenset({"CONTEXT_COMPILER", "WORLD_SIMULATOR", "CURRENT_SCENE"})


def assert_resolution_owner_matches_predicate(result: Resolution) -> None:
    expected = owner_for(result.predicate).name
    if result.owner != expected:
        raise InvariantViolation(
            f"predicate {result.predicate!r} is owned by {expected}, not {result.owner}"
        )


def assert_resolution_semantics(result: Resolution) -> None:
    """Validate the universal status/evidence semantics without inventing truth."""
    if not isinstance(result.status, ResolutionStatus):
        raise InvariantViolation(f"unsupported resolution status {result.status!r}")
    assert_resolution_owner_matches_predicate(result)

    if result.status in {ResolutionStatus.KNOWN, ResolutionStatus.BLOCKED} and not result.evidence:
        raise InvariantViolation(f"{result.status.value} requires authoritative evidence")
    if result.status is ResolutionStatus.UNKNOWN and not result.missing_required:
        raise InvariantViolation("UNKNOWN must identify at least one missing required fact")
    if result.status is ResolutionStatus.NOT_APPLICABLE:
        reason = str(result.metadata.get("reason", "")).strip()
        if not reason:
            raise InvariantViolation("NOT_APPLICABLE must explain why the owner is irrelevant")

    for prerequisite in result.external_prerequisites:
        external_owner = str(prerequisite.get("owner", ""))
        external_predicate = str(prerequisite.get("predicate", ""))
        if not external_owner or not external_predicate:
            raise InvariantViolation("external prerequisite must name owner and predicate")
        true_owner = owner_for(external_predicate).name
        if true_owner != external_owner:
            raise InvariantViolation(
                f"external prerequisite {external_predicate!r} belongs to {true_owner}, "
                f"not declared owner {external_owner}"
            )
        if external_owner == result.owner:
            raise InvariantViolation("same-owner prerequisite must be resolved internally, not externalized")


def assert_required_resolutions_known(
    resolutions: Iterable[Resolution],
    required_predicates: Sequence[str] | None = None,
) -> None:
    by_predicate = {result.predicate: result for result in resolutions}
    required = tuple(required_predicates or by_predicate.keys())
    for predicate in required:
        result = by_predicate.get(predicate)
        if result is None:
            raise InvariantViolation(f"required predicate {predicate!r} was not resolved")
        assert_resolution_semantics(result)
        if result.status is not ResolutionStatus.KNOWN:
            raise InvariantViolation(
                f"required predicate {predicate!r} failed closed with {result.status.value}"
            )


def assert_non_sovereign_stage_did_not_originate_truth(
    stage: str,
    originated_predicates: Sequence[str],
) -> None:
    stage = stage.upper()
    if stage not in NON_SOVEREIGN_STAGES:
        raise InvariantViolation(f"{stage} is not registered as a non-sovereign stage")
    if originated_predicates:
        raise InvariantViolation(
            f"{stage} attempted to originate sovereign predicates: {tuple(originated_predicates)}"
        )


def assert_athena_did_not_invent_eligibility(
    upstream: Iterable[Resolution],
    selected_option: str | None,
) -> None:
    if selected_option is None:
        return
    assert_required_resolutions_known(tuple(upstream))


def assert_calliope_did_not_mutate_reality(proposed_state_delta: Mapping[str, object] | None) -> None:
    if proposed_state_delta:
        raise InvariantViolation("CALLIOPE may render selected reality but may not produce durable state deltas")


def assert_clio_realized_only(*, realized: bool, persistence_authorized: bool, delta_present: bool) -> None:
    if delta_present and not realized:
        raise InvariantViolation("CLIO may not persist a merely proposed/unrealized delta")
    if delta_present and not persistence_authorized:
        raise InvariantViolation("CLIO may not persist without an authorized persistence envelope")


def assert_adrasteia_independent(*, producer_core: str, validator_core: str) -> None:
    if validator_core.upper() != "ADRASTEIA":
        raise InvariantViolation("commit/integrity gate must be performed by ADRASTEIA")
    if producer_core.upper() == "ADRASTEIA":
        raise InvariantViolation("ADRASTEIA gate must be independent of the producer being validated")
