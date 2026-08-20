from __future__ import annotations

from bloom_engine.apollo.models import VisualPackDefinition, VisualPackJobDefinition


FLORENCE_ID = "BLM-CHR-000001"

FLORENCE_STYLE_RULES = (
    "STYLE_GOLD controls rendering medium and presentation, never Florence's identity anatomy",
    "preserve real human individuality and age-specific anatomy",
    "restrained illustrated readability rather than generic anime anatomy",
    "cinematic natural lighting and tactile material specificity",
)

FLORENCE_ANTI_DRIFT = (
    "do not shorten or thin Florence's extraordinary hair",
    "do not shift the hair to generic bright orange",
    "do not adultify face, makeup, body, pose, or expression",
    "do not replace Florence's face geometry with a generic style face",
    "do not introduce pointed ears, wings, or default fantasy-princess styling",
    "do not introduce post-2009 technology or styling",
)

GENERIC_STYLE_RULES = (
    "STYLE_GOLD controls rendering medium and presentation only",
    "identity/body/hair Gold overrides style if a style reference changes the subject",
    "preserve individual age, ethnicity, facial architecture, body type, hair, and asymmetry",
    "use grounded 2009 Aster Hollow presentation unless a more specific approved authority says otherwise",
)

GENERIC_ANTI_DRIFT = (
    "do not normalize the subject toward a generic attractive face or body",
    "do not alter apparent age",
    "do not copy another cast member's face, body, hair, wardrobe, or signature silhouette",
    "do not invent supernatural anatomy or effects unless separately authoritative",
    "do not introduce post-2009 technology or styling",
)

SOFT = (
    "production readability",
    "material richness",
    "observational naturalism",
    "Aster Hollow style fit",
)

OPEN = (
    "one-off clothing choice unless separately approved",
    "background unless separately specified",
    "incidental pose/expression unless the slot specifically controls it",
)


def _job(
    output_type: str,
    priority: int,
    refs: tuple[str, ...],
    prompt: str,
    gates: tuple[str, ...],
    deps: tuple[str, ...] = (),
    optional_refs: tuple[str, ...] = (),
    *,
    style_rules: tuple[str, ...] = FLORENCE_STYLE_RULES,
    anti_drift: tuple[str, ...] = FLORENCE_ANTI_DRIFT,
) -> VisualPackJobDefinition:
    return VisualPackJobDefinition(
        output_type=output_type,
        priority=priority,
        required_reference_roles=refs,
        optional_reference_roles=optional_refs,
        prompt=prompt,
        hard_gates=gates,
        approved_dependencies=deps,
        soft_criteria=SOFT,
        style_rules=style_rules,
        anti_drift=anti_drift,
        open_fields=OPEN,
    )


