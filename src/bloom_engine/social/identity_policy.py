from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence


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

    ``ordinary_role_code`` and ``ordinary_role`` must match a server-owned role
    catalog entry. The free-text role string is therefore only the canonical
    display label for an already-authorized mundane role; callers cannot widen
    the meaning of the identity shell by supplying arbitrary role prose.
    """

    proposed_name: str
    ordinary_role: str
    population_scope: str
    reason_needed: str
    ordinary_role_code: str = ""
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

    The policy deliberately permits only the identity shell plus a server-owned
    ordinary structural role. Magical status/capability, protected relationships,
    genealogy, hidden plot function, focal status, and major authority remain
    separately protected truths.
    """

    role_catalog: Mapping[str, Mapping[str, str]] = {
        "ACADEMY_STUDENT": {
            "academy.student.peer": "Academy student peer",
            "academy.student.activity_participant": "Academy student activity participant",
        },
        "ACADEMY_STAFF": {
            "academy.staff.teacher": "Academy teacher",
            "academy.staff.student_support": "Academy student-support staff",
            "academy.staff.activity_advisor": "Academy activity advisor",
        },
        "TOWN_ORDINARY": {
            "town.resident": "Town resident",
            "town.worker": "Town worker",
            "town.neighbor": "Town neighbor",
        },
        "HOLLOW_CIRCLE_SUPPORTING_PERSON": {
            "hollow_circle.community_participant": "Hollow Circle community participant",
            "hollow_circle.logistics_support": "Hollow Circle community logistics support",
        },
    }
    allowed_scopes = frozenset(role_catalog)

    def assess(self, proposal: SupportingNpcIdentityProposal) -> SupportingNpcAssessment:
        if not proposal.proposed_name.strip():
            return SupportingNpcAssessment(SupportingNpcDecision.BLOCKED, message="Supporting identity requires a proposed name.")
        if proposal.population_scope not in self.allowed_scopes:
            return SupportingNpcAssessment(SupportingNpcDecision.BLOCKED, message="Population scope is not authorized for automatic supporting identity creation.")
        if not proposal.ordinary_role_code.strip():
            return SupportingNpcAssessment(SupportingNpcDecision.BLOCKED, message="Supporting identity requires a server-owned ordinary role code.")

        canonical_role = self.role_catalog[proposal.population_scope].get(proposal.ordinary_role_code)
        if canonical_role is None:
            return SupportingNpcAssessment(
                SupportingNpcDecision.BLOCKED,
                message="Ordinary role code is not authorized for this population scope.",
            )
        if proposal.ordinary_role != canonical_role:
            return SupportingNpcAssessment(
                SupportingNpcDecision.BLOCKED,
                message="Ordinary role text must exactly match the server-owned role catalog; arbitrary role prose cannot establish canon.",
            )
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
                "Ordinary supporting identity shell and server-owned structural role may proceed to THEMIS duplicate/name checks, "
                "ADRASTEIA validation, stable-ID allocation, and capability-gated CLIO persistence."
            ),
        )
