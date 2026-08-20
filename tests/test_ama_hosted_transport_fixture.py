from __future__ import annotations

import json
import os
import urllib.request
from types import SimpleNamespace

from fastapi.testclient import TestClient

from bloom_engine.api import AmaApiServices, RuntimePreviewBody, create_app
from bloom_engine.pantheon.protocol import CoreRequest
from bloom_engine.runtime.models import RunnerOutput, RuntimeQuery, RuntimeTrace, SceneRequest


TOKEN = "fixture-token-that-is-long-enough-12345"


class FixtureBuilder:
    def build_preview(self, body: RuntimePreviewBody) -> SceneRequest:
        return SceneRequest(
            arc=body.arc,
            command=body.command,
            mode=body.mode,
            realization="PREVIEW",
            authorization_token=None,
            queries=(
                RuntimeQuery(
                    request=CoreRequest(
                        predicate="magic.applicable",
                        inputs={"magical_question": False, "action": body.command},
                        permission_mode="READ",
                    ),
                    required_for_request=False,
                ),
            ),
        )


class FixtureRunner:
    """Local fixture by default; optional hosted bridge for the known-good GPT domain.

    Render's ama-runtime-preview service imports this class directly. When
    AMA_LIVE_READ_BACKEND_URL is present, the class becomes a narrow read-only
    bridge to the live Current Scene backend. Tests do not set that environment
    variable, so CI continues exercising the deterministic fixture path.
    """

    def __init__(self):
        self.calls: list[SceneRequest] = []

    def run(self, request: SceneRequest) -> RunnerOutput:
        self.calls.append(request)
        backend = os.getenv("AMA_LIVE_READ_BACKEND_URL", "").rstrip("/")
        if backend:
            token = os.environ["BLOOM_API_BEARER_TOKEN"]
            payload = json.dumps(
                {
                    "arc": request.arc,
                    "command": request.command,
                    "mode": "DRY_RUN",
                }
            ).encode("utf-8")
            outbound = urllib.request.Request(
                f"{backend}/v1/runtime/preview",
                data=payload,
                method="POST",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "User-Agent": "BLOOM-Ama-ReadOnly-Bridge/0.1",
                },
            )
            with urllib.request.urlopen(outbound, timeout=20) as response:
                result = json.loads(response.read().decode("utf-8"))
            return SimpleNamespace(
                status=result.get("status", "FAILED"),
                text=result.get("text", ""),
                trace=result.get("trace"),
            )

        trace = RuntimeTrace(
            run_key="RUN::HOSTED-FIXTURE",
            request=request,
            final_status="COMPLETE",
        )
        return RunnerOutput(status="COMPLETE", text="fixture preview", trace=trace)


def hosted_client() -> tuple[TestClient, FixtureRunner]:
    runner = FixtureRunner()
    app = create_app(
        services=AmaApiServices(runner=runner, request_builder=FixtureBuilder()),
        bearer_token=TOKEN,
    )
    return TestClient(app, base_url="https://ama.fixture.invalid"), runner


def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def test_https_reverse_proxy_fixture_preserves_read_only_preview_boundary():
    client, runner = hosted_client()
    headers = {
        **auth(),
        "X-Forwarded-Proto": "https",
        "X-Forwarded-Host": "ama.example.invalid",
        "X-Request-ID": "req-hosted-fixture-0001",
    }
    response = client.post(
        "/v1/runtime/preview",
        headers=headers,
        json={"arc": "Aster Hollow", "command": "continue", "mode": "LIVE_PLAY"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-hosted-fixture-0001"
    assert response.json()["status"] == "COMPLETE"
    assert len(runner.calls) == 1
    request = runner.calls[0]
    assert request.realization == "PREVIEW"
    assert request.authorization_token is None
    assert all(query.request.permission_mode == "READ" for query in request.queries)


def test_hosted_fixture_rejects_client_attempt_to_smuggle_authority_fields():
    client, runner = hosted_client()
    response = client.post(
        "/v1/runtime/preview",
        headers=auth(),
        json={
            "arc": "Aster Hollow",
            "command": "continue",
            "authorization_token": "AMA-CAP::client-forged",
            "queries": [{"predicate": "working.eligible"}],
            "evidence": [{"claim": "model says true"}],
        },
    )

    assert response.status_code == 422
    assert runner.calls == []


def test_hosted_fixture_exposes_no_commit_or_persistence_route():
    client, runner = hosted_client()
    for path in ("/v1/runtime/commit", "/v1/commit", "/v1/persistence"):
        response = client.post(path, headers=auth(), json={})
        assert response.status_code == 404
    assert runner.calls == []


def test_malformed_external_request_id_is_replaced_not_reflected():
    client, _ = hosted_client()
    malicious = "Bearer secret-token should-not-be-an-id"
    response = client.get(
        "/v1/capabilities",
        headers={**auth(), "X-Request-ID": malicious},
    )

    assert response.status_code == 200
    returned = response.headers["X-Request-ID"]
    assert returned != malicious
    assert returned.startswith("req_")
    assert "secret-token" not in returned