# Florence stays specialized because her extraordinary hair architecture is itself
# a production-critical identity feature and therefore intentionally hard-blocks
# several views when the rear-hair authority is absent.
FLORENCE_PRODUCTION_PACK = VisualPackDefinition(
    key="AH-FLO-PROD-PACK-v0.2",
    subject_id=FLORENCE_ID,
    jobs=(
        _job(
            "neutral_face_closeup", 1, ("FACE_GOLD", "STYLE_GOLD"),
            "Neutral Florence face close-up in diffuse natural daylight; minimal expression; no dramatic makeup or supernatural effect.",
            ("same recognizable Florence face as FACE_GOLD", "reads as sixteen", "eyes/freckles/complexion remain consistent with FACE_GOLD", "no beauty-filter sameface drift"),
            optional_refs=("HAIR_GOLD", "WARDROBE_GOLD"),
        ),
        _job(
            "front_full_body", 1, ("FACE_GOLD", "FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD", "STYLE_GOLD"),
            "Neutral front full-body calibration view of Florence, proportion-neutral perspective, ordinary 2009 clothing, full hair visible.",
            ("same Florence identity", "front body proportions match Gold", "canonical extraordinary hair length and mass preserved", "reads as sixteen", "no proportion-changing lens distortion"),
            optional_refs=("HAIR_GOLD", "WARDROBE_GOLD"),
        ),
        _job(
            "rear_full_body", 1, ("FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD", "STYLE_GOLD"),
            "Neutral rear full-body calibration view proving Florence's canonical hair abundance, integrated braids, full length, and rear proportions.",
            ("rear hair architecture matches Gold", "hair remains conspicuously well past hips", "rear body proportions remain consistent", "no invented outfit detail becomes identity authority"),
            optional_refs=("FACE_GOLD", "HAIR_GOLD", "WARDROBE_GOLD"),
        ),
        _job(
            "body_unobscured_by_hair", 1, ("FACE_GOLD", "FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD", "STYLE_GOLD"),
            "Front full-body Florence with canonical hair gently positioned aside enough to read body proportions; never cut, shorten, thin, or redesign the hair.",
            ("body remains consistent with Gold", "hair is repositioned rather than reduced", "identity and age preserved", "no generated measurement becomes canon"),
            optional_refs=("HAIR_GOLD", "WARDROBE_GOLD"),
        ),
        _job(
            "hair_rear", 1, ("REAR_HAIR_BODY_GOLD", "STYLE_GOLD"),
            "Rear Florence hair-construction reference with the full canonical mass, braids, and length visible from crown to ends.",
            ("rear hair architecture matches Gold", "full length clearly visible", "no thinning", "no bright-orange drift"),
            optional_refs=("FACE_GOLD", "HAIR_GOLD"),
        ),
        _job(
            "left_profile", 2, ("FACE_GOLD", "FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD", "STYLE_GOLD"),
            "Left-profile full-body Florence calibration view, neutral posture and natural daylight.",
            ("profile remains recognizable as Florence", "nose/jaw architecture remains consistent with FACE_GOLD", "reads as sixteen", "canonical hair length and mass preserved"),
            optional_refs=("HAIR_GOLD", "WARDROBE_GOLD"),
        ),
        _job(
            "right_profile", 2, ("FACE_GOLD", "FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD", "STYLE_GOLD"),
            "Right-profile full-body Florence calibration view, neutral posture and natural daylight.",
            ("profile remains recognizable as Florence", "nose/jaw architecture remains consistent with FACE_GOLD", "reads as sixteen", "canonical hair length and mass preserved"),
            optional_refs=("HAIR_GOLD", "WARDROBE_GOLD"),
        ),
        _job(
            "front_three_quarter", 2, ("FACE_GOLD", "FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD", "STYLE_GOLD"),
            "Front three-quarter Florence calibration view, relaxed neutral stance, ordinary 2009 styling.",
            ("same Florence identity", "reads as sixteen", "body proportions preserved", "hair silhouette preserved"),
            optional_refs=("HAIR_GOLD", "WARDROBE_GOLD"),
        ),
        _job(
            "rear_three_quarter", 2, ("FACE_GOLD", "FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD", "STYLE_GOLD"),
            "Rear three-quarter Florence calibration view showing back hair construction and enough face to verify identity.",
            ("rear hair remains canonical", "body proportions preserved", "visible facial structure remains Florence", "reads as sixteen"),
            optional_refs=("HAIR_GOLD", "WARDROBE_GOLD"),
        ),
        _job(
            "hair_front", 2, ("FACE_GOLD", "REAR_HAIR_BODY_GOLD", "STYLE_GOLD"),
            "Florence hair-construction reference from the front, neutral pose, canonical hair fully visible and uncompressed.",
            ("canonical deep copper/wine-auburn family", "extraordinary abundance", "fine integrated braids", "canonical length"),
            optional_refs=("FRONT_BODY_GOLD", "HAIR_GOLD"),
        ),
        _job(
            "hair_side", 2, ("FACE_GOLD", "REAR_HAIR_BODY_GOLD", "STYLE_GOLD"),
            "Side Florence hair-construction reference, full length visible with natural gravity and profile identity preserved.",
            ("canonical length and volume", "integrated braid logic", "profile remains Florence"),
            optional_refs=("FRONT_BODY_GOLD", "HAIR_GOLD"),
        ),
        _job(
            "transparent_production_master", 3, ("FACE_GOLD", "FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD", "STYLE_GOLD"),
            "Neutral transparent-background Florence production master; full body and hair entirely inside frame; ordinary baseline 2009 outfit; no unnecessary props.",
            ("same Florence identity", "reads as sixteen", "body and hair match approved calibration views", "entire body and hair inside canvas", "transparent production-ready background"),
            ("neutral_face_closeup", "front_full_body", "rear_full_body", "front_three_quarter", "hair_rear"),
            optional_refs=("HAIR_GOLD", "WARDROBE_GOLD"),
        ),
    ),
)


