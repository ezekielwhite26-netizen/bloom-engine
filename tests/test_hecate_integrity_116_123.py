from bloom_engine.contracts.resolution import ResolutionStatus
from bloom_engine.hecate.integrity_catalog import HECATE_INTEGRITY_TESTS
from bloom_engine.hecate.models import FocusBond, MagicForm, MagicProfile
from bloom_engine.hecate.resolver import HecateResolver
from bloom_engine.hecate.store import InMemoryHecateStore
from bloom_engine.hecate.working_rules import (
    FOCUS_DOCTRINE,
    HEAT_DOCTRINE,
    PassageFixture,
    assess_passage_focus_fixture,
)
from bloom_engine.pantheon.invariants import assert_resolution_semantics
from bloom_engine.pantheon.protocol import CoreRequest, resolve_with_owner_guard


FLORENCE = "BLM-CHR-000001"
JOSEPHINE = "BLM-CHR-000005"
PASSAGE = "HEC-FORM-SIG-PASSAGE"


def evidence(fact: str):
    return ({"source": "HECATE authoritative fixture", "fact": fact},)


def bond(key, practitioner, name, is_focus, object_ref, roles=()):
    return FocusBond(
        key=key,
        practitioner_ref=practitioner,
        focus_name=name,
        is_focus=is_focus,
        related_form_keys=(PASSAGE,) if practitioner == FLORENCE and is_focus else (),
        roles=roles,
        object_ref=object_ref,
        resolver_readiness="READY",
        evidence=evidence(f"{name} Focus classification is established"),
        do_not_infer=("classification does not prove physical availability",),
    )


def store_for_integrity() -> InMemoryHecateStore:
    form = MagicForm(
        key=PASSAGE,
        name="Passage",
        capability_statement="Works the transition between genuinely connected states.",
        requirements=("a genuine connected endpoint must already exist",),
        focus_roles=(
            "mirror: relation/witness",
            "ring: continuity/identity",
            "needle: crossing/transition",
            "thread: continuity carried through the Working",
            "shears: release/closure",
        ),
        costs_or_strain=(HEAT_DOCTRINE,),
        hard_limits=("Passage cannot invent an endpoint",),
        clearing_requirements=("release/clearing remains required",),
        resolver_readiness="READY",
        evidence=evidence("Passage and its endpoint limit are established"),
        do_not_infer=("no universal numeric Heat cost is established",),
    )
    profile = MagicProfile(
        key="HEC-PROF-FLORENCE-MACKELLAR",
        practitioner_ref=FLORENCE,
        form_keys=(PASSAGE,),
        capability_envelope="Passage practitioner.",
        resolver_readiness="PARTIAL",
        evidence=evidence("Florence is an established Passage practitioner"),
    )
    bonds = [
        bond("HEC-FOCUS-FLORENCE-MIRROR", FLORENCE, "antique folding mirror", True, "BLM-OBJ-000001", ("relation/witness",)),
        bond("HEC-NONFOCUS-FLORENCE-LEAF-HAIRPIN", FLORENCE, "enchanted brass leaf hairpin", False, "BLM-OBJ-000005"),
        bond("HEC-NONFOCUS-FLORENCE-NEEDLE-MINDER", FLORENCE, "enchanted needle minder", False, "BLM-OBJ-000009"),
        bond("HEC-NONFOCUS-FLORENCE-THREAD-WINDER", FLORENCE, "mother-of-pearl thread winder", False, "BLM-OBJ-000008"),
        bond("HEC-NONFOCUS-FLORENCE-ROUTE-SAMPLE", FLORENCE, "route-structure embroidery sample", False, "BLM-OBJ-000011"),
        bond("HEC-NONFOCUS-JOSEPHINE-DRIFTING-LIGHT-PENDANT", JOSEPHINE, "drifting-light pendant", False, "BLM-OBJ-000013"),
    ]
    return InMemoryHecateStore(
        forms={PASSAGE: form},
        profiles={FLORENCE: profile},
        focus_bonds={(b.practitioner_ref, b.focus_name): b for b in bonds},
    )


def test_116_exact_catalog_and_status_surface():
    assert tuple(spec.stable_id for spec in HECATE_INTEGRITY_TESTS) == tuple(
        f"BLM-TST-{number:06d}" for number in range(116, 124)
    )
    assert {status.value for status in ResolutionStatus} == {
        "KNOWN", "UNKNOWN", "BLOCKED", "NOT_APPLICABLE"
    }


