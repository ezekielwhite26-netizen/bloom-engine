from __future__ import annotations

import base64
import json
import time
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from bloom_engine.apollo.models import CompiledVisualJob, PersistedVisualCandidate, RenderedVisual

VISUAL_ASSETS = "tblR8LVRGUEFGS2lX"
ATTACHMENT_FIELD = "fld0cB8AomF9eAFHs"
F = {
    "key": "fldkJGMdmUlVVqCLu",
    "name": "fldPyou5bDkoxqgno",
    "arc": "fldfYhxo2CaqwsUZp",
    "subjects": "fld9BzJ4e9jJl2JDI",
    "subject_entities": "fldqCp7EF233chehy",
    "type": "fldambDi840eB0cMu",
    "attachment": ATTACHMENT_FIELD,
    "controls": "fldW5ZCmomkkibVaH",
    "not_controls": "fldR8BHiNwbZ53lFV",
    "parents": "fldNXxe3HxnaKbyhF",
    "brief": "fldrssrZvqWnCRMu5",
    "continuity": "fldxr3taTNYXYAwzN",
    "findings": "fldxOjJDXFhN7Hl2H",
    "era": "fldkv6Q1B4LoizAnQ",
    "provenance": "fldlk9bgSKcKyfZu4",
    "created": "fldQ7Shz5Yxnt0Sbw",
    "notes": "fldEBMrKVPlm8Jt1F",
    "production_slot": "fldrpOM8fkP4GINBs",
}


class VisualAssetStore(Protocol):
    def persist_generated(self, job: CompiledVisualJob, rendered: RenderedVisual, *, iteration: int, parent_candidate_id: str | None = None) -> PersistedVisualCandidate: ...
    def mark_system_pass(self, candidate: PersistedVisualCandidate, findings: str) -> PersistedVisualCandidate: ...


