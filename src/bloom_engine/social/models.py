from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Sequence


class RelationshipStatus(str, Enum):
    """Epistemic/canon status of a social relation.

    ESTABLISHED is durable canon. SUPPORTED_CANDIDATE is a well-supported
    possibility that must not be narrated or persisted as if already true.
    OPEN is merely plausible/unresolved.
    """

    ESTABLISHED = "ESTABLISHED"
    SUPPORTED_CANDIDATE = "SUPPORTED_CANDIDATE"
    OPEN = "OPEN"


class EncounterChannelKind(str, Enum):
    HOUSEHOLD = "HOUSEHOLD"
    FAMILY = "FAMILY"
    SCHOOL_COHORT = "SCHOOL_COHORT"
    CLASS = "CLASS"
    STUDENT_ACTIVITY = "STUDENT_ACTIVITY"
    ORGANIZATION = "ORGANIZATION"
    MENTORSHIP = "MENTORSHIP"
    WORKPLACE = "WORKPLACE"
    NEIGHBORHOOD = "NEIGHBORHOOD"
    ROUTE = "ROUTE"
    COMMUNITY = "COMMUNITY"
    EVENT = "EVENT"


class EncounterEvidenceState(str, Enum):
    KNOWN_TRUE = "KNOWN_TRUE"
    KNOWN_FALSE = "KNOWN_FALSE"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EncounterDecision(str, Enum):
    CAN_ARRIVE = "CAN_ARRIVE"
    CANNOT_ARRIVE = "CANNOT_ARRIVE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class RelationshipEdge:
    edge_key: str
    left_ref: str
    right_ref: str
    relation_kind: str
    status: RelationshipStatus
    provenance_refs: Sequence[str] = field(default_factory=tuple)
    notes: str = ""


@dataclass(frozen=True, slots=True)
class EncounterEvidence:
    """One already-resolved sovereign prerequisite for an encounter channel."""

    owner: str
    predicate: str
    state: EncounterEvidenceState
    provenance_refs: Sequence[str] = field(default_factory=tuple)
    detail: str = ""


@dataclass(frozen=True, slots=True)
class EncounterChannel:
    """One structural reason two people may regularly cross paths.

    A channel is connective metadata, not proof that an encounter is happening.
    Runtime eligibility still depends on sovereign evidence such as schedule,
    location, institutional membership, and any channel-specific prerequisites.
    """

    channel_key: str
    focal_ref: str
    other_ref: str
    kind: EncounterChannelKind
    recurring: bool = False
    relationship_edge_keys: Sequence[str] = field(default_factory=tuple)
    source_refs: Sequence[str] = field(default_factory=tuple)
    notes: str = ""
