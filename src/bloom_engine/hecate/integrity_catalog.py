from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class HecateIntegritySpec:
    stable_id: str
    key: str
    requirement: str


HECATE_INTEGRITY_TESTS: tuple[HecateIntegritySpec, ...] = (
    HecateIntegritySpec(
        "BLM-TST-000116",
        "HECATE-RESOLVER-STATUS-EXHAUSTIVE",
        "Every HECATE resolution has exactly one of KNOWN, UNKNOWN, BLOCKED, NOT_APPLICABLE.",
    ),
    HecateIntegritySpec(
        "BLM-TST-000117",
        "HECATE-EVIDENCE-REQUIRED",
        "KNOWN/BLOCKED require evidence; UNKNOWN identifies checked evidence and missing facts; NOT_APPLICABLE explains irrelevance.",
    ),
    HecateIntegritySpec(
        "BLM-TST-000118",
        "HECATE-PASSAGE-NO-ENDPOINT-INVENTION",
        "Passage is BLOCKED when a genuine connected endpoint is known absent.",
    ),
    HecateIntegritySpec(
        "BLM-TST-000119",
        "HECATE-FOCUS-NO-POWER-BATTERY",
        "Focus externalizes Working function and Heat remains embodied strain rather than mana/fuel.",
    ),
    HecateIntegritySpec(
        "BLM-TST-000120",
        "HECATE-NONFOCUS-NO-PROMOTION",
        "Explicit non-Foci remain supported negative Focus results despite enchantment, beauty, theme, or repeated mention.",
    ),
    HecateIntegritySpec(
        "BLM-TST-000121",
        "HECATE-EXTERNAL-OWNER-BOUNDARY",
        "HECATE surfaces non-magical prerequisites with the true sovereign owner and never answers them itself.",
    ),
    HecateIntegritySpec(
        "BLM-TST-000122",
        "HECATE-ORDINARY-ACTION-NOT-APPLICABLE",
        "Ordinary non-magical actions return NOT_APPLICABLE unless a magical predicate is actually requested.",
    ),
    HecateIntegritySpec(
        "BLM-TST-000123",
        "HECATE-PASSAGE-FOCUS-FUNCTION-DEGRADATION",
        "Episode 6 Focus comparisons remain specific qualitative evidence; no universal omission rule or numeric Heat cost is invented.",
    ),
)
