from __future__ import annotations

import hashlib
from dataclasses import dataclass

from fastapi.testclient import TestClient

import bloom_engine.apollo.api as visual_api
import bloom_engine.app as preview_app
from bloom_engine.apollo.authority import ApolloVisualAuthorityCompiler
from bloom_engine.apollo.director import ApolloVisualDirector
from bloom_engine.apollo.job_store import InMemoryVisualJobStore
from bloom_engine.apollo.models import (
    CompiledVisualJob,
    CompiledVisualRequest,
    PersistedVisualCandidate,
    RenderedVisual,
    VisualGateStatus,
    VisualJobRequest,
    VisualPackDefinition,
    VisualPackJobDefinition,
    VisualQAGate,
    VisualQAReport,
    VisualReferenceAuthority,
    VisualRequestKind,
    VisualRunStatus,
    VisualSubjectIdentity,
    VisualSubjectKind,
)
from bloom_engine.apollo.storage import InMemoryVisualAssetStore


ARC = "Aster Hollow / At the Threshold"
FLORENCE = VisualSubjectIdentity(
    stable_id="BLM-CHR-000001",
    display_name="Florence Maeve MacKellar",
    kind=VisualSubjectKind.CHARACTER,
    record_id="rec-florence",
)


def _ref(role: str, *, uri: str | None = "https://example.test/gold.png") -> VisualReferenceAuthority:
    return VisualReferenceAuthority(
        asset_key=f"ASSET::{role}",
        asset_name=role,
        subject_name=FLORENCE.display_name,
        role=role,
        uri=uri,
        controls=(role,),
        does_not_control=("open fields",),
        status="Approved Anchor",
        reference_strength="Gold Standard",
        record_id=f"rec-{role}",
        width=512,
        height=512,
    )


def _job(*, max_iterations: int = 5, ready: bool = True) -> CompiledVisualJob:
    return CompiledVisualJob(
        job_key="AH-FLO-PACK::left_profile",
        arc=ARC,
        subject_id=FLORENCE.stable_id,
        subject_name=FLORENCE.display_name,
        subject_kind=VisualSubjectKind.CHARACTER,
        output_type="left_profile",
        prompt="Generate a left-profile calibration view.",
        references=(_ref("FACE_GOLD"),),
        hard_gates=("same Florence identity", "reads as sixteen"),
        soft_criteria=("production readability",),
        style_rules=("painted illustrated realism",),
        anti_drift=("do not adultify",),
        open_fields=("incidental outfit",),
        max_iterations=max_iterations,
        missing_dependencies=() if ready else ("REFERENCE:FACE_GOLD",),
    )


def _compiled(*, ready: bool = True, max_iterations: int = 5) -> CompiledVisualRequest:
    return CompiledVisualRequest(
        request_key="VIS-RUN::TEST",
        subject=FLORENCE,
        jobs=(_job(ready=ready, max_iterations=max_iterations),),
        warnings=() if ready else ("left_profile: REFERENCE:FACE_GOLD",),
    )


class StaticCompiler:
    def __init__(self, value: CompiledVisualRequest):
        self.value = value
        self.calls = 0

    def compile(self, request):
        self.calls += 1
        return self.value


class RecordingRenderer:
    def __init__(self, provider_id: str):
        self.provider_id = provider_id
        self.calls: list[dict] = []

    def render(self, job, **kwargs):
        self.calls.append({"job": job, **kwargs})
        n = len(self.calls)
        return RenderedVisual(
            provider_id=self.provider_id,
            model=f"{self.provider_id}-test",
            mime_type="image/png",
            temporary_url=f"https://example.test/{self.provider_id}-{n}.png",
        )


class SequenceCritic:
    def __init__(self, reports: list[VisualQAReport]):
        self.reports = list(reports)
        self.calls = []

    def review(self, job, candidate, previous_best=None):
        self.calls.append((candidate, previous_best))
        return self.reports.pop(0)


def _qa(
    *,
    overall: bool,
    identity: float,
    repair: tuple[str, ...] = (),
    preserve: tuple[str, ...] = (),
    hard_fail: bool = False,
) -> VisualQAReport:
    return VisualQAReport(
        overall_pass=overall,
        hard_gate_results=(
            VisualQAGate(
                gate="identity",
                status=VisualGateStatus.FAIL if hard_fail else VisualGateStatus.PASS,
                evidence="test evidence",
                repair="fix identity" if hard_fail else "",
            ),
        ),
        identity_score=identity,
        style_score=identity,
        period_score=identity,
        production_score=identity,
        regressions=(),
        repair_plan=repair,
        preserve=preserve,
        summary=f"qa-{identity}",
    )


