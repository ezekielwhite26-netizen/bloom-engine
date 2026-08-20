from bloom_engine.runtime.world_fill import (
    CanonClass,
    WorldFillDecision,
    WorldFillPolicy,
    WorldFillProposal,
)


def proposal(**overrides):
    values = dict(
        predicate="schedule.student_period",
        proposed_by_owner="CHRONOS",
        canon_class=CanonClass.DURABLE_GENERATED_CANON,
        fact_key="AMARA::PERIOD-3",
        reason_needed="Resolve ordinary Academy encounter continuity.",
        supporting_constraints=("Amara is enrolled as a junior.", "Period 3 is currently OPEN."),
        conflict_keys=(),
        provenance_refs=("AH-ACADEMY-SOCIAL-WEB-v0.1",),
        source_run="RUN::ACADEMY::BUILD-SOCIAL-WEB",
        user_approved=False,
    )
    values.update(overrides)
    return WorldFillProposal(**values)


def test_mundane_schedule_gap_can_become_auto_commit_eligible():
    result = WorldFillPolicy().assess(proposal())
    assert result.decision is WorldFillDecision.AUTO_COMMIT_ELIGIBLE
    assert result.owner == "CHRONOS"
    assert result.rule_id == "WF-CHRONOS-SCHEDULE"


def test_wrong_core_cannot_originate_fact():
    result = WorldFillPolicy().assess(proposal(proposed_by_owner="CALLIOPE"))
    assert result.decision is WorldFillDecision.BLOCKED


def test_existing_conflict_blocks_instead_of_overwriting_canon():
    result = WorldFillPolicy().assess(proposal(conflict_keys=("AMARA::PERIOD-3::BIOLOGY",)))
    assert result.decision is WorldFillDecision.BLOCKED


def test_ephemeral_fact_is_never_promoted_to_durable_canon():
    result = WorldFillPolicy().assess(
        proposal(canon_class=CanonClass.EPHEMERAL, supporting_constraints=(), provenance_refs=())
    )
    assert result.decision is WorldFillDecision.EPHEMERAL_ONLY


def test_protected_fact_requires_user_approval():
    protected = proposal(
        predicate="relationship.romance.secret_attraction",
        proposed_by_owner="HERA",
        canon_class=CanonClass.PROTECTED_CANON,
    )
    result = WorldFillPolicy().assess(protected)
    assert result.decision is WorldFillDecision.USER_APPROVAL_REQUIRED


def test_caller_cannot_downgrade_server_protected_predicate_to_generated_canon():
    protected = proposal(
        predicate="relationship.romance.secret_attraction",
        proposed_by_owner="HERA",
        canon_class=CanonClass.DURABLE_GENERATED_CANON,
    )
    result = WorldFillPolicy().assess(protected)
    assert result.decision is WorldFillDecision.USER_APPROVAL_REQUIRED


def test_caller_cannot_downgrade_server_protected_predicate_to_ephemeral_then_approve():
    protected = proposal(
        predicate="relationship.romance.secret_attraction",
        proposed_by_owner="HERA",
        canon_class=CanonClass.EPHEMERAL,
        user_approved=True,
    )
    result = WorldFillPolicy().assess(protected)
    assert result.decision is WorldFillDecision.COMMIT_ELIGIBLE_AFTER_APPROVAL


def test_user_approved_protected_fact_can_only_proceed_to_persistence_gates():
    protected = proposal(
        predicate="relationship.romance.secret_attraction",
        proposed_by_owner="HERA",
        canon_class=CanonClass.PROTECTED_CANON,
        user_approved=True,
    )
    result = WorldFillPolicy().assess(protected)
    assert result.decision is WorldFillDecision.COMMIT_ELIGIBLE_AFTER_APPROVAL


def test_unlisted_durable_predicate_fails_closed():
    result = WorldFillPolicy().assess(
        proposal(
            predicate="personality.hidden_resentment",
            proposed_by_owner="MNEMOSYNE",
        )
    )
    assert result.decision is WorldFillDecision.BLOCKED


def test_durable_fact_requires_constraints_reason_and_provenance():
    policy = WorldFillPolicy()
    assert policy.assess(proposal(supporting_constraints=())).decision is WorldFillDecision.BLOCKED
    assert policy.assess(proposal(reason_needed="")).decision is WorldFillDecision.BLOCKED
    assert policy.assess(proposal(provenance_refs=())).decision is WorldFillDecision.BLOCKED


def test_low_risk_familiarity_edge_is_bounded_and_auto_eligible():
    result = WorldFillPolicy().assess(
        proposal(
            predicate="relationship.familiarity.school_acquaintance",
            proposed_by_owner="HERA",
            fact_key="AMARA::MAYA::FAMILIARITY",
            supporting_constraints=("Shared Chemistry section is durable canon.",),
        )
    )
    assert result.decision is WorldFillDecision.AUTO_COMMIT_ELIGIBLE
    assert result.rule_id == "WF-HERA-FAMILIARITY"
