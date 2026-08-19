from fastapi.testclient import TestClient

from bloom_engine.api import app


client = TestClient(app)


def test_health_is_public_and_reports_persistence_disabled(monkeypatch):
    monkeypatch.delenv("AMA_PERSISTENCE_ENABLED", raising=False)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["persistence_enabled"] is False


def test_run_is_preview_only():
    response = client.post("/v1/run", json={"command": "continue Episode 7"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "PREVIEW"
    assert body["persistence_authorized"] is False


def test_commit_requires_api_key(monkeypatch):
    monkeypatch.setenv("AMA_API_KEY", "secret")
    monkeypatch.setenv("AMA_PERSISTENCE_ENABLED", "false")
    response = client.post(
        "/v1/commit",
        json={"transaction_key": "TXN::1", "capability_token": "AMA-CAP::fixture"},
    )
    assert response.status_code == 401


def test_commit_stays_locked_while_persistence_disabled(monkeypatch):
    monkeypatch.setenv("AMA_API_KEY", "secret")
    monkeypatch.setenv("AMA_PERSISTENCE_ENABLED", "false")
    response = client.post(
        "/v1/commit",
        headers={"x-ama-api-key": "secret"},
        json={"transaction_key": "TXN::1", "capability_token": "AMA-CAP::fixture"},
    )
    assert response.status_code == 423
