from __future__ import annotations

import pytest

from bloom_engine.apollo.authority import ApolloVisualAuthorityCompiler
from bloom_engine.apollo.models import (
    CompiledVisualJob,
    RenderedVisual,
    VisualJobRequest,
    VisualReferenceAuthority,
    VisualRequestKind,
    VisualSubjectIdentity,
    VisualSubjectKind,
)
from bloom_engine.apollo.storage import AirtableVisualAssetStore


ARC = "Aster Hollow / At the Threshold"
AMARA = VisualSubjectIdentity(
    stable_id="BLM-CHR-000009",
    display_name="Amara Simone Bellamy",
    kind=VisualSubjectKind.CHARACTER,
    record_id="rec-amara",
)


def ref(role: str, *, uri: str | None = "https://example.test/reference.png", record_id: str | None = None):
    return VisualReferenceAuthority(
        asset_key=f"ASSET::{role}",
        asset_name=role,
        subject_name=AMARA.display_name,
        role=role,
        uri=uri,
        controls=(role,),
        does_not_control=("unsupported fields",),
        status="Approved Anchor",
        reference_strength="Gold Standard",
        record_id=record_id or f"rec-{role.lower().replace('_', '-')}",
        width=512,
        height=512,
    )


class Source:
    def __init__(self, refs):
        self.refs = tuple(refs)

    def resolve_subject(self, query, kind, arc):
        return AMARA

    def list_references(self, subject, arc):
        return self.refs

    def approved_slots(self, subject, arc):
        return ()


def request(output_type="left_profile"):
    return VisualJobRequest(
        arc=ARC,
        command=f"Plan {AMARA.display_name} {output_type}",
        subject_query=AMARA.display_name,
        subject_kind=VisualSubjectKind.CHARACTER,
        request_kind=VisualRequestKind.SINGLE_ASSET,
        output_type=output_type,
    )


def test_non_florence_character_receives_generic_production_pack():
    compiler = ApolloVisualAuthorityCompiler(Source([
        ref("FACE_GOLD"),
        ref("FRONT_BODY_GOLD"),
        ref("STYLE_GOLD"),
    ]))

    result = compiler.compile(request("left_profile"))

    assert result.subject.stable_id == AMARA.stable_id
    assert len(result.jobs) == 1
    assert result.jobs[0].ready is True
    assert result.jobs[0].output_type == "left_profile"
    assert result.jobs[0].subject_record_id == AMARA.record_id


def test_optional_character_reference_absence_does_not_block():
    compiler = ApolloVisualAuthorityCompiler(Source([
        ref("FACE_GOLD"),
        ref("FRONT_BODY_GOLD"),
        ref("STYLE_GOLD"),
    ]))

    result = compiler.compile(request("front_full_body"))

    assert result.jobs[0].ready is True
    assert not any(item.startswith("REFERENCE:REAR_HAIR_BODY_GOLD") for item in result.jobs[0].missing_dependencies)
    assert not any(item.startswith("REFERENCE:HAIR_GOLD") for item in result.jobs[0].missing_dependencies)


def test_style_gold_is_required_for_production_assets():
    compiler = ApolloVisualAuthorityCompiler(Source([
        ref("FACE_GOLD"),
        ref("FRONT_BODY_GOLD"),
    ]))

    result = compiler.compile(request("left_profile"))

    assert result.jobs[0].ready is False
    assert "REFERENCE:STYLE_GOLD" in result.jobs[0].missing_dependencies


def test_duplicate_authority_role_fails_closed():
    compiler = ApolloVisualAuthorityCompiler(Source([
        ref("FACE_GOLD", record_id="rec-face-a"),
        ref("FACE_GOLD", record_id="rec-face-b"),
        ref("FRONT_BODY_GOLD"),
        ref("STYLE_GOLD"),
    ]))

    with pytest.raises(ValueError, match="AMBIGUOUS_VISUAL_AUTHORITY_ROLE"):
        compiler.compile(request("left_profile"))


def test_same_asset_assigned_to_multiple_optional_roles_is_sent_once():
    shared = "rec-shared-hair"
    compiler = ApolloVisualAuthorityCompiler(Source([
        ref("FACE_GOLD"),
        ref("FRONT_BODY_GOLD"),
        ref("STYLE_GOLD"),
        ref("HAIR_GOLD", record_id=shared),
        ref("REAR_HAIR_BODY_GOLD", record_id=shared),
    ]))

    result = compiler.compile(request("left_profile"))

    record_ids = [item.record_id for item in result.jobs[0].references]
    assert record_ids.count(shared) == 1


def test_airtable_candidate_write_requires_stable_subject_record_link():
    job = CompiledVisualJob(
        job_key="TEST::JOB",
        arc=ARC,
        subject_id=AMARA.stable_id,
        subject_name=AMARA.display_name,
        subject_kind=VisualSubjectKind.CHARACTER,
        output_type="left_profile",
        prompt="test",
        references=(ref("FACE_GOLD"),),
        hard_gates=("identity",),
        soft_criteria=(),
        style_rules=(),
        anti_drift=(),
        open_fields=(),
        max_iterations=1,
        subject_record_id="",
    )
    rendered = RenderedVisual(
        provider_id="test",
        model="test-model",
        mime_type="image/png",
        temporary_url="https://example.test/candidate.png",
    )
    store = AirtableVisualAssetStore(base_id="appNhl43NzKfbsTAw", token="unused")

    with pytest.raises(RuntimeError, match="MISSING_STABLE_SUBJECT_RECORD_LINK"):
        store.persist_generated(job, rendered, iteration=1)