@dataclass(slots=True)
class AirtableVisualAssetStore:
    """Durable candidate registry using BLOOM's existing Visual Assets table.

    The generated image is copied into Airtable before provider delivery URLs
    expire. The record deliberately leaves approval/reference-strength/authority
    roles blank. A system pass updates only QA metadata; it never creates visual
    canon authority.
    """

    base_id: str
    token: str
    timeout_seconds: int = 60
    api_base: str = "https://api.airtable.com/v0"
    content_base: str = "https://content.airtable.com/v0"

    def _request(self, url: str, *, method: str, payload: Any) -> dict[str, Any]:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method=method,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _create_candidate_record(self, job: CompiledVisualJob, rendered: RenderedVisual, iteration: int, parent_candidate_id: str | None) -> dict[str, Any]:
        if not job.subject_record_id or not job.subject_record_id.startswith("rec"):
            raise RuntimeError("MISSING_STABLE_SUBJECT_RECORD_LINK")
        asset_key = f"AH-VIS-GEN-{uuid.uuid4().hex[:16]}-{iteration}"
        parent_text = parent_candidate_id or "; ".join(ref.asset_key for ref in job.references)
        fields: dict[str, Any] = {
            F["key"]: asset_key,
            F["name"]: f"{job.subject_name} — {job.output_type} — Candidate {iteration}",
            F["arc"]: job.arc,
            F["subjects"]: job.subject_name,
            F["subject_entities"]: [job.subject_record_id],
            F["production_slot"]: job.output_type,
            F["type"]: "Other",
            F["not_controls"]: "Presentation-only generated candidate. Not authoritative for any visible field unless explicitly approved later.",
            F["parents"]: parent_text,
            F["brief"]: job.prompt,
            F["provenance"]: f"APOLLO Visual Director; renderer={rendered.provider_id}; model={rendered.model}; job={job.job_key}; iteration={iteration}",
            F["created"]: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            F["notes"]: "GENERATED candidate. Production Slot is operational metadata only. SYSTEM_PASS, if later recorded, is not human approval and is not Gold.",
        }
        if rendered.temporary_url:
            fields[F["attachment"]] = [{"url": rendered.temporary_url, "filename": f"{asset_key}.png"}]
        table = urllib.parse.quote(VISUAL_ASSETS, safe="")
        return self._request(
            f"{self.api_base}/{self.base_id}/{table}?returnFieldsByFieldId=true",
            method="POST",
            payload={"records": [{"fields": fields}], "typecast": False},
        )["records"][0]

    def _upload_base64(self, record_id: str, asset_key: str, rendered: RenderedVisual) -> dict[str, Any]:
        if not rendered.image_base64:
            raise RuntimeError("NO_BASE64_IMAGE_TO_UPLOAD")
        raw = base64.b64decode(rendered.image_base64, validate=True)
        if len(raw) > 5 * 1024 * 1024:
            raise RuntimeError(f"AIRTABLE_DIRECT_UPLOAD_TOO_LARGE:{len(raw)}")
        url = f"{self.content_base}/{self.base_id}/{record_id}/{ATTACHMENT_FIELD}/uploadAttachment"
        return self._request(
            url,
            method="POST",
            payload={"contentType": rendered.mime_type, "file": rendered.image_base64, "filename": f"{asset_key}.png"},
        )

    @staticmethod
    def _attachment(record: dict[str, Any]) -> tuple[str, str]:
        attachments = (record.get("fields") or {}).get(ATTACHMENT_FIELD) or []
        if not attachments:
            raise RuntimeError("AIRTABLE_CANDIDATE_ATTACHMENT_NOT_AVAILABLE")
        first = attachments[-1]
        return str(first.get("id", "")), str(first.get("url", ""))

    def persist_generated(self, job: CompiledVisualJob, rendered: RenderedVisual, *, iteration: int, parent_candidate_id: str | None = None) -> PersistedVisualCandidate:
        record = self._create_candidate_record(job, rendered, iteration, parent_candidate_id)
        asset_key = str((record.get("fields") or {}).get(F["key"], ""))
        if not rendered.temporary_url:
            record = self._upload_base64(str(record["id"]), asset_key, rendered)
        attachment_id, preview_url = self._attachment(record)
        if not preview_url:
            raise RuntimeError("AIRTABLE_CANDIDATE_PREVIEW_URL_MISSING")
        return PersistedVisualCandidate(
            candidate_id=attachment_id or f"ATTACHMENT::{record['id']}",
            asset_key=asset_key,
            asset_record_id=str(record["id"]),
            job_key=job.job_key,
            iteration=iteration,
            provider_id=rendered.provider_id,
            model=rendered.model,
            preview_url=preview_url,
            parent_candidate_id=parent_candidate_id,
            status="GENERATED",
            created_at=str(record.get("createdTime") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())),
        )

    def mark_system_pass(self, candidate: PersistedVisualCandidate, findings: str) -> PersistedVisualCandidate:
        table = urllib.parse.quote(VISUAL_ASSETS, safe="")
        self._request(
            f"{self.api_base}/{self.base_id}/{table}/{candidate.asset_record_id}?returnFieldsByFieldId=true",
            method="PATCH",
            payload={"fields": {
                F["continuity"]: "Pass",
                F["findings"]: findings,
                F["notes"]: "SYSTEM_PASS only. Human approval is still required before APPROVED/GOLD. No APOLLO Authority Role is assigned automatically.",
            }},
        )
        return PersistedVisualCandidate(
            candidate_id=candidate.candidate_id,
            asset_key=candidate.asset_key,
            asset_record_id=candidate.asset_record_id,
            job_key=candidate.job_key,
            iteration=candidate.iteration,
            provider_id=candidate.provider_id,
            model=candidate.model,
            preview_url=candidate.preview_url,
            parent_candidate_id=candidate.parent_candidate_id,
            status="SYSTEM_PASS",
            created_at=candidate.created_at,
        )


class InMemoryVisualAssetStore:
    def __init__(self) -> None:
        self.candidates: list[PersistedVisualCandidate] = []

    def persist_generated(self, job: CompiledVisualJob, rendered: RenderedVisual, *, iteration: int, parent_candidate_id: str | None = None) -> PersistedVisualCandidate:
        n = len(self.candidates) + 1
        candidate = PersistedVisualCandidate(
            candidate_id=f"TEST-CAND-{n}", asset_key=f"TEST-ASSET-{n}", asset_record_id=f"rec-test-{n}",
            job_key=job.job_key, iteration=iteration, provider_id=rendered.provider_id, model=rendered.model,
            preview_url=rendered.temporary_url or f"https://example.test/{n}.png", parent_candidate_id=parent_candidate_id,
            status="GENERATED", created_at="2000-01-01T00:00:00Z",
        )
        self.candidates.append(candidate)
        return candidate

    def mark_system_pass(self, candidate: PersistedVisualCandidate, findings: str) -> PersistedVisualCandidate:
        updated = PersistedVisualCandidate(
            candidate.candidate_id,
            candidate.asset_key,
            candidate.asset_record_id,
            candidate.job_key,
            candidate.iteration,
            candidate.provider_id,
            candidate.model,
            candidate.preview_url,
            candidate.parent_candidate_id,
            "SYSTEM_PASS",
            candidate.created_at,
        )
        self.candidates = [updated if c.candidate_id == candidate.candidate_id else c for c in self.candidates]
        return updated