def _request(token: str | None = "VIS-CAP::test") -> VisualJobRequest:
    return VisualJobRequest(
        arc=ARC,
        command="Build Florence left profile",
        subject_query="Florence Maeve MacKellar",
        subject_kind=VisualSubjectKind.CHARACTER,
        request_kind=VisualRequestKind.SINGLE_ASSET,
        output_type="left_profile",
        authorization_token=token,
    )


def test_director_requires_explicit_generation_capability():
    renderer = RecordingRenderer("flux-2-pro")
    director = ApolloVisualDirector(
        compiler=StaticCompiler(_compiled()),
        renderers={"flux-2-pro": renderer, "gpt-image-2": RecordingRenderer("gpt-image-2")},
        critic=SequenceCritic([_qa(overall=True, identity=100)]),
        assets=InMemoryVisualAssetStore(),
    )

    try:
        director.run(_request(token=None))
    except PermissionError as exc:
        assert str(exc) == "VISUAL_GENERATION_AUTHORIZATION_REQUIRED"
    else:
        raise AssertionError("director generated without an authorization token")

    assert renderer.calls == []


def test_system_pass_remains_non_gold():
    assets = InMemoryVisualAssetStore()
    director = ApolloVisualDirector(
        compiler=StaticCompiler(_compiled()),
        renderers={"flux-2-pro": RecordingRenderer("flux-2-pro"), "gpt-image-2": RecordingRenderer("gpt-image-2")},
        critic=SequenceCritic([_qa(overall=True, identity=100)]),
        assets=assets,
    )

    result = director.run(_request())

    assert result.status is VisualRunStatus.SYSTEM_PASS
    assert result.requires_human_approval is True
    assert result.jobs[0].best_candidate is not None
    assert result.jobs[0].best_candidate.status == "SYSTEM_PASS"
    assert all(candidate.status not in {"APPROVED", "GOLD"} for candidate in assets.candidates)


def test_repair_uses_qa_from_best_candidate_not_worse_current_candidate():
    primary = RecordingRenderer("flux-2-pro")
    repair = RecordingRenderer("gpt-image-2")
    first = _qa(
        overall=False,
        identity=80,
        repair=("make the profile nose match FACE_GOLD",),
        preserve=("hair length", "age read"),
        hard_fail=True,
    )
    worse = _qa(
        overall=False,
        identity=20,
        repair=("bad-current-repair-plan",),
        preserve=("bad-current-preserve",),
        hard_fail=True,
    )
    final = _qa(overall=True, identity=95)
    director = ApolloVisualDirector(
        compiler=StaticCompiler(_compiled(max_iterations=5)),
        renderers={"flux-2-pro": primary, "gpt-image-2": repair},
        critic=SequenceCritic([first, worse, final]),
        assets=InMemoryVisualAssetStore(),
    )

    result = director.run(_request())

    assert result.status is VisualRunStatus.SYSTEM_PASS
    assert len(repair.calls) == 2
    assert repair.calls[0]["repair_plan"] == first.repair_plan
    assert repair.calls[1]["repair_plan"] == first.repair_plan
    assert repair.calls[1]["preserve"] == first.preserve
    assert repair.calls[1]["previous_candidate"].candidate_id == "TEST-CAND-1"


def test_two_non_improving_iterations_stop_loop():
    repair = RecordingRenderer("gpt-image-2")
    director = ApolloVisualDirector(
        compiler=StaticCompiler(_compiled(max_iterations=6)),
        renderers={"flux-2-pro": RecordingRenderer("flux-2-pro"), "gpt-image-2": repair},
        critic=SequenceCritic([
            _qa(overall=False, identity=80, repair=("r1",), hard_fail=True),
            _qa(overall=False, identity=50, repair=("r2",), hard_fail=True),
            _qa(overall=False, identity=40, repair=("r3",), hard_fail=True),
        ]),
        assets=InMemoryVisualAssetStore(),
    )

    result = director.run(_request())

    assert result.status is VisualRunStatus.HUMAN_REVIEW_REQUIRED
    assert result.jobs[0].stop_reason == "TWO_CONSECUTIVE_NON_IMPROVING_ITERATIONS"
    assert len(result.jobs[0].candidates) == 3


def test_compiler_blocks_when_explicit_gold_role_has_no_image_attachment():
    class Source:
        def resolve_subject(self, query, kind, arc):
            return FLORENCE

        def list_references(self, subject, arc):
            return (_ref("FACE_GOLD", uri=None),)

        def approved_slots(self, subject, arc):
            return ()

    pack = VisualPackDefinition(
        key="PACK",
        subject_id=FLORENCE.stable_id,
        jobs=(
            VisualPackJobDefinition(
                output_type="portrait",
                priority=1,
                prompt="portrait",
                required_reference_roles=("FACE_GOLD",),
                hard_gates=("identity",),
            ),
        ),
    )
    compiler = ApolloVisualAuthorityCompiler(Source(), {FLORENCE.stable_id: pack})
    result = compiler.compile(VisualJobRequest(
        arc=ARC,
        command="plan portrait",
        subject_query=FLORENCE.display_name,
        subject_kind=VisualSubjectKind.CHARACTER,
        request_kind=VisualRequestKind.SINGLE_ASSET,
        output_type="portrait",
    ))

    assert result.jobs[0].ready is False
    assert result.jobs[0].missing_dependencies == ("MISSING_ATTACHMENT:ASSET::FACE_GOLD",)


