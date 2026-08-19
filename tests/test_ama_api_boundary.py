from __future__ import annotations

from fastapi.testclient import TestClient

from bloom_engine.api import AmaApiServices, RuntimePreviewBody, create_app
from bloom_engine.pantheon.protocol import CoreRequest
from bloom_engine.runtime.models import RunnerOutput, RuntimeQuery, RuntimeTrace, SceneRequest


TOKEN = "test-token-that-is-long-enough-12345"


class StubBuilder:
    def __init__(self, *, realization: str = "PREVIEW", authorization_token=None, permission_mode: str = "READ"):
        self.realization = realization
        self.authorization_token = authorization_token
        self.permission_mode = permission_mode
        self.seen: RuntimePreviewBody | None = None

    def build_preview(self, body: RuntimePreviewBody) -> SceneRequest:
        self.seen = body
        return SceneRequest(
            arc=body.arc,
            command=body.command,
            mode=body.mode,
            realization=self.realization,
            authorization_token=self.authorization_token,
            queries=(
                RuntimeQuery(
                    request=CoreRequest(
                        predicate="magic.applicable",
                        inputs={"magical_question": False, "action": body.command},
                        permission_mode=self.permission_mode,
                    ),
                    required_for_request=False,
                ),
            ),
        )


class StubRunner:
    def __init__(self):
        self.calls: list[SceneRequest] = []

    def run(self, request: SceneRequest) -> RunnerOutput:
        self.calls.append(request)
        trace = RuntimeTrace(
            run_key="RUN::API-TEST",
            request=request,
            final_status="COMPLETE",
        )
        return RunnerOutput(status="COMPLETE", text="safe preview", trace=trace)


def client(builder: StubBuilder | None = None, runner: StubRunner | None = None) -> tuple[TestClient, StubBuilder, StubRunner]:
    builder = builder or StubBuilder()
    runner = runner or StubRunner()
    app = create_app(
        services=AmaApiServices(runner=runner, request_builder=builder),
        bearer_token=TOKEN,
    )
    return TestClient(app), builder, runner


def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def test_health_is_public_but_contains_no_runtime_state():
    c, _, _ = client()
    response = c.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "bloom-engine",
        "api_version": "AMA-BLOOM-API-v0.1",
    }


def test_capabilities_require_auth_and_advertise_closed_write_boundary():
    c, _, _ = client()
    assert c.get("/v1/capabilities").status_code == 401

    response = c.get("/v1/capabilities", headers=auth())
    assert response.status_code == 200
    body = response.json()
    assert body["runtime_preview"] is True
    assert body["runtime_commit"] is False
    assert body["persistence_live"] is False
    assert body["raw_sovereign_query_api"] is False
    assert body["client_may_supply_authoritative_evidence"] is False
    assert body["model_may_mint_write_authority"] is False


def test_wrong_bearer_token_is_rejected():
    c, _, runner = client()
    response = c.post(
        "/v1/runtime/preview",
        headers={"Authorization": "Bearer definitely-wrong-token-123456"},
        json={"arc": "Aster Hollow", "command": "continue"},
    )
    assert response.status_code == 401
    assert runner.calls == []


def test_preview_runs_without_write_authority():
    c, builder, runner = client()
    response = c.post(
        "/v1/runtime/preview",
        headers=auth(),
        json={"arc": "Aster Hollow", "command": "continue", "mode": "LIVE_PLAY"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETE"
    assert response.json()["text"] == "safe preview"
    assert builder.seen is not None
    assert len(runner.calls) == 1
    assert runner.calls[0].realization == "PREVIEW"
    assert runner.calls[0].authorization_token is None


def test_client_cannot_smuggle_query_manifest_evidence_or_capability_token():
    c, _, runner = client()
    response = c.post(
        "/v1/runtime/preview",
        headers=auth(),
        json={
            "arc": "Aster Hollow",
            "command": "continue",
            "queries": [{"predicate": "working.eligible", "inputs": {"endpoint": True}}],
            "evidence": [{"ref": "MODEL-SAYS-SO"}],
            "authorization_token": "AMA-CAP::fake",
        },
    )
    assert response.status_code == 422
    assert runner.calls == []


def test_preview_boundary_rejects_builder_that_creates_commit_request():
    builder = StubBuilder(realization="COMMIT_AFTER_RENDER", authorization_token="AMA-CAP::server-bug")
    c, _, runner = client(builder=builder)
    response = c.post(
        "/v1/runtime/preview",
        headers=auth(),
        json={"arc": "Aster Hollow", "command": "continue"},
    )
    assert response.status_code == 503
    assert runner.calls == []


def test_preview_boundary_rejects_non_read_sovereign_query():
    builder = StubBuilder(permission_mode="COMMIT")
    c, _, runner = client(builder=builder)
    response = c.post(
        "/v1/runtime/preview",
        headers=auth(),
        json={"arc": "Aster Hollow", "command": "continue"},
    )
    assert response.status_code == 503
    assert runner.calls == []


def test_short_server_token_is_configuration_error():
    builder = StubBuilder()
    runner = StubRunner()
    try:
        create_app(
            services=AmaApiServices(runner=runner, request_builder=builder),
            bearer_token="too-short",
        )
    except ValueError as exc:
        assert "at least 24" in str(exc)
    else:
        raise AssertionError("weak API token was accepted")
