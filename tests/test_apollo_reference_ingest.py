from __future__ import annotations

import base64
import copy
import hashlib

import pytest

from bloom_engine.apollo.reference_ingest import (
    ATTACHMENT_FIELD,
    F,
    AirtableReferenceAttachmentIngestor,
)


PNG_BYTES = b"\x89PNG\r\n\x1a\nBLOOM-TEST"
PNG_B64 = base64.b64encode(PNG_BYTES).decode("ascii")


def record(
    *,
    status: str = "Approved Anchor",
    roles: list[str] | None = None,
    scope: str = "SUBJECT",
    subjects: list[str] | None = None,
    attached: bool = False,
):
    fields = {
        F["key"]: "AH-VA-FLO-FACE-GOLD-001",
        F["name"]: "Florence FACE_GOLD",
        F["status"]: status,
        F["strength"]: "Gold Standard",
        F["authority_roles"]: roles if roles is not None else ["FACE_GOLD"],
        F["authority_scope"]: scope,
        F["subject_entities"]: subjects if subjects is not None else ["rec-florence"],
    }
    if attached:
        fields[ATTACHMENT_FIELD] = [{"id": "att-existing", "url": "https://example.test/existing.png"}]
    return {"id": "rec-visual", "fields": fields}


class FakeIngestor(AirtableReferenceAttachmentIngestor):
    def __init__(self, row):
        super().__init__(base_id="app00000000000000", token="test")
        self.row = copy.deepcopy(row)
        self.upload_calls = 0

    def _list_all(self):
        return [copy.deepcopy(self.row)]

    def _request(self, url: str, *, method: str = "GET", payload=None):
        if method == "POST" and "uploadAttachment" in url:
            self.upload_calls += 1
            self.row.setdefault("fields", {})[ATTACHMENT_FIELD] = [{
                "id": "att-new",
                "url": "https://example.test/new.png",
                "filename": payload["filename"],
            }]
            return copy.deepcopy(self.row)
        if method == "GET" and "/rec-visual?" in url:
            return copy.deepcopy(self.row)
        raise AssertionError(f"unexpected fake request: {method} {url}")


def test_rejected_reference_cannot_receive_bytes():
    ingestor = FakeIngestor(record(status="Rejected"))

    with pytest.raises(PermissionError, match="VISUAL_ASSET_NOT_APPROVED"):
        ingestor.ingest(
            asset_key="AH-VA-FLO-FACE-GOLD-001",
            filename="face.png",
            mime_type="image/png",
            image_base64=PNG_B64,
        )

    assert ingestor.upload_calls == 0


def test_reference_without_explicit_apollo_role_cannot_receive_bytes():
    ingestor = FakeIngestor(record(roles=[]))

    with pytest.raises(PermissionError, match="HAS_NO_APOLLO_AUTHORITY_ROLE"):
        ingestor.inspect("AH-VA-FLO-FACE-GOLD-001")


def test_subject_scoped_reference_requires_stable_subject_link():
    ingestor = FakeIngestor(record(subjects=[]))

    with pytest.raises(PermissionError, match="MISSING_STABLE_SUBJECT_LINK"):
        ingestor.inspect("AH-VA-FLO-FACE-GOLD-001")


def test_ingest_attaches_bytes_without_changing_authority_metadata():
    ingestor = FakeIngestor(record())
    original_status = ingestor.row["fields"][F["status"]]
    original_roles = tuple(ingestor.row["fields"][F["authority_roles"]])

    result = ingestor.ingest(
        asset_key="AH-VA-FLO-FACE-GOLD-001",
        filename="Florence face.png",
        mime_type="image/png",
        image_base64=PNG_B64,
        expected_sha256=hashlib.sha256(PNG_BYTES).hexdigest(),
    )

    assert result.outcome == "ATTACHED"
    assert result.state.has_attachment is True
    assert result.sha256 == hashlib.sha256(PNG_BYTES).hexdigest()
    assert result.byte_count == len(PNG_BYTES)
    assert ingestor.row["fields"][F["status"]] == original_status
    assert tuple(ingestor.row["fields"][F["authority_roles"]]) == original_roles
    assert ingestor.upload_calls == 1


def test_existing_attachment_is_idempotent_and_not_replaced():
    ingestor = FakeIngestor(record(attached=True))

    result = ingestor.ingest(
        asset_key="AH-VA-FLO-FACE-GOLD-001",
        filename="face.png",
        mime_type="image/png",
        image_base64=PNG_B64,
    )

    assert result.outcome == "ALREADY_ATTACHED"
    assert result.state.attachment_id == "att-existing"
    assert ingestor.upload_calls == 0


def test_sha_mismatch_stops_before_upload():
    ingestor = FakeIngestor(record())

    with pytest.raises(ValueError, match="REFERENCE_SHA256_MISMATCH"):
        ingestor.ingest(
            asset_key="AH-VA-FLO-FACE-GOLD-001",
            filename="face.png",
            mime_type="image/png",
            image_base64=PNG_B64,
            expected_sha256="0" * 64,
        )

    assert ingestor.upload_calls == 0
