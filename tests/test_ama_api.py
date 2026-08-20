from types import SimpleNamespace

from fastapi.testclient import TestClient

import bloom_engine.api as api


client = TestClient(api.app)


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer secret"}


def test_health_is_public_and_reports_persistence_disabled(monkeypatch):
    monkeypatch.delenv("AIRTABLE_PAT", raising=False)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["persistence_live"] is False
    assert body["airtable_read_configured"] is False


def test_capabilities_require_bearer_auth(monkeypatch):
    monkeypatch.setenv("BLOOM_API_BEARER_TOKEN", "secret")

    unauthorized = client.get("/v1/capabilities")
    assert unauthorized.status_code == 401

    response = client.get("/v1/capabilities", headers=_auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["runtime_preview"] is True
    assert body["runtime_commit"] is False
    assert body["persistence_live"] is False
    assert body["model_may_mint_write_authority"] is False


def test_runtime_preview_is_authenticated_and_read_only(monkeypatch):
    monkeypatch.setenv("BLOOM_API_BEARER_TOKEN", "secret")

    class FakeRunner:
        def run(self, request):
            assert request.mode == "DRY_RUN"
            assert request.realization == "PREVIEW"
            assert request.authorization_token is None
            return SimpleNamespace(
                status="COMPLETE",
                text="Verified active Aster Hollow scene. Read-only preview: nothing was persisted.",
                trace={"mode": "DRY_RUN", "realization": "PREVIEW"},
            )

    monkeypatch.setattr(api, "build_runner", lambda: FakeRunner())

    payload = {
        "arc": "Aster Hollow / At the Threshold",
        "command": "Inspect the current Aster Hollow state and active scene pointer",
        "mode": "DRY_RUN",
    }

    unauthorized = client.post("/v1/runtime/preview", json=payload)
    assert unauthorized.status_code == 401

    response = client.post("/v1/runtime/preview", json=payload, headers=_auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "COMPLETE"
    assert body["trace"]["mode"] == "DRY_RUN"
    assert "nothing was persisted" in body["text"]


def test_runtime_preview_rejects_non_dry_run(monkeypatch):
    monkeypatch.setenv("BLOOM_API_BEARER_TOKEN", "secret")
    response = client.post(
        "/v1/runtime/preview",
        headers=_auth_headers(),
        json={
            "arc": "Aster Hollow / At the Threshold",
            "command": "Inspect the current scene",
            "mode": "COMMIT",
        },
    )
    assert response.status_code == 422


def test_runtime_preview_rejects_unsupported_scope(monkeypatch):
    monkeypatch.setenv("BLOOM_API_BEARER_TOKEN", "secret")
    response = client.post(
        "/v1/runtime/preview",
        headers=_auth_headers(),
        json={
            "arc": "Aster Hollow / At the Threshold",
            "command": "Rewrite Florence canon",
            "mode": "DRY_RUN",
        },
    )
    assert response.status_code == 422
