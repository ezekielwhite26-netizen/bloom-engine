import hashlib
from types import SimpleNamespace

from fastapi.testclient import TestClient

import bloom_engine.api as api
from bloom_engine.runtime.manuscript import (
    F,
    T,
    ManuscriptContextRepository,
    ManuscriptSessionStore,
    review_manuscript,
)


client = TestClient(api.app)
ARC = "Aster Hollow / At the Threshold"


def _auth_headers() -> dict[str, str]:
    return {"Authorization": "Bearer secret"}


def _set_auth(monkeypatch, token: str = "secret") -> None:
    monkeypatch.delenv("BLOOM_API_BEARER_TOKEN", raising=False)
    monkeypatch.setenv(
        "BLOOM_API_BEARER_TOKEN_SHA256",
        hashlib.sha256(token.encode("utf-8")).hexdigest(),
    )


def _rec(record_id: str, fields: dict) -> dict:
    return {"id": record_id, "fields": fields}


class FakeAirtable:
    def __init__(self, rows: dict[str, list[dict]]):
        self.rows = rows

    def list_all(self, table_id: str) -> list[dict]:
        return list(self.rows.get(table_id, []))


def _repository_fixture() -> ManuscriptContextRepository:
    rows = {table_id: [] for table_id in T.values()}
    rows[T["characters"]] = [
        _rec(
            "rec-flo",
            {
                F["characters"]["name"]: "Florence Maeve MacKellar",
                F["characters"]["arc"]: ARC,
                F["characters"]["role"]: "Protagonist",
            },
        )
    ]
    rows[T["locations"]] = [
        _rec(
            "rec-morrows",
            {
                F["location"]["key"]: "BLM-LOC-000009",
                F["location"]["name"]: "Morrow's",
                F["location"]["arc"]: ARC,
                F["location"]["type"]: "Business",
                F["location"]["physical"]: "Ordinary diner first.",
            },
        )
    ]
    rows[T["writing_corrections"]] = [
        _rec(
            "rec-corr",
            {
                F["correction"]["key"]: "BLOOM-WR-CORR-007",
                F["correction"]["arc"]: ARC,
                F["correction"]["scope"]: "Reader orientation",
                F["correction"]["preferred"]: "Land reader-new familiar subjects through Florence-filtered action.",
                F["correction"]["strength"]: "Strong",
                F["correction"]["active"]: True,
            },
        )
    ]
    rows[T["writing_qa"]] = [
        _rec(
            "rec-qa",
            {
                F["qa"]["key"]: "BLOOM-WR-QA-011",
                F["qa"]["arc"]: ARC,
                F["qa"]["category"]: "Epistemics",
                F["qa"]["scope"]: "Reader ledger",
                F["qa"]["assertion"]: "Only accepted Writing Runs advance reader state.",
                F["qa"]["guidance"]: "Preview remains uncommitted.",
                F["qa"]["severity"]: "Blocking",
                F["qa"]["active"]: True,
            },
        )
    ]
    rows[T["gold"]] = [
        _rec(
            "rec-gold-approved",
            {
                F["gold"]["key"]: "ASTER-GOLD-004",
                F["gold"]["arc"]: ARC,
                F["gold"]["title"]: "Morrow's calibration",
                F["gold"]["passage"]: "Approved calibration text.",
                F["gold"]["approved"]: True,
                F["gold"]["status"]: "Approved",
            },
        ),
        _rec(
            "rec-gold-candidate",
            {
                F["gold"]["key"]: "ASTER-GOLD-CAND-999",
                F["gold"]["arc"]: ARC,
                F["gold"]["title"]: "Unapproved candidate",
                F["gold"]["passage"]: "Must not be loaded as Gold.",
                F["gold"]["approved"]: False,
                F["gold"]["status"]: "Candidate",
            },
        ),
    ]
    rows[T["writing_runs"]] = [
        _rec(
            "rec-run-preview",
            {
                F["run"]["key"]: "PREVIEW-RUN",
                F["run"]["arc"]: ARC,
                F["run"]["run_date"]: "2026-08-20T18:00:00Z",
                F["run"]["seen"]: "PREVIEW MUST NOT ADVANCE",
                F["run"]["committed"]: False,
            },
        ),
        _rec(
            "rec-run-committed",
            {
                F["run"]["key"]: "COMMITTED-RUN",
                F["run"]["arc"]: ARC,
                F["run"]["run_date"]: "2026-08-19T18:00:00Z",
                F["run"]["florence"]: "Florence knows the established opening facts.",
                F["run"]["seen"]: "Reader has seen the accepted opening.",
                F["run"]["suspect"]: "Reader may suspect a threshold pattern.",
                F["run"]["withheld"]: "Hidden season truth remains withheld.",
                F["run"]["committed"]: True,
            },
        ),
    ]
    return ManuscriptContextRepository(FakeAirtable(rows))


def test_repository_uses_only_approved_gold_and_committed_reader_ledger():
    context = _repository_fixture().build(
        arc=ARC,
        command="Draft the Morrow's scene",
        scene_or_chapter="Chapter One — Morrow's",
        temporal_scope="HISTORICAL_MANUSCRIPT",
        character_names=("Florence Maeve MacKellar",),
        location_names=("Morrow's",),
    )

    assert context["status"] == "DEGRADED"
    assert [item["key"] for item in context["approved_gold"]] == ["ASTER-GOLD-004"]
    assert context["reader_ledger"]["source_run_key"] == "COMMITTED-RUN"
    assert "accepted opening" in context["reader_ledger"]["reader_has_seen"]
    assert "PREVIEW MUST NOT ADVANCE" not in str(context["reader_ledger"])
    assert context["story_canon_persisted"] is False
    assert context["reader_ledger_committed"] is False
    assert any("Historical manuscript safety" in warning for warning in context["warnings"])