def generic_character_production_pack(subject_id: str) -> VisualPackDefinition:
    """Reusable human-character production coverage.

    Subject-specific Gold determines identity. Optional hair/rear/wardrobe anchors
    are consumed when curated, but their absence does not cause APOLLO to invent
    them as canon. STYLE_GOLD is required because production assets should not
    silently choose a new rendering medium.
    """

    def g(
        output_type: str,
        priority: int,
        required: tuple[str, ...],
        prompt: str,
        gates: tuple[str, ...],
        deps: tuple[str, ...] = (),
        optional: tuple[str, ...] = (),
    ) -> VisualPackJobDefinition:
        return _job(
            output_type,
            priority,
            required,
            prompt,
            gates,
            deps,
            optional,
            style_rules=GENERIC_STYLE_RULES,
            anti_drift=GENERIC_ANTI_DRIFT,
        )

    optional_identity = ("REAR_HAIR_BODY_GOLD", "HAIR_GOLD", "WARDROBE_GOLD")
    return VisualPackDefinition(
        key=f"AH-CHAR-PROD-PACK-v0.1::{subject_id}",
        subject_id=subject_id,
        jobs=(
            g("neutral_face_closeup", 1, ("FACE_GOLD", "STYLE_GOLD"), "Neutral face identity calibration close-up in diffuse natural daylight.", ("recognizably the same subject as FACE_GOLD", "apparent age preserved", "individual facial architecture preserved"), optional=optional_identity),
            g("front_full_body", 1, ("FACE_GOLD", "FRONT_BODY_GOLD", "STYLE_GOLD"), "Neutral front full-body calibration view with proportion-neutral perspective and grounded 2009 presentation.", ("same subject identity", "body proportion family matches FRONT_BODY_GOLD", "apparent age preserved"), optional=optional_identity),
            g("rear_full_body", 1, ("FRONT_BODY_GOLD", "STYLE_GOLD"), "Neutral rear full-body calibration view; preserve all established hair/body information without inventing new authority.", ("body proportion family remains consistent", "hair visible in supplied authorities is not normalized or redesigned"), optional=("FACE_GOLD",) + optional_identity),
            g("left_profile", 2, ("FACE_GOLD", "FRONT_BODY_GOLD", "STYLE_GOLD"), "Neutral left-profile full-body calibration view.", ("profile remains recognizably the same subject", "body proportion family preserved", "apparent age preserved"), optional=optional_identity),
            g("right_profile", 2, ("FACE_GOLD", "FRONT_BODY_GOLD", "STYLE_GOLD"), "Neutral right-profile full-body calibration view.", ("profile remains recognizably the same subject", "body proportion family preserved", "apparent age preserved"), optional=optional_identity),
            g("front_three_quarter", 2, ("FACE_GOLD", "FRONT_BODY_GOLD", "STYLE_GOLD"), "Neutral front three-quarter production calibration view.", ("same subject identity", "body proportion family preserved", "no sameface normalization"), optional=optional_identity),
            g("rear_three_quarter", 2, ("FACE_GOLD", "FRONT_BODY_GOLD", "STYLE_GOLD"), "Neutral rear three-quarter production calibration view.", ("same subject identity where face is visible", "body and hair remain consistent with supplied authority"), optional=optional_identity),
            g("hair_front", 2, ("FACE_GOLD", "STYLE_GOLD"), "Front hair-construction reference preserving the subject's established hair identity.", ("hair color/texture/architecture follow supplied Gold", "face remains same subject"), optional=("FRONT_BODY_GOLD", "HAIR_GOLD", "REAR_HAIR_BODY_GOLD")),
            g("hair_rear", 2, ("STYLE_GOLD",), "Rear hair-construction reference preserving all established hair information and leaving unsupported specifics non-canonical.", ("hair is not normalized toward another cast member",), optional=("FACE_GOLD", "FRONT_BODY_GOLD", "HAIR_GOLD", "REAR_HAIR_BODY_GOLD")),
            g("hair_side", 2, ("FACE_GOLD", "STYLE_GOLD"), "Side hair-construction reference with natural gravity and stable identity.", ("hair follows supplied Gold", "profile remains same subject"), optional=("FRONT_BODY_GOLD", "HAIR_GOLD", "REAR_HAIR_BODY_GOLD")),
            g("transparent_production_master", 3, ("FACE_GOLD", "FRONT_BODY_GOLD", "STYLE_GOLD"), "Neutral transparent-background production master with the entire subject inside frame and no unnecessary props.", ("same subject identity", "body matches approved calibration", "entire silhouette inside canvas", "transparent production-ready background"), ("neutral_face_closeup", "front_full_body", "rear_full_body", "front_three_quarter"), optional=optional_identity),
        ),
    )


PACKS_BY_SUBJECT = {FLORENCE_PRODUCTION_PACK.subject_id: FLORENCE_PRODUCTION_PACK}
