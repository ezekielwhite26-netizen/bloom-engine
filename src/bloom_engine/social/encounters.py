from __future__ import annotations

from typing import Sequence

from bloom_engine.social.models import (
    EncounterChannel,
    EncounterDecision,
    EncounterEvidence,
    EncounterEvidenceState,
)


def evaluate_encounter_channel(
    channel: EncounterChannel,
    evidence: Sequence[EncounterEvidence],
) -> EncounterDecision:
    """Combine already-resolved prerequisites without inventing presence.

    Rules are intentionally conservative:
    - any required KNOWN_FALSE blocks the channel;
    - any UNKNOWN keeps the channel UNKNOWN;
    - NOT_APPLICABLE cannot be used as positive support;
    - at least one positive sovereign fact is required for CAN_ARRIVE.

    The caller is responsible for requesting the right sovereign predicates for
    the channel (typically EUNOMIA + CHRONOS + ATLAS, with HERA/MNEMOSYNE/etc.
    when relevant). This helper never calls a core and never promotes a social
    candidate into an established relationship.
    """

    if not evidence:
        return EncounterDecision.UNKNOWN

    if any(item.state is EncounterEvidenceState.KNOWN_FALSE for item in evidence):
        return EncounterDecision.CANNOT_ARRIVE

    if any(item.state is EncounterEvidenceState.UNKNOWN for item in evidence):
        return EncounterDecision.UNKNOWN

    positives = [item for item in evidence if item.state is EncounterEvidenceState.KNOWN_TRUE]
    if not positives:
        return EncounterDecision.UNKNOWN

    return EncounterDecision.CAN_ARRIVE
