from __future__ import annotations

import hashlib

from fastapi.testclient import TestClient

import bloom_engine.apollo.api as visual_api
import bloom_engine.app as preview_app


class FakeResult:
    def to_public_dict(self):
        return {
            "outcome": "ATTACHED",
            "reference": {"asset_key": "AH-VA-FLO-FACE-GOLD-001", "has_attachment": True},
            "authority_metadata_changed": False,
            "canon_promoted": False,
        }


class FakeIngestor:
    def __init__(self):
        self.calls = []

    def ingest(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResult()


def bearer(monkeypatch, token: str = "bearer-secret"):
    monkeypatch.delenv("BLOOM_API_BEARER_TOKEN", raising=False)
    monkeypatch.setenv("BLOOM_API_BEARER_TOKEN_SHA256", hashlib.sha256(token.encode()).hexdigest())
    return {"Authorization": f"Bearer {token}"}


def payload():
    return {
        "asset_key": "AH-VA-FLO-FACE-GOLD-001",
        "filename": "face.png",
        "mime_type": "image/png",
        "image_base64": "iVBORw0KGgo=",
    }


def test_admin_reference_ingest_route_is_not_advertised_in_openapi(monkeypatch):
    headers = bearer(monkeypatch)
    client = TestClient(preview_app.app)
    schema = client.get("/openapi.json", headers=headers).json()
    assert "/v1/visual/admin/reference-attachment" not in schema["paths"]


def test_normal_bearer_is_not_enough_for_reference_ingest(monkeypatch):
    headers = bearer(monkeypatch)
    monkeypatch.setenv(
        "BLOOM_APOLLO_ADMIN_TOKEN_SHA256",
        hashlib.sha256(b"admin-secret").hexdigest(),
    )
    client = TestClient(preview_app.app)

    response = client.post("/v1/visual/admin/reference-attachment", headers=headers, json=payload())

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing APOLLO admin credentials"


def test_reference_ingest_is_disabled_without_admin_configuration(monkeypatch):
    headers = bearer(monkeypatch)
    monkeypatch.delenv("BLOOM_APOLLO_ADMIN_TOKEN_SHA256", raising=False)
    headers["X-BLOOM-APOLLO-ADMIN"] = "anything"
    client = TestClient(preview_app.app)

    response = client.post("/v1/visual/admin/reference-attachment", headers=headers, json=payload())

    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_correct_admin_token_can_invoke_ingestor_without_authority_promotion(monkeypatch):
    headers = bearer(monkeypatch)
    admin = "admin-secret"
    monkeypatch.setenv("BLOOM_APOLLO_ADMIN_TOKEN_SHA256", hashlib.sha256(admin.encode()).hexdigest())
    headers["X-BLOOM-APOLLO-ADMIN"] = admin
    fake = FakeIngestor()
    monkeypatch.setattr(visual_api, "_reference_ingestor", lambda: fake)
    client = TestClient(preview_app.app)

    response = client.post("/v1/visual/admin/reference-attachment", headers=headers, json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "ATTACHED"
    assert body["authority_metadata_changed"] is False
    assert body["canon_promoted"] is False
    assert len(fake.calls) == 1