def test_review_blocks_unsupported_claim_and_never_returns_replacement_prose():
    repo = _repository_fixture()
    context = repo.build(
        arc=ARC,
        command="Draft",
        scene_or_chapter="Chapter One",
        temporal_scope="HISTORICAL_MANUSCRIPT",
        character_names=("Florence Maeve MacKellar",),
        location_names=("Morrow's",),
    )
    session = ManuscriptSessionStore().issue(context)

    result = review_manuscript(
        session=session,
        phase="DRAFT",
        claims=({"kind": "FACT", "key": "NOT-ISSUED"},),
        reader_new_subjects=(),
        oriented_subjects=(),
        reader_ledger_commit_requested=False,
    )

    assert result["status"] == "BLOCKED"
    assert result["replacement_prose"] is None
    assert result["story_canon_persisted"] is False
    assert result["reader_ledger_committed"] is False


def test_review_warns_for_reader_new_subject_without_orientation():
    repo = _repository_fixture()
    context = repo.build(
        arc=ARC,
        command="Draft",
        scene_or_chapter="Chapter One",
        temporal_scope="HISTORICAL_MANUSCRIPT",
        character_names=("Florence Maeve MacKellar",),
        location_names=("Morrow's",),
    )
    session = ManuscriptSessionStore().issue(context)
    key = context["allowed_fact_keys"][0]

    result = review_manuscript(
        session=session,
        phase="FINAL",
        claims=({"kind": "FACT", "key": key},),
        reader_new_subjects=("Amara Simone Bellamy",),
        oriented_subjects=(),
        reader_ledger_commit_requested=False,
    )

    assert result["status"] == "PASS_WITH_WARNINGS"
    assert any(f["category"] == "READER_ORIENTATION" for f in result["findings"])


def test_review_blocks_reader_ledger_commit_request():
    context = _repository_fixture().build(
        arc=ARC,
        command="Draft",
        scene_or_chapter="Chapter One",
        temporal_scope="HISTORICAL_MANUSCRIPT",
        character_names=("Florence Maeve MacKellar",),
        location_names=("Morrow's",),
    )
    session = ManuscriptSessionStore().issue(context)

    result = review_manuscript(
        session=session,
        phase="FINAL",
        claims=(),
        reader_new_subjects=(),
        oriented_subjects=(),
        reader_ledger_commit_requested=True,
    )

    assert result["status"] == "BLOCKED"
    assert any("cannot commit Reader Knowledge Ledger" in f["message"] for f in result["findings"])


def test_hosted_context_and_review_are_authenticated_and_read_only(monkeypatch):
    _set_auth(monkeypatch)
    api.manuscript_sessions.clear()
    repo = _repository_fixture()
    monkeypatch.setattr(api, "build_manuscript_repository", lambda: repo)

    payload = {
        "arc": ARC,
        "command": "Draft the Morrow's scene",
        "scene_or_chapter": "Chapter One — Morrow's",
        "temporal_scope": "HISTORICAL_MANUSCRIPT",
        "character_names": ["Florence Maeve MacKellar"],
        "location_names": ["Morrow's"],
    }

    unauthorized = client.post("/v1/manuscript/context", json=payload)
    assert unauthorized.status_code == 401

    response = client.post("/v1/manuscript/context", json=payload, headers=_auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["story_canon_persisted"] is False
    assert body["reader_ledger_committed"] is False
    assert body["clio_invoked"] is False
    context_id = body["context_id"]
    allowed_key = body["context"]["allowed_fact_keys"][0]

    review = client.post(
        "/v1/manuscript/review",
        headers=_auth_headers(),
        json={
            "context_id": context_id,
            "phase": "DRAFT",
            "claims": [{"kind": "FACT", "key": allowed_key}],
            "reader_new_subjects": [],
            "oriented_subjects": [],
            "reader_ledger_commit_requested": False,
        },
    )
    assert review.status_code == 200
    reviewed = review.json()
    assert reviewed["status"] == "PASS"
    assert reviewed["replacement_prose"] is None
    assert reviewed["story_canon_persisted"] is False
    assert reviewed["reader_ledger_committed"] is False
    assert reviewed["clio_invoked"] is False


def test_hosted_review_rejects_unissued_context(monkeypatch):
    _set_auth(monkeypatch)
    api.manuscript_sessions.clear()
    response = client.post(
        "/v1/manuscript/review",
        headers=_auth_headers(),
        json={
            "context_id": "MCTX::not-issued",
            "phase": "DRAFT",
            "claims": [],
        },
    )
    assert response.status_code == 410


def test_capabilities_advertise_manuscript_read_only(monkeypatch):
    _set_auth(monkeypatch)
    response = client.get("/v1/capabilities", headers=_auth_headers())
    assert response.status_code == 200
    body = response.json()
    assert body["manuscript_context"] is True
    assert body["manuscript_review"] is True
    assert body["manuscript_commit"] is False
    assert body["reader_ledger_commit"] is False
    assert body["persistence_live"] is False
