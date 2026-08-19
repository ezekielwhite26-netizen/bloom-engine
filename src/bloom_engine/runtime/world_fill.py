from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence

from bloom_engine.pantheon.registry import owner_for


class CanonClass(str, Enum):
    EPHEMERAL = "EPHEMERAL"
    DURABLE_GENERATED_CANON = "DURABLE_GENERATED_CANON"
    PROTECTED_CANON = "PROTECTED_CANON"


class WorldFillDecision(str, Enum):
    EPHEMERAL_ONLY = "EPHEMERAL_ONLY"
    AUTO_COMMIT_ELIGIBLE = "AUTO_COMMIT_ELIGIBLE"
    USER_APPROVAL_REQUIRED = "USER_APPROVAL_REQUIRED"
    COMMIT_ELIGIBLE_AFTER_APPROVAL = "COMMIT_ELIGIBLE_AFTER_APPROVAL"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class WorldFillRule:
    """Server-owned authorization for one bounded category of mundane world fill.

    The model/client may request a fill, but this catalog decides whether the
    predicate is ever eligible for automatic durable canon. Rules grant no write
    capability by themselves; CLIO + ADRASTEIA still gate persistence.
    """

    rule_id: str
    predicate_prefix: str
    owner: str
    description: str

    def matches(self, predicate: str) -> bool:
        return predicate.startswith(self.predicate_prefix)


DEFAULT_WORLD_FILL_RULES: tuple[WorldFillRule, ...] = (
    WorldFillRule(
        "WF-CHRONOS-SCHEDULE",
        "schedule.",
        "CHRONOS",
        "Low-risk recurring schedules such as class periods, shifts, and meetings.",
    ),
    WorldFillRule(
        "WF-EUNOMIA-INSTITUTION",
        "institution.",
        "EUNOMIA",
        "Low-risk institutional structure or membership needed for ordinary continuity.",
    ),
    WorldFillRule(
        "WF-EUNOMIA-ORGANIZATION",
        "organization.",
        "EUNOMIA",
        "Low-risk organization membership/role structure that does not alter protected authority.",
    ),
    WorldFillRule(
        "WF-HERA-FAMILIARITY",
        "relationship.familiarity.",
        "HERA",
        "Ordinary acquaintance/familiarity edges; never romance, betrayal, intimacy, or major bond changes.",
    ),
)


@dataclass(frozen=True, slots=True)
class WorldFillProposal:
    predicate: str
    proposed_by_owner: str
    canon_class: CanonClass
    fact_key: str
    reason_needed: str
    supporting_constraints: Sequence[str] = field(default_factory=tuple)
    conflict_keys: Sequence[str] = field(default_factory=tuple)
    provenance_refs: Sequence[str] = field(default_factory=tuple)
    source_run: str = ""
    user_approved: bool = False


@dataclass(frozen=True, slots=True)
class WorldFillAssessment:
    decision: WorldFillDecision
    owner: str
    rule_id: str | None = None
    message: str = ""


class WorldFillPolicy:
    """Fail-closed canonization policy for newly resolved world-detail gaps.

    This policy does not generate facts and does not persist them. It only says
    whether a sovereignly proposed fact may proceed to the ADRASTEIA/CLIO gates.
    """

    def __init__(self, rules: Sequence[WorldFillRule] = DEFAULT_WORLD_FILL_RULES):
        self.rules = tuple(rules)

    def _matching_rule(self, proposal: WorldFillProposal) -> WorldFillRule | None:
        matches = [rule for rule in self.rules if rule.matches(proposal.predicate)]
        if len(matches) > 1:
            raise ValueError(f"World-fill predicate matched multiple rules: {proposal.predicate}")
        return matches[0] if matches else None

    def assess(self, proposal: WorldFillProposal) -> WorldFillAssessment:
        sovereign_owner = owner_for(proposal.predicate).name
        if proposal.proposed_by_owner != sovereign_owner:
            return WorldFillAssessment(
                WorldFillDecision.BLOCKED,
                sovereign_owner,
                message="Proposal did not originate from the predicate's sovereign owner.",
            )

        if proposal.conflict_keys:
            return WorldFillAssessment(
                WorldFillDecision.BLOCKED,
                sovereign_owner,
                message="Existing canon conflict must be resolved before world fill.",
            )

        if proposal.canon_class is CanonClass.EPHEMERAL:
            return WorldFillAssessment(
                WorldFillDecision.EPHEMERAL_ONLY,
                sovereign_owner,
                message="Usable for the current run only; do not persist as durable canon.",
            )

        if proposal.canon_class is CanonClass.PROTECTED_CANON:
            if proposal.user_approved:
                return WorldFillAssessment(
                    WorldFillDecision.COMMIT_ELIGIBLE_AFTER_APPROVAL,
                    sovereign_owner,
                    message="Protected canon has explicit user approval; ADRASTEIA/CLIO must still validate and persist.",
                )
            return WorldFillAssessment(
                WorldFillDecision.USER_APPROVAL_REQUIRED,
                sovereign_owner,
                message="Protected canon cannot be automatically canonized.",
            )

        rule = self._matching_rule(proposal)
        if rule is None or rule.owner != sovereign_owner:
            return WorldFillAssessment(
                WorldFillDecision.BLOCKED,
                sovereign_owner,
                message="No server-owned auto-canon rule authorizes this predicate.",
            )
        if not proposal.supporting_constraints:
            return WorldFillAssessment(
                WorldFillDecision.BLOCKED,
                sovereign_owner,
                rule_id=rule.rule_id,
                message="Durable generated canon requires explicit supporting constraints.",
            )
        if not proposal.reason_needed.strip():
            return WorldFillAssessment(
                WorldFillDecision.BLOCKED,
                sovereign_owner,
                rule_id=rule.rule_id,
                message="Durable generated canon requires a recorded reason for resolution.",
            )
        if not proposal.provenance_refs:
            return WorldFillAssessment(
                WorldFillDecision.BLOCKED,
                sovereign_owner,
                rule_id=rule.rule_id,
                message="Durable generated canon requires provenance references.",
            )

        return WorldFillAssessment(
            WorldFillDecision.AUTO_COMMIT_ELIGIBLE,
            sovereign_owner,
            rule_id=rule.rule_id,
            message="Eligible to proceed to ADRASTEIA and capability-gated CLIO persistence.",
        )
