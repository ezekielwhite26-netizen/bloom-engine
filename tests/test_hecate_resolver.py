from bloom_engine.contracts.resolution import ResolutionStatus
from bloom_engine.hecate.models import FocusBond, MagicForm, MagicalCondition, MagicProfile
from bloom_engine.hecate.resolver import HecateResolver
from bloom_engine.hecate.store import InMemoryHecateStore
from bloom_engine.pantheon.protocol import CoreRequest, resolve_with_owner_guard


FLORENCE = "BLM-CHR-000001"
PASSAGE = "HEC-FORM-SIG-PASSAGE"


def evidence(fact: str):
    return ({"source": "HECATE fixture", "fact": fact},)


def make_store() -> InMemoryHecateStore:
    passage = MagicForm(
        key=PASSAGE,
        name="Passage",
        capability_statement="Open/use a genuine available passage without inventing an endpoint.",
        requirements=("a genuine available connection/endpoint must exist",),
        focus_roles=("relation/witness", "continuity/identity", "crossing/transition", "continuity carried through Working", "release/closure"),
        costs_or_strain=("Heat/embodied strain may increase when Florence carries missing Focus function",),
        hard_limits=("Passage cannot invent an endpoint",),
        resolver_readiness="READY",
        evidence=evidence("Passage form and hard endpoint limit are established"),
        do_not_infer=("exact numeric Heat cost is not established",),
    )
    profile = MagicProfile(
        key="HEC-PROFILE-FLORENCE",
        practitioner_ref=FLORENCE,
        form_keys=(PASSAGE,),
        capability_envelope="Passage plus a partially specified General Revelation faculty.",
        resolver_readiness="PARTIAL",
        evidence=evidence("Florence is an established Passage practitioner"),
        do_not_infer=("do not invent exact Heat thresholds",),
    )
    mirror = FocusBond(
        key="HEC-FOCUS-FLORENCE-MIRROR",
        practitioner_ref=FLORENCE,
        focus_name="antique folding mirror",
        is_focus=True,
        related_form_keys=(PASSAGE,),
        roles=("relation/witness",),
        object_ref="BLM-OBJ-000001",
        resolver_readiness="READY",
        evidence=evidence("mirror is an established Florence Focus"),
        do_not_infer=("Focus status does not prove current physical availability",),
    )
    hairpin = FocusBond(
        key="HEC-NONFOCUS-FLORENCE-LEAF-HAIRPIN",
        practitioner_ref=FLORENCE,
        focus_name="enchanted brass leaf hairpin",
        is_focus=False,
        related_form_keys=(),
        object_ref="BLM-OBJ-000005",
        resolver_readiness="READY",
        evidence=evidence("leaf hairpin is explicitly not a Focus"),
        do_not_infer=("enchantment does not promote an object to Focus",),
    )
    needle_minder = MagicalCondition(
        key="HEC-COND-OBJ-NEEDLE-MINDER-ENCHANTMENT",
        subject_ref="BLM-OBJ-000009",
        state="ACTIVE",
        effect_summary="The object is enchanted.",
        exact_behavior_known=False,
        evidence=evidence("needle minder is established as enchanted"),
        do_not_infer=("exact activation, range, cost, and behavior are unresolved",),
    )
    return InMemoryHecateStore(
        forms={PASSAGE: passage},
        profiles={FLORENCE: profile},
        focus_bonds={
            (FLORENCE, "antique folding mirror"): mirror,
            (FLORENCE, "enchanted brass leaf hairpin"): hairpin,
        },
        conditions={needle_minder.key: needle_minder},
    )


def test_hecate_status_surface_is_exhaustive():
    assert {status.value for status in ResolutionStatus} == {
        "KNOWN", "UNKNOWN", "BLOCKED", "NOT_APPLICABLE"
    }


def test_known_nonfocus_is_supported_negative_not_unknown():
    resolver = HecateResolver(make_store())
    result = resolve_with_owner_guard(
        resolver,
        CoreRequest(
            predicate="focus.is_focus",
            inputs={"practitioner_ref": FLORENCE, "focus_name": "enchanted brass leaf hairpin"},
        ),
    )
    assert result.status is ResolutionStatus.KNOWN
    assert result.value["is_focus"] is False
    assert result.evidence


def test_focus_status_does_not_invent_physical_availability():
    resolver = HecateResolver(make_store())
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


def test_passage_blocks_when_endpoint_is_known_absent():
    resolver = HecateResolver(make_store())
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
    assert result.value["eligible"] is False
    assert "Passage cannot invent a genuine connected endpoint" in result.blockers


def test_passage_endpoint_unknown_stays_unknown_and_routes_to_atlas():
    resolver = HecateResolver(make_store())
    result = resolve_with_owner_guard(
        resolver,
        CoreRequest(
            predicate="working.eligible",
            inputs={"practitioner_ref": FLORENCE, "form_key": PASSAGE},
        ),
    )
    assert result.status is ResolutionStatus.UNKNOWN
    assert "whether a genuine connected endpoint exists" in result.missing_required
    assert result.external_prerequisites == (
        {"owner": "ATLAS", "predicate": "access.connected_endpoint", "required_for": "Passage"},
    )


def test_needle_minder_behavior_is_unknown_not_invented():
    resolver = HecateResolver(make_store())
    result = resolve_with_owner_guard(
        resolver,
        CoreRequest(
            predicate="magical_condition.behavior",
            inputs={"condition_key": "HEC-COND-OBJ-NEEDLE-MINDER-ENCHANTMENT"},
        ),
    )
    assert result.status is ResolutionStatus.UNKNOWN
    assert result.evidence
    assert result.missing_required == ("exact magical behavior/mechanics",)


def test_ordinary_nonmagical_action_is_not_applicable():
    resolver = HecateResolver(make_store())
    result = resolve_with_owner_guard(
        resolver,
        CoreRequest(
            predicate="magic.applicable",
            inputs={"magical_question": False, "action": "ordinary sewing"},
        ),
    )
    assert result.status is ResolutionStatus.NOT_APPLICABLE
    assert result.value == {"applicable": False}


def test_missing_focus_record_stays_unknown_instead_of_becoming_false():
    resolver = HecateResolver(make_store())
    result = resolve_with_owner_guard(
        resolver,
        CoreRequest(
            predicate="focus.is_focus",
            inputs={"practitioner_ref": FLORENCE, "focus_name": "unrecorded object"},
        ),
    )
    assert result.status is ResolutionStatus.UNKNOWN
    assert "Focus Bond or explicit non-Focus evidence" in result.missing_required
