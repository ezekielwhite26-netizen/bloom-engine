from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


class SupportingNpcDecision(str, Enum):
    AUTO_CANON_ELIGIBLE = "AUTO_CANON_ELIGIBLE"
    USER_APPROVAL_REQUIRED = "USER_APPROVAL_REQUIRED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class SupportingNpcIdentityProposal:
    """A bounded proposal for a non-focal supporting character identity.

    This is a THEMIS-facing pre-persistence policy. It does not allocate a stable
    ID and does not create canon. It decides only whether an ordinary supporting
    identity may proceed to duplicate checks, ADRASTEIA, stable-ID allocation,
    and capability-gated CLIO persistence.
    """

    proposed_name: str
    ordinary_role: str
    population_scope: str
    reason_needed: str
    supporting_constraints: Sequence[str] = field(default_factory=tuple)
    provenance_refs: Sequence[str] = field(default_factory=tuple)
    duplicate_identity_refs: Sequence[str] = field(default_factory=tuple)
    requested_stable_id: str | None = None
    focal_or_protagonist_role: bool = False
    protected_family_or_genealogy: bool = False
    protected_relationship_truth: bool = False
    magical_truth_embedded: bool = False
    hidden_plot_truth_embedded: bool = False
    major_authority_role: bool = False


@dataclass(frozen=True, slots=True)
class SupportingNpcAssessment:
    decision: SupportingNpcDecision
    owner: str = "THEMIS"
    message: str = ""


class SupportingNpcIdentityPolicy:
    """Fail-closed policy for mundane background/recurring identity creation.

    The policy deliberately permits only the identity shell plus an ordinary
    structural role. Magical status/capability, protected relationships,
    genealogy, hidden plot function, focal status, and major authority remain
    separately protected truths.
    """

    allowed_scopes = frozenset(
        {
            "ACADEMY_STUDENT",
            "ACADEMY_STAFF",
            "TOWN_ORDINARY",
            "HOLLOW_CIRCLE_SUPPORTING_PERSON",
        }
    )

    def assess(self, proposal: SupportingNpcIdentityProposal) -> SupportingNpcAssessment:
        if not proposal.proposed_name.strip():
            return SupportingNpcAssessment(SupportingNpcDecision.BLOCKED, message="Supporting identity requires a proposed name.")
        if not proposal.ordinary_role.strip():
            return SupportingNpcAssessment(SupportingNpcDecision.BLOCKED, message="Supporting identity requires an ordinary structural role.")
        if proposal.population_scope not in self.allowed_scopes:
            return SupportingNpcAssessment(SupportingNpcDecision.BLOCKED, message="Population scope is not authorized for automatic supporting identity creation.")
        if not proposal.reason_needed.strip():
            return SupportingNpcAssessment(SupportingNpcDecision.BLOCKED, message="Supporting identity requires a recorded reason for creation.")
        if not proposal.supporting_constraints:
            return SupportingNpcAssessment(SupportingNpcDecision.BLOCKED, message="Supporting identity requires explicit structural constraints.")
        if not proposal.provenance_refs:
            return SupportingNpcAssessment(SupportingNpcDecision.BLOCKED, message="Supporting identity requires provenance references.")
        if proposal.duplicate_identity_refs:
            return SupportingNpcAssessment(SupportingNpcDecision.BLOCKED, message="Possible duplicate identity must be resolved before creation.")
        if proposal.requested_stable_id is not None:
            return SupportingNpcAssessment(SupportingNpcDecision.BLOCKED, message="Caller may not choose or mint a stable ID; THEMIS allocator must assign it.")

        protected = (
            proposal.focal_or_protagonist_role
            or proposal.protected_family_or_genealogy
            or proposal.protected_relationship_truth
            or proposal.magical_truth_embedded
            or proposal.hidden_plot_truth_embedded
            or proposal.major_authority_role
        )
        if protected:
            return SupportingNpcAssessment(
                SupportingNpcDecision.USER_APPROVAL_REQUIRED,
                message="Proposal includes protected creative/authority truth and cannot auto-canonize as a supporting identity.",
            )

        return SupportingNpcAssessment(
            SupportingNpcDecision.AUTO_CANON_ELIGIBLE,
            message=(
                "Ordinary supporting identity may proceed to THEMIS duplicate/name checks, "
                "ADRASTEIA validation, stable-ID allocation, and capability-gated CLIO persistence."
            ),
        )
