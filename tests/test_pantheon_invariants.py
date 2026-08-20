import pytest

from bloom_engine.contracts.resolution import Resolution, ResolutionStatus
from bloom_engine.pantheon.invariants import (
    InvariantViolation,
    PANTHEON_INVARIANTS,
    assert_adrasteia_independent,
    assert_athena_did_not_invent_eligibility,
    assert_calliope_did_not_mutate_reality,
    assert_clio_realized_only,
    assert_non_sovereign_stage_did_not_originate_truth,
    assert_required_resolutions_known,
    assert_resolution_owner_matches_predicate,
)


def evidence(fact: str = "fixture"):
    return ({"source": "test fixture", "fact": fact},)


def known(predicate: str, owner: str) -> Resolution:
    return Resolution(
        owner=owner,
        predicate=predicate,
        status=ResolutionStatus.KNOWN,
        value=True,
        evidence=evidence(),
    )


def unknown(predicate: str, owner: str) -> Resolution:
    return Resolution(
        owner=owner,
        predicate=predicate,
        status=ResolutionStatus.UNKNOWN,
        evidence=evidence("checked but unresolved"),
        missing_required=("required fact",),
    )


def test_107_invariant_catalog_has_expected_stable_ids():
    assert tuple(spec.stable_id for spec in PANTHEON_INVARIANTS) == tuple(
        f"BLM-TST-{number:06d}" for number in range(107, 116)
    )


def test_107_one_owner_sovereignty_rejects_wrong_owner():
    with pytest.raises(InvariantViolation):
        assert_resolution_owner_matches_predicate(known("magic.form", "ATLAS"))


def test_108_compiler_cannot_originate_truth():
    assert_non_sovereign_stage_did_not_originate_truth("CONTEXT_COMPILER", ())
    with pytest.raises(InvariantViolation):
        assert_non_sovereign_stage_did_not_originate_truth(
            "CONTEXT_COMPILER", ("time.current",)
        )


def test_109_unknown_fails_closed_for_required_gate():
    with pytest.raises(InvariantViolation):
        assert_required_resolutions_known((unknown("access.connected_endpoint", "ATLAS"),))


def test_110_athena_cannot_select_when_upstream_gate_is_unknown():
    with pytest.raises(InvariantViolation):
        assert_athena_did_not_invent_eligibility(
            (unknown("working.eligible", "HECATE"),),
            selected_option="perform Working",
        )


def test_111_calliope_cannot_mutate_reality():
    assert_calliope_did_not_mutate_reality(None)
    with pytest.raises(InvariantViolation):
        assert_calliope_did_not_mutate_reality({"possession.current_holder": "Florence"})


def test_112_clio_persists_realized_authorized_only():
    assert_clio_realized_only(realized=True, persistence_authorized=True, delta_present=True)
    with pytest.raises(InvariantViolation):
        assert_clio_realized_only(realized=False, persistence_authorized=True, delta_present=True)
    with pytest.raises(InvariantViolation):
        assert_clio_realized_only(realized=True, persistence_authorized=False, delta_present=True)


def test_113_adrasteia_gate_is_independent():
    assert_adrasteia_independent(producer_core="CLIO", validator_core="ADRASTEIA")
    with pytest.raises(InvariantViolation):
        assert_adrasteia_independent(producer_core="ADRASTEIA", validator_core="ADRASTEIA")


def test_114_world_simulator_is_non_sovereign():
    assert_non_sovereign_stage_did_not_originate_truth("WORLD_SIMULATOR", ())
    with pytest.raises(InvariantViolation):
        assert_non_sovereign_stage_did_not_originate_truth(
            "WORLD_SIMULATOR", ("forecast.current",)
        )


def test_115_current_scene_is_projection_not_authority():
    assert_non_sovereign_stage_did_not_originate_truth("CURRENT_SCENE", ())
    with pytest.raises(InvariantViolation):
        assert_non_sovereign_stage_did_not_originate_truth(
            "CURRENT_SCENE", ("location.current",)
        )
