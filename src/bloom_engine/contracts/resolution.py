from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class ResolutionStatus(str, Enum):
    """Exhaustive sovereign resolver result states."""

    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True)
class Resolution:
    """Provider-neutral result returned by a sovereign core resolver.

    A resolver may answer only its own domain predicate. External prerequisites
    are requests to other owners, never facts synthesized by the caller.
    """

    owner: str
    predicate: str
    status: ResolutionStatus
    value: Any = None
    evidence: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    missing_required: Sequence[str] = field(default_factory=tuple)
    blockers: Sequence[str] = field(default_factory=tuple)
    external_prerequisites: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    do_not_infer: Sequence[str] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def require_evidence_for_decisive_status(self) -> None:
        """Raise when a decisive result is unsupported."""
        if self.status in {ResolutionStatus.KNOWN, ResolutionStatus.BLOCKED} and not self.evidence:
            raise ValueError(f"{self.status.value} resolution requires authoritative evidence")

    def is_eligible_for_required_gate(self) -> bool:
        """Only KNOWN can satisfy a required positive gate.

        UNKNOWN fails closed. BLOCKED is explicitly ineligible. NOT_APPLICABLE
        means the owner has no predicate to answer and must not be treated as a
        positive eligibility decision by itself.
        """
        return self.status is ResolutionStatus.KNOWN
