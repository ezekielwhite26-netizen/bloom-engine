from __future__ import annotations

from typing import Sequence

from bloom_engine.social.models import (
    EncounterChannel,
    EncounterDecision,
    EncounterEvidence,
    EncounterEvidenceState,
)


_REQUIRED_PRESENCE_OWNERS = ("EUNOMIA", "CHRONOS", "ATLAS")


def evaluate_encounter_channel(
    channel: EncounterChannel,
    evidence: Sequence[EncounterEvidence],
) -> EncounterDecision:
    """Combine already-resolved prerequisites without inventing presence.

    Presence is a deterministic eligibility question before ATHENA or rendering.
    The minimum ordinary encounter contract is explicit evidence from EUNOMIA
    (institution/activity eligibility), CHRONOS (temporal overlap), and ATLAS
    (location/reachability), in that dependency order. HERA and other refiners
    may shape an encounter after this floor is satisfied, but they cannot stand
    in for a missing required owner.

    Rules are intentionally conservative:
    - any required KNOWN_FALSE blocks the channel;
    - a missing required owner is UNKNOWN, not implicit success;
    - any required UNKNOWN keeps the channel UNKNOWN;
    - NOT_APPLICABLE cannot be used as positive support;
    - relationship/familiarity or other optional evidence cannot establish
      physical presence by itself.

    This helper never calls a core, promotes a social candidate, invokes ATHENA,
    or creates a convenience NPC. It only combines already-resolved evidence.
    """

    if not evidence:
        return EncounterDecision.UNKNOWN

    evidence_by_owner: dict[str, list[EncounterEvidence]] = {}
    for item in evidence:
        evidence_by_owner.setdefault(item.owner, []).append(item)

    # Preserve the sovereign dependency order explicitly. A later positive fact
    # cannot compensate for a missing/unknown earlier prerequisite.
    for owner in _REQUIRED_PRESENCE_OWNERS:
        owner_evidence = evidence_by_owner.get(owner)
        if not owner_evidence:
            return EncounterDecision.UNKNOWN
        if any(item.state is EncounterEvidenceState.KNOWN_FALSE for item in owner_evidence):
            return EncounterDecision.CANNOT_ARRIVE
        if any(item.state is EncounterEvidenceState.UNKNOWN for item in owner_evidence):
            return EncounterDecision.UNKNOWN
        if not any(item.state is EncounterEvidenceState.KNOWN_TRUE for item in owner_evidence):
            return EncounterDecision.UNKNOWN

    return EncounterDecision.CAN_ARRIVE
