from bloom_engine.social.identity_policy import (
    SupportingNpcDecision,
    SupportingNpcIdentityPolicy,
    SupportingNpcIdentityProposal,
)


def _proposal(**overrides):
    base = dict(
        proposed_name="Maya Chen",
        ordinary_role="Academy junior and Student Council events volunteer",
        population_scope="ACADEMY_STUDENT",
        reason_needed="Fill a recurring ordinary school-network role around Florence.",
        supporting_constraints=("junior cohort", "student activity overlap"),
        provenance_refs=("ASTER_HOLLOW_ACADEMY_POPULATION_PLAN_V01",),
    )
    base.update(overrides)
    return SupportingNpcIdentityProposal(**base)


def test_plain_supporting_student_identity_can_become_auto_canon_eligible():
    result = SupportingNpcIdentityPolicy().assess(_proposal())
    assert result.decision is SupportingNpcDecision.AUTO_CANON_ELIGIBLE
    assert result.owner == "THEMIS"


def test_client_or_model_cannot_choose_stable_id():
    result = SupportingNpcIdentityPolicy().assess(_proposal(requested_stable_id="BLM-CHR-999999"))
    assert result.decision is SupportingNpcDecision.BLOCKED


def test_duplicate_candidate_blocks_new_identity():
    result = SupportingNpcIdentityPolicy().assess(_proposal(duplicate_identity_refs=("BLM-CHR-000777",)))
    assert result.decision is SupportingNpcDecision.BLOCKED


def test_old_family_or_genealogy_link_requires_user_approval():
    result = SupportingNpcIdentityPolicy().assess(_proposal(protected_family_or_genealogy=True))
    assert result.decision is SupportingNpcDecision.USER_APPROVAL_REQUIRED


def test_magic_cannot_hide_inside_supporting_identity_creation():
    result = SupportingNpcIdentityPolicy().assess(_proposal(magical_truth_embedded=True))
    assert result.decision is SupportingNpcDecision.USER_APPROVAL_REQUIRED


def test_friendship_or_romance_truth_cannot_hide_inside_identity_creation():
    result = SupportingNpcIdentityPolicy().assess(_proposal(protected_relationship_truth=True))
    assert result.decision is SupportingNpcDecision.USER_APPROVAL_REQUIRED


def test_focal_character_creation_is_not_auto_canon():
    result = SupportingNpcIdentityPolicy().assess(_proposal(focal_or_protagonist_role=True))
    assert result.decision is SupportingNpcDecision.USER_APPROVAL_REQUIRED


def test_hidden_plot_function_is_not_auto_canon():
    result = SupportingNpcIdentityPolicy().assess(_proposal(hidden_plot_truth_embedded=True))
    assert result.decision is SupportingNpcDecision.USER_APPROVAL_REQUIRED


def test_major_authority_role_is_not_auto_canon():
    result = SupportingNpcIdentityPolicy().assess(_proposal(major_authority_role=True))
    assert result.decision is SupportingNpcDecision.USER_APPROVAL_REQUIRED


def test_unknown_scope_fails_closed():
    result = SupportingNpcIdentityPolicy().assess(_proposal(population_scope="SECRET_RULING_COUNCIL"))
    assert result.decision is SupportingNpcDecision.BLOCKED


def test_missing_constraints_fails_closed():
    result = SupportingNpcIdentityPolicy().assess(_proposal(supporting_constraints=()))
    assert result.decision is SupportingNpcDecision.BLOCKED


def test_hollow_circle_identity_shell_does_not_imply_magic():
    result = SupportingNpcIdentityPolicy().assess(
        _proposal(
            proposed_name="Jordan Reyes",
            ordinary_role="supporting person in Circle community logistics",
            population_scope="HOLLOW_CIRCLE_SUPPORTING_PERSON",
            magical_truth_embedded=False,
        )
    )
    assert result.decision is SupportingNpcDecision.AUTO_CANON_ELIGIBLE
