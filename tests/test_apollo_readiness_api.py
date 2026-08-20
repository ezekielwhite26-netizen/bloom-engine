from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

import bloom_engine.apollo.api as visual_api
import bloom_engine.app as preview_app
from bloom_engine.apollo.models import (
    CompiledVisualJob,
    CompiledVisualRequest,
    VisualReferenceAuthority,
    VisualSubjectIdentity,
    VisualSubjectKind,
)


SUBJECT = VisualSubjectIdentity(
    stable_id="BLM-CHR-000001",
    display_name="Florence Maeve MacKellar",
    kind=VisualSubjectKind.CHARACTER,
    record_id="rec-florence",
)


def ref(role: str, *, has_image: bool):
    return VisualReferenceAuthority(
        asset_key=f"ASSET-{role}",
        asset_name=role,
        subject_name=SUBJECT.display_name,
        role=role,
        uri=f"https://example.test/{role}.png" if has_image else None,
        controls=(role,),
        does_not_control=(),
        status="Approved Anchor",
        reference_strength="Gold Standard",
        record_id=f"rec-{role}",
    )


class Source:
    def __init__(self, refs):
        self.refs = tuple(refs)

    def resolve_subject(self, query, kind, arc):
        return SUBJECT

    def list_references(self, subject, arc):
        return self.refs


class Compiler:
    def __init__(self):
        self.source = Source((ref("FACE_GOLD", has_image=True), ref("STYLE_GOLD", has_image=False)))

    def compile(self, request):
        job = CompiledVisualJob(
            job_key="PACK::01::portrait",
            arc=request.arc,
            subject_id=SUBJECT.stable_id,
            subject_name=SUBJECT.display_name,
            subject_kind=SUBJECT.kind,
            output_type="portrait",
            prompt="portrait",
            references=(self.source.refs[0],),
            hard_gates=("identity",),
            soft_criteria=(),
            style_rules=(),
            anti_drift=(),
            open_fields=(),
            max_iterations=1,
            missing_dependencies=("MISSING_ATTACHMENT:ASSET-STYLE_GOLD",),
        )
        return CompiledVisualRequest(
            request_key="VIS-RUN::TEST",
            subject=SUBJECT,
            jobs=(job,),
            warnings=("portrait: MISSING_ATTACHMENT:ASSET-STYLE_GOLD",),
        )


def auth(monkeypatch):
    token = "bearer-secret"
    monkeypatch.delenv("BLOOM_API_BEARER_TOKEN", raising=False)
    monkeypatch.setenv("BLOOM_API_BEARER_TOKEN_SHA256", hashlib.sha256(token.encode()).hexdigest())
    return {"Authorization": f"Bearer {token}"}


def test_readiness_separates_authority_metadata_from_image_bytes(monkeypatch):
    headers = auth(monkeypatch)
    monkeypatch.setattr(visual_api, "_compiler", lambda: Compiler())
    client = TestClient(preview_app.app)

    response = client.post(
        "/v1/visual/readiness",
        headers=headers,
        json={
            "arc": "Aster Hollow / At the Threshold",
            "command": "Check Florence visual readiness",
            "subject_query": SUBJECT.display_name,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["authority_metadata_present"] is True
    assert body["authority_roles_present"] == ["FACE_GOLD", "STYLE_GOLD"]
    assert body["authority_roles_with_image_bytes"] == ["FACE_GOLD"]
    assert body["authority_roles_missing_image_bytes"] == ["STYLE_GOLD"]
    assert body["ready_for_any_generation"] is False
    assert body["ready_for_full_requested_pack"] is False
    assert body["spent"] is False
    assert body["renderer_invoked"] is False
