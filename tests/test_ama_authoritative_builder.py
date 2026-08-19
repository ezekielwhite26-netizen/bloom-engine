import pytest

from bloom_engine.api.authoritative_builder import CatalogAmaRequestBuilder, IntentBuildError
from bloom_engine.api.models import RuntimePreviewBody


def body(command: str, **kwargs):
    return RuntimePreviewBody(arc="ASTER_HOLLOW", command=command, **kwargs)


def test_passage_intent_builds_hecate_read_query_without_client_evidence():
    request = CatalogAmaRequestBuilder().build_preview(
        body(
            "can this actor perform passage here",
            requested_actor_ref="BLM-CHR-FLORENCE",
            requested_target_location_ref="BLM-LOC-HEARTH",
            requested_object_ref="BLM-OBJ-MIRROR",
        )
    )
    assert request.realization == "PREVIEW"
    assert request.authorization_token is None
    assert len(request.queries) == 1
    query = request.queries[0]
    assert query.request.predicate == "magic.passage_eligibility"
    assert query.request.subject_refs == ("BLM-CHR-FLORENCE",)
    assert query.request.evidence == ()
    assert query.request.permission_mode == "READ"
    assert query.required_for_request is True


def test_travel_intent_routes_to_atlas_prefix():
    request = CatalogAmaRequestBuilder().build_preview(
        body(
            "preview travel to target location",
            requested_actor_ref="BLM-CHR-FLORENCE",
            requested_target_location_ref="BLM-LOC-GREEN",
        )
    )
    assert request.queries[0].request.predicate == "travel.feasibility"


def test_object_intent_routes_to_hephaestus_prefix():
    request = CatalogAmaRequestBuilder().build_preview(
        body(
            "preview object use",
            requested_actor_ref="BLM-CHR-FLORENCE",
            requested_object_ref="BLM-OBJ-SHEARS",
        )
    )
    assert request.queries[0].request.predicate == "object.usability"


def test_unsupported_freeform_intent_fails_closed_instead_of_guessing_queries():
    with pytest.raises(IntentBuildError, match="unsupported or ambiguous"):
        CatalogAmaRequestBuilder().build_preview(body("continue the story however you think is best"))


def test_missing_required_stable_ref_fails_closed():
    with pytest.raises(IntentBuildError, match="requested_target_location_ref"):
        CatalogAmaRequestBuilder().build_preview(
            body("preview travel to target location", requested_actor_ref="BLM-CHR-FLORENCE")
        )


def test_external_live_play_mode_cannot_cross_preview_boundary():
    with pytest.raises(IntentBuildError, match="DRY_RUN only"):
        CatalogAmaRequestBuilder().build_preview(
            RuntimePreviewBody(
                arc="ASTER_HOLLOW",
                command="preview object use",
                mode="LIVE_PLAY",
                requested_actor_ref="BLM-CHR-FLORENCE",
                requested_object_ref="BLM-OBJ-SHEARS",
            )
        )
