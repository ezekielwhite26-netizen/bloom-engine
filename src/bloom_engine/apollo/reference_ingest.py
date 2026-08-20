from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


VISUAL_ASSETS = "tblR8LVRGUEFGS2lX"
ATTACHMENT_FIELD = "fld0cB8AomF9eAFHs"
F = {
    "key": "fldkJGMdmUlVVqCLu",
    "name": "fldPyou5bDkoxqgno",
    "attachment": ATTACHMENT_FIELD,
    "status": "fldvKWE2Sc2KyJ1zB",
    "strength": "fldItxdvTYigaC4Qr",
    "subject_entities": "fldqCp7EF233chehy",
    "authority_roles": "fldsHT2et8d6AZosf",
    "authority_scope": "fldOdVVEwNa7xT0Q6",
}

APPROVED_ASSET_STATUSES = {"Approved Anchor", "Approved Secondary"}
ALLOWED_IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/webp"}
MAX_DIRECT_UPLOAD_BYTES = 5 * 1024 * 1024


def _select_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or "").strip()
    return str(value or "").strip()


def _select_names(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    values: list[str] = []
    for item in value:
        name = _select_name(item)
        if name:
            values.append(name)
    return tuple(values)


def _linked_record_ids(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    ids: list[str] = []
    for item in value:
        if isinstance(item, str) and item.startswith("rec"):
            ids.append(item)
        elif isinstance(item, dict):
            candidate = str(item.get("id") or "")
            if candidate.startswith("rec"):
                ids.append(candidate)
    return tuple(ids)


def _safe_filename(value: str, mime_type: str) -> str:
    raw = os.path.basename(value.strip()) or "reference"
    stem = re.sub(r"[^A-Za-z0-9._ -]+", "_", raw).strip(" .") or "reference"
    lower = stem.lower()
    expected = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }[mime_type]
    if not lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
        stem += expected
    return stem[:180]


@dataclass(frozen=True, slots=True)
class ReferenceAttachmentState:
    asset_key: str
    asset_name: str
    record_id: str
    status: str
    reference_strength: str
    authority_roles: tuple[str, ...]
    authority_scope: str
    subject_record_ids: tuple[str, ...]
    has_attachment: bool
    attachment_id: str | None = None
    attachment_url: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "asset_key": self.asset_key,
            "asset_name": self.asset_name,
            "record_id": self.record_id,
            "status": self.status,
            "reference_strength": self.reference_strength,
            "authority_roles": list(self.authority_roles),
            "authority_scope": self.authority_scope,
            "subject_record_ids": list(self.subject_record_ids),
            "has_attachment": self.has_attachment,
            "attachment_id": self.attachment_id,
            "attachment_url": self.attachment_url,
        }


@dataclass(frozen=True, slots=True)
class ReferenceAttachmentIngestResult:
    outcome: str
    state: ReferenceAttachmentState
    sha256: str | None
    byte_count: int | None

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
            "reference": self.state.to_public_dict(),
            "authority_metadata_changed": False,
            "canon_promoted": False,
        }


