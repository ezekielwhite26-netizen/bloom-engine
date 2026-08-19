from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from bloom_engine.api import AmaApiServices, create_app
from bloom_engine.api.observability import safe_request_id
from bloom_engine.runtime.models import RunnerOutput, RuntimeTrace, SceneRequest


TOKEN = "test-token-that-is-long-enough-12345"


class Builder:
    def build_preview(self, body):
        return SceneRequest(arc=body.arc, command=body.command, mode="DRY_RUN", realization="PREVIEW")


class Runner:
    def run(self, request):
        trace = RuntimeTrace(run_key="RUN::OBS", request=request, final_status="COMPLETE")
        return RunnerOutput(status="COMPLETE", text="preview", trace=trace)


def make_client():
    app = create_app(
        services=AmaApiServices(runner=Runner(), request_builder=Builder()),
        bearer_token=TOKEN,
    )
    return TestClient(app)


def test_server_mints_safe_request_id_when_missing():
    response = make_client().get("/health")
    request_id = response.headers["X-Request-ID"]
    assert request_id.startswith("req_")
    assert len(request_id) > 20


def test_safe_client_request_id_is_echoed_for_correlation():
    response = make_client().get("/health", headers={"X-Request-ID": "client-req-12345678"})
    assert response.headers["X-Request-ID"] == "client-req-12345678"


def test_malformed_request_id_is_replaced():
    assert safe_request_id("bad id with spaces") != "bad id with spaces"


def test_access_log_never_contains_bearer_token_or_request_body(caplog):
    caplog.set_level(logging.INFO, logger="bloom_engine.api.access")
    secret_command = "private-command-DO-NOT-LOG"
    response = make_client().post(
        "/v1/runtime/preview",
        headers={"Authorization": f"Bearer {TOKEN}"},
        json={"arc": "Aster Hollow", "command": secret_command},
    )
    assert response.status_code == 200
    text = caplog.text
    assert "ama_request" in text
    assert "/v1/runtime/preview" in text
    assert TOKEN not in text
    assert secret_command not in text
    assert "Authorization" not in text
