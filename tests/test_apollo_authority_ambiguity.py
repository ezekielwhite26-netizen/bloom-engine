from __future__ import annotations

import pytest

from bloom_engine.apollo.authority import ApolloVisualAuthorityCompiler
from bloom_engine.apollo.models import (
    VisualJobRequest,
    VisualPackDefinition,
    VisualPackJobDefinition,
    VisualReferenceAuthority,
    VisualRequestKind,
    VisualSubjectIdentity,
    VisualSubjectKind,
)


ARC = "Aster Hollow / At the Threshold"
SUBJECT = VisualSubjectIdentity(
    stable_id="BLM-CHR-000003",
    display_name="Amara Simone Bellamy",
    kind=VisualSubjectKind.CHARACTER,
    record_id="rec-amara",
)


def ref(role: str, suffix: str) -> VisualReferenceAuthority:
    return VisualReferenceAuthority(
        asset_key=f"ASSET-{role}-{suffix}",
        asset_name=f"{role} {suffix}",
        subject_name=SUBJECT.display_name,
        role=role,
        uri=f"https://example.test/{role}-{suffix}.png",
        controls=(role,),
        does_not_control=(),
        status="Approved Anchor",
        reference_strength="Gold Standard",
        record_id=f"rec-{role}-{suffix}",
    )


PACK = VisualPackDefinition(
    key="TEST-PACK",
    subject_id=SUBJECT.stable_id,
    jobs=(
        VisualPackJobDefinition(
            output_type="portrait",
            priority=1,
            prompt="portrait",
            required_reference_roles=("FACE_GOLD", "STYLE_GOLD"),
            hard_gates=("identity",),
        ),
    ),
)


class Source:
    def __init__(self, refs):
        self.refs = tuple(refs)

    def resolve_subject(self, query, kind, arc):
        return SUBJECT

    def list_references(self, subject, arc):
        return self.refs

    def approved_slots(self, subject, arc):
        return ()


def request() -> VisualJobRequest:
    return VisualJobRequest(
        arc=ARC,
        command="plan portrait",
        subject_query=SUBJECT.display_name,
        subject_kind=VisualSubjectKind.CHARACTER,
        request_kind=VisualRequestKind.SINGLE_ASSET,
        output_type="portrait",
    )


def test_duplicate_unused_secondary_roles_do_not_block_production_authority():
    compiler = ApolloVisualAuthorityCompiler(
        Source((
            ref("FACE_GOLD", "1"),
            ref("STYLE_GOLD", "1"),
            ref("APPROVED_SECONDARY", "1"),
            ref("APPROVED_SECONDARY", "2"),
        )),
        {SUBJECT.stable_id: PACK},
    )

    result = compiler.compile(request())

    assert result.jobs[0].ready is True
    assert {reference.role for reference in result.jobs[0].references} == {"FACE_GOLD", "STYLE_GOLD"}


def test_duplicate_consumed_gold_role_fails_closed():
    compiler = ApolloVisualAuthorityCompiler(
        Source((
            ref("FACE_GOLD", "1"),
            ref("FACE_GOLD", "2"),
            ref("STYLE_GOLD", "1"),
        )),
        {SUBJECT.stable_id: PACK},
    )

    with pytest.raises(ValueError, match="AMBIGUOUS_VISUAL_AUTHORITY_ROLE"):
        compiler.compile(request())
