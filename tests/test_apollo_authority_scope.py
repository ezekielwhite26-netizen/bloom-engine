from bloom_engine.apollo.authority import ASSET_F, AirtableVisualAuthoritySource, _arc_matches
from bloom_engine.apollo.models import VisualSubjectIdentity, VisualSubjectKind


SUBJECT = VisualSubjectIdentity(
    stable_id="BLM-CHR-000001",
    display_name="Florence Maeve MacKellar",
    kind=VisualSubjectKind.CHARACTER,
    record_id="recM6kgdzsBGvPaH8",
)


def test_arc_scope_matches_explicit_parent_path():
    assert _arc_matches("Aster Hollow", "Aster Hollow / At the Threshold") is True
    assert _arc_matches("Aster Hollow", "Aster Hollow / At the Threshold / Episode 1") is True


def test_arc_scope_is_not_fuzzy_prefix_matching():
    assert _arc_matches("Aster Hollow", "Aster Hollowness / Other") is False
    assert _arc_matches("Aster Hollow", "Dawnspire / Aster Hollow") is False


def test_arc_scoped_style_gold_applies_to_child_arc():
    fields = {
        ASSET_F["authority_scope"]: {"name": "ARC"},
        ASSET_F["arc"]: "Aster Hollow",
        ASSET_F["subjects"]: "Aster Hollow production rendering system; Florence exemplar only",
    }
    assert AirtableVisualAuthoritySource._asset_in_authority_scope(
        fields,
        SUBJECT,
        "Aster Hollow / At the Threshold",
    ) is True


def test_subject_scope_still_requires_the_subject():
    fields = {
        ASSET_F["authority_scope"]: {"name": "SUBJECT"},
        ASSET_F["arc"]: "Aster Hollow",
        ASSET_F["subjects"]: "Somebody Else",
    }
    assert AirtableVisualAuthoritySource._asset_in_authority_scope(
        fields,
        SUBJECT,
        "Aster Hollow / At the Threshold",
    ) is False
