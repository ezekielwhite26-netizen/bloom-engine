from __future__ import annotations

from bloom_engine.apollo.models import VisualPackDefinition, VisualPackJobDefinition


FLORENCE_ID = "BLM-CHR-000001"

STYLE_RULES = (
    "Aster Hollow Illustrated Realism",
    "preserve real human individuality and age-specific anatomy",
    "restrained light-novel readability rather than generic anime anatomy",
    "graphite/gouache/watercolor physicality with cinematic natural lighting",
    "tactile, materially specific clothing and environments",
)

ANTI_DRIFT = (
    "do not shorten or thin Florence's extraordinary hair",
    "do not shift the hair to generic bright orange",
    "do not adultify face, makeup, body, pose, or expression",
    "do not replace Florence's face geometry with a generic style face",
    "do not introduce pointed ears, wings, or default fantasy-princess styling",
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
)


def _job(
    output_type: str,
    priority: int,
    refs: tuple[str, ...],
    prompt: str,
    gates: tuple[str, ...],
    deps: tuple[str, ...] = (),
) -> VisualPackJobDefinition:
    return VisualPackJobDefinition(
        output_type=output_type,
        priority=priority,
        required_reference_roles=refs,
        prompt=prompt,
        hard_gates=gates,
        approved_dependencies=deps,
        soft_criteria=SOFT,
        style_rules=STYLE_RULES,
        anti_drift=ANTI_DRIFT,
        open_fields=OPEN,
    )


FLORENCE_PRODUCTION_PACK = VisualPackDefinition(
    key="AH-FLO-PROD-PACK-v0.1",
    subject_id=FLORENCE_ID,
    jobs=(
        _job(
            "neutral_face_closeup", 1, ("FACE_GOLD",),
            "Neutral Florence face close-up in diffuse natural daylight; minimal expression; no dramatic makeup or supernatural effect.",
            ("same recognizable Florence face as FACE_GOLD", "reads as sixteen", "eyes/freckles/complexion remain consistent with FACE_GOLD", "no beauty-filter sameface drift"),
        ),
        _job(
            "front_full_body", 1, ("FACE_GOLD", "FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD"),
            "Neutral front full-body calibration view of Florence, proportion-neutral perspective, ordinary 2009 clothing, full hair visible.",
            ("same Florence identity", "front body proportions match Gold", "canonical extraordinary hair length and mass preserved", "reads as sixteen", "no proportion-changing lens distortion"),
        ),
        _job(
            "rear_full_body", 1, ("FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD"),
            "Neutral rear full-body calibration view proving Florence's canonical hair abundance, integrated braids, full length, and rear proportions.",
            ("rear hair architecture matches Gold", "hair remains conspicuously well past hips", "rear body proportions remain consistent", "no invented outfit detail becomes identity authority"),
        ),
        _job(
            "body_unobscured_by_hair", 1, ("FACE_GOLD", "FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD"),
            "Front full-body Florence with canonical hair gently positioned aside enough to read body proportions; never cut, shorten, thin, or redesign the hair.",
            ("body remains consistent with Gold", "hair is repositioned rather than reduced", "identity and age preserved", "no generated measurement becomes canon"),
        ),
        _job(
            "hair_rear", 1, ("REAR_HAIR_BODY_GOLD",),
            "Rear Florence hair-construction reference with the full canonical mass, braids, and length visible from crown to ends.",
            ("rear hair architecture matches Gold", "full length clearly visible", "no thinning", "no bright-orange drift"),
        ),
        _job(
            "left_profile", 2, ("FACE_GOLD", "FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD"),
            "Left-profile full-body Florence calibration view, neutral posture and natural daylight.",
            ("profile remains recognizable as Florence", "nose/jaw architecture remains consistent with FACE_GOLD", "reads as sixteen", "canonical hair length and mass preserved"),
        ),
        _job(
            "right_profile", 2, ("FACE_GOLD", "FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD"),
            "Right-profile full-body Florence calibration view, neutral posture and natural daylight.",
            ("profile remains recognizable as Florence", "nose/jaw architecture remains consistent with FACE_GOLD", "reads as sixteen", "canonical hair length and mass preserved"),
        ),
        _job(
            "front_three_quarter", 2, ("FACE_GOLD", "FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD"),
            "Front three-quarter Florence calibration view, relaxed neutral stance, ordinary 2009 styling.",
            ("same Florence identity", "reads as sixteen", "body proportions preserved", "hair silhouette preserved"),
        ),
        _job(
            "rear_three_quarter", 2, ("FACE_GOLD", "FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD"),
            "Rear three-quarter Florence calibration view showing back hair construction and enough face to verify identity.",
            ("rear hair remains canonical", "body proportions preserved", "visible facial structure remains Florence", "reads as sixteen"),
        ),
        _job(
            "hair_front", 2, ("FACE_GOLD", "FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD"),
            "Florence hair-construction reference from the front, neutral pose, canonical hair fully visible and uncompressed.",
            ("canonical deep copper/wine-auburn family", "extraordinary abundance", "fine integrated braids", "canonical length"),
        ),
        _job(
            "hair_side", 2, ("FACE_GOLD", "REAR_HAIR_BODY_GOLD"),
            "Side Florence hair-construction reference, full length visible with natural gravity and profile identity preserved.",
            ("canonical length and volume", "integrated braid logic", "profile remains Florence"),
        ),
        _job(
            "transparent_production_master", 3, ("FACE_GOLD", "FRONT_BODY_GOLD", "REAR_HAIR_BODY_GOLD"),
            "Neutral transparent-background Florence production master; full body and hair entirely inside frame; ordinary baseline 2009 outfit; no unnecessary props.",
            ("same Florence identity", "reads as sixteen", "body and hair match approved calibration views", "entire body and hair inside canvas", "transparent production-ready background"),
            ("neutral_face_closeup", "front_full_body", "rear_full_body", "front_three_quarter", "hair_rear"),
        ),
    ),
)

PACKS_BY_SUBJECT = {FLORENCE_PRODUCTION_PACK.subject_id: FLORENCE_PRODUCTION_PACK}