def _set_auth(monkeypatch, token: str = "secret") -> dict[str, str]:
    monkeypatch.delenv("BLOOM_API_BEARER_TOKEN", raising=False)
    monkeypatch.setenv(
        "BLOOM_API_BEARER_TOKEN_SHA256",
        hashlib.sha256(token.encode("utf-8")).hexdigest(),
    )
    return {"Authorization": f"Bearer {token}"}


def _payload(*, confirm_spend: bool | None = None):
    payload = {
        "arc": ARC,
        "command": "Build Florence full production profile",
        "subject_query": "Florence Maeve MacKellar",
        "subject_kind": "CHARACTER",
        "request_kind": "PRODUCTION_PACK",
    }
    if confirm_spend is not None:
        payload["confirm_spend"] = confirm_spend
    return payload


def test_visual_routes_are_bearer_protected(monkeypatch):
    monkeypatch.setattr(visual_api, "_compiler", lambda: StaticCompiler(_compiled()))
    client = TestClient(preview_app.app)
    response = client.post("/v1/visual/plan", json=_payload())
    assert response.status_code == 401


def test_plan_is_read_only_and_does_not_invoke_renderer(monkeypatch):
    headers = _set_auth(monkeypatch)
    compiler = StaticCompiler(_compiled())
    monkeypatch.setattr(visual_api, "_compiler", lambda: compiler)
    monkeypatch.setattr(visual_api, "_director", lambda: (_ for _ in ()).throw(AssertionError("renderer invoked by plan")))
    client = TestClient(preview_app.app)

    response = client.post("/v1/visual/plan", headers=headers, json=_payload())

    assert response.status_code == 200
    assert response.json()["jobs"][0]["ready"] is True
    assert compiler.calls == 1


def test_generate_requires_current_request_spend_confirmation(monkeypatch):
    headers = _set_auth(monkeypatch)
    monkeypatch.setattr(visual_api, "_compiler", lambda: StaticCompiler(_compiled()))
    client = TestClient(preview_app.app)

    response = client.post("/v1/visual/generate", headers=headers, json=_payload(confirm_spend=False))

    assert response.status_code == 422
    assert "confirm_spend=true" in response.json()["detail"]


def test_blocked_plan_returns_spent_false_before_provider_check(monkeypatch):
    headers = _set_auth(monkeypatch)
    monkeypatch.delenv("BFL_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(visual_api, "_compiler", lambda: StaticCompiler(_compiled(ready=False)))
    client = TestClient(preview_app.app)

    response = client.post("/v1/visual/generate", headers=headers, json=_payload(confirm_spend=True))

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "BLOCKED"
    assert body["spent"] is False
    assert body["visual_job_id"] is None


def test_generation_job_is_durable_and_still_requires_human_review(monkeypatch):
    headers = _set_auth(monkeypatch)
    monkeypatch.setenv("BFL_API_KEY", "test-bfl")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    compiler = StaticCompiler(_compiled())
    jobs = InMemoryVisualJobStore()

    class FakeDirector:
        def run(self, request):
            assert request.authorization_token and request.authorization_token.startswith("VIS-CAP::")
            return type("Output", (), {
                "status": VisualRunStatus.SYSTEM_PASS,
                "to_public_dict": lambda self: {
                    "request_key": "VIS-RUN::TEST",
                    "subject_id": FLORENCE.stable_id,
                    "subject_name": FLORENCE.display_name,
                    "status": "SYSTEM_PASS",
                    "requires_human_approval": True,
                    "jobs": [],
                    "warnings": [],
                },
            })()

    monkeypatch.setattr(visual_api, "_compiler", lambda: compiler)
    monkeypatch.setattr(visual_api, "_job_store", lambda: jobs)
    monkeypatch.setattr(visual_api, "_director", lambda: FakeDirector())
    client = TestClient(preview_app.app)

    response = client.post("/v1/visual/generate", headers=headers, json=_payload(confirm_spend=True))

    assert response.status_code == 200
    job_id = response.json()["visual_job_id"]
    assert response.json()["requires_human_approval"] is True
    state = jobs.get(job_id)
    assert state is not None
    assert state.status == "SYSTEM_PASS"
    assert state.result is not None
    assert state.result["requires_human_approval"] is True

    status_response = client.get(f"/v1/visual/jobs/{job_id}", headers=headers)
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "SYSTEM_PASS"
    assert status_response.json()["requires_human_approval"] is True
