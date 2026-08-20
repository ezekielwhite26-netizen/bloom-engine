from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Sequence


FOCUS_DOCTRINE = "A Focus externalizes part of a Working; it is not a generic power battery."
HEAT_DOCTRINE = "Heat is embodied practitioner strain, not mana or stored magical fuel."


class PassageFixture(str, Enum):
    """Only the currently evidenced Episode 6 comparison cases.

    These names are test/runtime fixture identifiers, not universal magical
    configuration names. Unknown configurations must not inherit their effects.
    """

    MIRROR_AND_RING = "episode6_mirror_and_ring"
    MIRROR_ONLY = "episode6_mirror_only"
    EMBROIDERY_RING_OMITTED = "episode6_embroidery_ring_omitted"


@dataclass(frozen=True, slots=True)
class PassageFocusAssessment:
    known: bool
    fixture: PassageFixture | None = None
    carried_functions: Sequence[str] = field(default_factory=tuple)
    qualitative_strain: str | None = None
    observed_degradation: Sequence[str] = field(default_factory=tuple)
    release_behavior: Sequence[str] = field(default_factory=tuple)
    evidence: Sequence[Mapping[str, str]] = field(default_factory=tuple)
    do_not_infer: Sequence[str] = field(default_factory=tuple)


def assess_passage_focus_fixture(value: str | PassageFixture) -> PassageFocusAssessment:
    """Resolve only the played comparative Passage Focus evidence.

    This deliberately does not derive a universal omission table, numeric Heat
    cost, or arbitrary Focus substitution rule from the Episode 6 exercises.
    """
    try:
        fixture = value if isinstance(value, PassageFixture) else PassageFixture(value)
    except ValueError:
        return PassageFocusAssessment(
            known=False,
            do_not_infer=(
                "No universal Focus-omission rule is established from the Episode 6 fixtures.",
                "Do not invent numeric Heat costs or degradation for an untested configuration.",
            ),
        )

    common_evidence = (
        {
            "source": "Episode 6 Passage/Focus practice audit",
            "fact": "Helena-study exercises compare Florence's full/reduced Focus functions.",
        },
    )

    if fixture is PassageFixture.MIRROR_AND_RING:
        return PassageFocusAssessment(
            known=True,
            fixture=fixture,
            qualitative_strain="cleaner/cooler than the tested mirror-only configuration",
            evidence=common_evidence,
            do_not_infer=("No numeric Heat difference is established.",),
        )

    if fixture is PassageFixture.MIRROR_ONLY:
        return PassageFocusAssessment(
            known=True,
            fixture=fixture,
            carried_functions=("continuity/identity normally externalized by the ring",),
            qualitative_strain="more Heat than the tested mirror+ring configuration",
            evidence=common_evidence,
            do_not_infer=(
                "Do not convert this comparison into a universal penalty for every missing Focus.",
                "No numeric Heat cost is established.",
            ),
        )

    return PassageFocusAssessment(
        known=True,
        fixture=fixture,
        observed_degradation=("thread looped when the ring/continuity function was omitted",),
        release_behavior=("shears released the residual Working in the tested exercise",),
        evidence=common_evidence,
        do_not_infer=(
            "This observed loop/release behavior is specific evidence, not a universal omission rule.",
            "No numeric Heat cost is established.",
        ),
    )
