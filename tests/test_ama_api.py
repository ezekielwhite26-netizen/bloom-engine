import hashlib
import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

import bloom_engine.api as api


client = TestClient(api.app)


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer secret"}


def _set_auth(monkeypatch, token: str = "secret") -> None:
    monkeypatch.delenv("BLOOM_API_BEARER_TOKEN", raising=False)
    monkeypatch.setenv(
        "BLOOM_API_BEARER_TOKEN_SHA256",
        hashlib.sha256(token.encode("utf-8")).hexdigest(),
    )


def test_health_is_public_and_reports_persistence_disabled(monkeypatch):
    monkeypatch.delenv("AIRTABLE_PAT", raising=False)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["persistence_live"] is False
    assert body["airtable_read_configured"] is False


def test_capabilities_require_bearer_auth(monkeypatch):
    _set_auth(monkeypatch)

    unauthorized = client.get("/v1/capabilities")
    assert unauthorized.status_code == 401

    response = client.get("/v1/capabilities", headers=_auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["runtime_preview"] is True
    assert body["runtime_commit"] is False
    assert body["persistence_live"] is False
    assert body["model_may_mint_write_authority"] is False


def test_legacy_raw_bearer_env_still_works(monkeypatch):
    monkeypatch.delenv("BLOOM_API_BEARER_TOKEN_SHA256", raising=False)
    monkeypatch.setenv("BLOOM_API_BEARER_TOKEN", "secret")
    response = client.get("/v1/capabilities", headers=_auth_headers())
    assert response.status_code == 200


def test_runtime_preview_is_authenticated_read_only_and_compact(monkeypatch):
    _set_auth(monkeypatch)

    huge_internal_blob = "x" * 100_000

    class FakeRunner:
        def run(self, request):
            assert request.mode == "DRY_RUN"
            assert request.realization == "PREVIEW"
            assert request.authorization_token is None
            return SimpleNamespace(
                status="COMPLETE",
                text="Verified active Aster Hollow scene. Read-only preview: nothing was persisted.",
                trace=SimpleNamespace(
                    run_key="RUN::TEST",
                    final_status="COMPLETE",
                    packet=SimpleNamespace(
                        packet_key="PKT::TEST",
                        contract_version="TEST-v1",
                        blockers=(),
                        warnings=(),
                        huge_internal_blob=huge_internal_blob,
                    ),
                    athena=SimpleNamespace(
                        selected_option_id="AMA-READ-CURRENT-SCENE",
                        fulcrum="READ_ONLY_INSPECTION",
                        result="ACT",
                        reason_code="AUTHORITATIVE_CURRENT_SCENE_READ",
                    ),
                    clio=None,
                    huge_internal_blob=huge_internal_blob,
                ),
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
    assert body["trace"]["request"]["mode"] == "DRY_RUN"
    assert body["trace"]["request"]["realization"] == "PREVIEW"
    assert body["trace"]["packet"]["packet_key"] == "PKT::TEST"
    assert body["trace"]["clio"]["status"] == "NOT_INVOKED"
    assert "nothing was persisted" in body["text"]
    assert "huge_internal_blob" not in json.dumps(body)
    assert len(response.content) < 8_192


def test_runtime_preview_rejects_non_dry_run(monkeypatch):
    _set_auth(monkeypatch)
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
    _set_auth(monkeypatch)
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