def test_117_evidence_and_missing_reason_semantics():
    resolver = HecateResolver(store_for_integrity())

    blocked = resolve_with_owner_guard(
        resolver,
        CoreRequest(
            predicate="working.eligible",
            inputs={
                "practitioner_ref": FLORENCE,
                "form_key": PASSAGE,
                "genuine_connected_endpoint": False,
            },
        ),
    )
    assert_resolution_semantics(blocked)
    assert blocked.status is ResolutionStatus.BLOCKED and blocked.evidence

    unknown = resolve_with_owner_guard(
        resolver,
        CoreRequest(
            predicate="focus.is_focus",
            inputs={"practitioner_ref": FLORENCE, "focus_name": "unrecorded object"},
            evidence=evidence("Focus Bonds were checked and no exact record matched"),
        ),
    )
    assert_resolution_semantics(unknown)
    assert unknown.status is ResolutionStatus.UNKNOWN
    assert unknown.evidence and unknown.missing_required

    not_applicable = resolve_with_owner_guard(
        resolver,
        CoreRequest(predicate="magic.applicable", inputs={"magical_question": False}),
    )
    assert_resolution_semantics(not_applicable)
    assert not_applicable.status is ResolutionStatus.NOT_APPLICABLE
    assert not_applicable.metadata["reason"]


def test_118_passage_cannot_invent_endpoint():
    resolver = HecateResolver(store_for_integrity())
    result = resolve_with_owner_guard(
        resolver,
        CoreRequest(
            predicate="working.eligible",
            inputs={
                "practitioner_ref": FLORENCE,
                "form_key": PASSAGE,
                "genuine_connected_endpoint": False,
            },
        ),
    )
    assert result.status is ResolutionStatus.BLOCKED
    assert "Passage cannot invent a genuine connected endpoint" in result.blockers


def test_119_focus_is_function_not_battery_and_heat_is_not_mana():
    assert "externalizes" in FOCUS_DOCTRINE
    assert "not a generic power battery" in FOCUS_DOCTRINE
    assert "embodied practitioner strain" in HEAT_DOCTRINE
    assert "not mana" in HEAT_DOCTRINE
    form = store_for_integrity().get_form(PASSAGE)
    assert form is not None
    assert any("not mana" in item for item in form.costs_or_strain)
    assert not any("stored power" in role.casefold() for role in form.focus_roles)


def test_120_all_five_explicit_nonfoci_remain_supported_negatives():
    resolver = HecateResolver(store_for_integrity())
    cases = (
        (FLORENCE, "enchanted brass leaf hairpin"),
        (FLORENCE, "enchanted needle minder"),
        (FLORENCE, "mother-of-pearl thread winder"),
        (FLORENCE, "route-structure embroidery sample"),
        (JOSEPHINE, "drifting-light pendant"),
    )
    for practitioner, focus_name in cases:
        result = resolve_with_owner_guard(
            resolver,
            CoreRequest(
                predicate="focus.is_focus",
                inputs={"practitioner_ref": practitioner, "focus_name": focus_name},
            ),
        )
        assert result.status is ResolutionStatus.KNOWN
        assert result.value["is_focus"] is False
        assert result.evidence


def test_121_physical_availability_is_externalized_to_hephaestus():
    resolver = HecateResolver(store_for_integrity())
    result = resolve_with_owner_guard(
        resolver,
        CoreRequest(
            predicate="focus.is_focus",
            inputs={"practitioner_ref": FLORENCE, "focus_name": "antique folding mirror"},
        ),
    )
    assert result.status is ResolutionStatus.KNOWN
    assert result.value["is_focus"] is True
    assert result.external_prerequisites == (
        {"owner": "HEPHAESTUS", "predicate": "object.available", "subject_ref": "BLM-OBJ-000001"},
    )
    assert "available" not in result.value


def test_122_ordinary_actions_are_not_magicalized():
    resolver = HecateResolver(store_for_integrity())
    for action in ("ordinary sewing", "walking", "carrying", "opening a door", "grooming", "eating"):
        result = resolve_with_owner_guard(
            resolver,
            CoreRequest(
                predicate="magic.applicable",
                inputs={"magical_question": False, "action": action},
            ),
        )
        assert result.status is ResolutionStatus.NOT_APPLICABLE
        assert result.metadata["reason"]


def test_123_episode6_focus_degradation_stays_specific_and_qualitative():
    full = assess_passage_focus_fixture(PassageFixture.MIRROR_AND_RING)
    reduced = assess_passage_focus_fixture(PassageFixture.MIRROR_ONLY)
    embroidery = assess_passage_focus_fixture(PassageFixture.EMBROIDERY_RING_OMITTED)
    untested = assess_passage_focus_fixture("untested_configuration")

    assert full.known and "cleaner/cooler" in full.qualitative_strain
    assert reduced.known
    assert reduced.carried_functions == ("continuity/identity normally externalized by the ring",)
    assert "more Heat" in reduced.qualitative_strain
    assert embroidery.known
    assert any("thread looped" in item for item in embroidery.observed_degradation)
    assert any("shears released" in item for item in embroidery.release_behavior)
    assert untested.known is False

    all_text = " ".join(
        [
            *(full.do_not_infer or ()),
            *(reduced.do_not_infer or ()),
            *(embroidery.do_not_infer or ()),
            *(untested.do_not_infer or ()),
        ]
    )
    assert "numeric Heat" in all_text
    assert "universal" in all_text
