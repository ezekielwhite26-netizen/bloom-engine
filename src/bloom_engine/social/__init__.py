"""Connective social-graph and encounter-candidate primitives.

This package owns no world truth. HERA/EUNOMIA/CHRONOS/ATLAS and other
sovereign cores establish facts; these helpers only preserve status and combine
already-resolved evidence without upgrading UNKNOWN or candidate relationships.
"""

from bloom_engine.social.models import (
    EncounterChannel,
    EncounterChannelKind,
    EncounterDecision,
    EncounterEvidence,
    EncounterEvidenceState,
    RelationshipEdge,
    RelationshipStatus,
)
from bloom_engine.social.encounters import evaluate_encounter_channel
from bloom_engine.social.identity_policy import (
    SupportingNpcAssessment,
    SupportingNpcDecision,
    SupportingNpcIdentityPolicy,
    SupportingNpcIdentityProposal,
)

__all__ = [
    "EncounterChannel",
    "EncounterChannelKind",
    "EncounterDecision",
    "EncounterEvidence",
    "EncounterEvidenceState",
    "RelationshipEdge",
    "RelationshipStatus",
    "evaluate_encounter_channel",
    "SupportingNpcAssessment",
    "SupportingNpcDecision",
    "SupportingNpcIdentityPolicy",
    "SupportingNpcIdentityProposal",
]