@dataclass(slots=True)
class AirtableReferenceAttachmentIngestor:
    """Attach already-approved reference bytes without changing visual authority.

    This is deliberately an operator path, not a renderer. The target Visual
    Assets row must already be curated and approved. The method never assigns a
    role, changes approval status/reference strength, or promotes canon. Existing
    attachments make the operation idempotent: no replacement occurs implicitly.
    """

    base_id: str
    token: str
    timeout_seconds: int = 60
    api_base: str = "https://api.airtable.com/v0"
    content_base: str = "https://content.airtable.com/v0"

    def _request(self, url: str, *, method: str = "GET", payload: Any | None = None) -> dict[str, Any]:
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "BLOOM-APOLLO-Reference-Ingest/0.1",
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _table_url(self) -> str:
        table = urllib.parse.quote(VISUAL_ASSETS, safe="")
        return f"{self.api_base}/{self.base_id}/{table}"

    def _list_all(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        offset: str | None = None
        while True:
            query = {"returnFieldsByFieldId": "true"}
            if offset:
                query["offset"] = offset
            payload = self._request(self._table_url() + "?" + urllib.parse.urlencode(query))
            records.extend(payload.get("records", []))
            offset = payload.get("offset")
            if not offset:
                return records

    def _record_by_asset_key(self, asset_key: str) -> dict[str, Any]:
        target = asset_key.strip()
        matches = [
            row for row in self._list_all()
            if str((row.get("fields") or {}).get(F["key"], "")).strip() == target
        ]
        if not matches:
            raise ValueError(f"VISUAL_ASSET_NOT_FOUND:{target}")
        if len(matches) != 1:
            raise ValueError(f"DUPLICATE_VISUAL_ASSET_KEY:{target}")
        return matches[0]

    @staticmethod
    def _state(record: dict[str, Any]) -> ReferenceAttachmentState:
        fields = record.get("fields") or {}
        attachments = fields.get(F["attachment"]) or []
        first = attachments[0] if isinstance(attachments, list) and attachments else {}
        return ReferenceAttachmentState(
            asset_key=str(fields.get(F["key"], "")).strip(),
            asset_name=str(fields.get(F["name"], "")).strip(),
            record_id=str(record.get("id") or ""),
            status=_select_name(fields.get(F["status"])),
            reference_strength=_select_name(fields.get(F["strength"])),
            authority_roles=_select_names(fields.get(F["authority_roles"])),
            authority_scope=_select_name(fields.get(F["authority_scope"])) or "SUBJECT",
            subject_record_ids=_linked_record_ids(fields.get(F["subject_entities"])),
            has_attachment=bool(first),
            attachment_id=str(first.get("id") or "") or None if isinstance(first, dict) else None,
            attachment_url=str(first.get("url") or "") or None if isinstance(first, dict) else None,
        )

    @staticmethod
    def _validate_curated_target(state: ReferenceAttachmentState) -> None:
        if state.status not in APPROVED_ASSET_STATUSES:
            raise PermissionError(f"VISUAL_ASSET_NOT_APPROVED:{state.asset_key}:{state.status or 'NONE'}")
        if not state.authority_roles:
            raise PermissionError(f"VISUAL_ASSET_HAS_NO_APOLLO_AUTHORITY_ROLE:{state.asset_key}")
        if state.authority_scope == "SUBJECT" and not state.subject_record_ids:
            raise PermissionError(f"SUBJECT_SCOPED_ASSET_MISSING_STABLE_SUBJECT_LINK:{state.asset_key}")
        if state.authority_scope not in {"SUBJECT", "ARC", "GLOBAL"}:
            raise PermissionError(f"INVALID_APOLLO_AUTHORITY_SCOPE:{state.asset_key}:{state.authority_scope}")

    def inspect(self, asset_key: str) -> ReferenceAttachmentState:
        state = self._state(self._record_by_asset_key(asset_key))
        self._validate_curated_target(state)
        return state

    def ingest(
        self,
        *,
        asset_key: str,
        filename: str,
        mime_type: str,
        image_base64: str,
        expected_sha256: str | None = None,
    ) -> ReferenceAttachmentIngestResult:
        state = self.inspect(asset_key)
        if state.has_attachment:
            return ReferenceAttachmentIngestResult("ALREADY_ATTACHED", state, None, None)

        mime = mime_type.strip().lower()
        if mime not in ALLOWED_IMAGE_MIME_TYPES:
            raise ValueError(f"UNSUPPORTED_REFERENCE_IMAGE_TYPE:{mime_type}")
        try:
            raw = base64.b64decode(image_base64, validate=True)
        except Exception as exc:
            raise ValueError("INVALID_REFERENCE_BASE64") from exc
        if not raw:
            raise ValueError("EMPTY_REFERENCE_IMAGE")
        if len(raw) > MAX_DIRECT_UPLOAD_BYTES:
            raise ValueError(f"REFERENCE_IMAGE_TOO_LARGE_FOR_AIRTABLE_DIRECT_UPLOAD:{len(raw)}")

        digest = hashlib.sha256(raw).hexdigest()
        if expected_sha256 and digest.casefold() != expected_sha256.strip().casefold():
            raise ValueError("REFERENCE_SHA256_MISMATCH")

        safe_name = _safe_filename(filename, mime)
        url = f"{self.content_base}/{self.base_id}/{state.record_id}/{ATTACHMENT_FIELD}/uploadAttachment"
        self._request(
            url,
            method="POST",
            payload={
                "contentType": mime,
                "file": image_base64,
                "filename": safe_name,
            },
        )

        # Read back from Airtable rather than trusting upload success alone. The
        # readback proves bytes are now available to the runtime's authority
        # compiler. No authority/status fields are written here.
        query = urllib.parse.urlencode({"returnFieldsByFieldId": "true"})
        readback = self._request(f"{self._table_url()}/{state.record_id}?{query}")
        verified = self._state(readback)
        self._validate_curated_target(verified)
        if not verified.has_attachment:
            raise RuntimeError(f"REFERENCE_ATTACHMENT_READBACK_FAILED:{state.asset_key}")
        return ReferenceAttachmentIngestResult("ATTACHED", verified, digest, len(raw))
