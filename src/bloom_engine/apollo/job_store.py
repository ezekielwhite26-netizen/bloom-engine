from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol


VISUAL_BATCHES = "tbl8POAF2SdnyRh1g"
F = {
    "key": "fldXxYz80tPNzC0rx",
    "name": "fldEUuWW0PprnpZxb",
    "arc": "fldS32XvshRl4DVua",
    "purpose": "fldgf13oP8J85odpf",
    "canon": "fldcR36qhEJlYXFAW",
    "brief": "fldvyWLttZ8s6aNbi",
    "shot_list": "fldyYisuRtSN3giOU",
    "continuity": "fldNDuWfP0uKWb6C9",
    "anchors": "fldETTWUrV860XfZE",
    "variation": "fldIRCZfnsIhUexUH",
    "era": "fldyZdBRifQLWC0AU",
    "status": "fld0lJ2jhbHasRCVi",
    "review": "fldnPrS4Y8PCgzn8J",
    "approved": "fldZeahnkuf4RWFQ6",
    "rejected": "flddmARt9qUE2loYC",
    "provenance": "fldMfzUaeAhaanxJl",
    "notes": "fldOnuoGHepMoXyGP",
}


@dataclass(frozen=True, slots=True)
class VisualJobState:
    visual_job_id: str
    request_key: str
    status: str
    subject_id: str
    subject_name: str
    result: dict[str, Any] | None = None
    error: str | None = None
    record_id: str | None = None


class VisualJobStore(Protocol):
    def start(
        self,
        *,
        visual_job_id: str,
        request_key: str,
        arc: str,
        subject_id: str,
        subject_name: str,
        command: str,
        shot_list: tuple[str, ...],
        required_anchor_assets: tuple[str, ...],
    ) -> VisualJobState: ...

    def finish(self, visual_job_id: str, *, status: str, result: dict[str, Any]) -> VisualJobState: ...
    def fail(self, visual_job_id: str, *, error: str) -> VisualJobState: ...
    def get(self, visual_job_id: str) -> VisualJobState | None: ...


@dataclass(slots=True)
class AirtableVisualJobStore:
    """Durable operational job registry backed by BLOOM Visual Batches.

    Visual Batches is an orchestration table, not canon. A generated job reaches
    `Reviewing` when APOLLO finishes. It never becomes `Complete` merely because
    SYSTEM_PASS succeeded; `Complete` remains reserved for explicit human review.
    """

    base_id: str
    token: str
    timeout_seconds: int = 30
    api_base: str = "https://api.airtable.com/v0"

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
            },
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _table_url(self) -> str:
        table = urllib.parse.quote(VISUAL_BATCHES, safe="")
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

    @staticmethod
    def _decode(record: dict[str, Any]) -> VisualJobState:
        fields = record.get("fields") or {}
        notes_raw = str(fields.get(F["notes"], "") or "").strip()
        notes: dict[str, Any] = {}
        if notes_raw:
            try:
                decoded = json.loads(notes_raw)
                if isinstance(decoded, dict):
                    notes = decoded
            except json.JSONDecodeError:
                notes = {}
        status_value = fields.get(F["status"])
        if isinstance(status_value, dict):
            batch_status = str(status_value.get("name") or "")
        else:
            batch_status = str(status_value or "")
        result = notes.get("result") if isinstance(notes.get("result"), dict) else None
        error = notes.get("error") if isinstance(notes.get("error"), str) else None
        return VisualJobState(
            visual_job_id=str(fields.get(F["key"], "")),
            request_key=str(notes.get("request_key") or ""),
            status=str(notes.get("runtime_status") or batch_status or "UNKNOWN"),
            subject_id=str(notes.get("subject_id") or ""),
            subject_name=str(notes.get("subject_name") or fields.get(F["name"], "")),
            result=result,
            error=error,
            record_id=str(record.get("id") or "") or None,
        )

    def _find_record(self, visual_job_id: str) -> dict[str, Any] | None:
        matches = [
            row for row in self._list_all()
            if str((row.get("fields") or {}).get(F["key"], "")) == visual_job_id
        ]
        if len(matches) > 1:
            raise RuntimeError(f"DUPLICATE_VISUAL_JOB_ID:{visual_job_id}")
        return matches[0] if matches else None

    def start(
        self,
        *,
        visual_job_id: str,
        request_key: str,
        arc: str,
        subject_id: str,
        subject_name: str,
        command: str,
        shot_list: tuple[str, ...],
        required_anchor_assets: tuple[str, ...],
    ) -> VisualJobState:
        if self._find_record(visual_job_id) is not None:
            raise RuntimeError(f"VISUAL_JOB_ALREADY_EXISTS:{visual_job_id}")
        notes = {
            "schema": "APOLLO-VISUAL-JOB-v1",
            "request_key": request_key,
            "runtime_status": "RUNNING",
            "subject_id": subject_id,
            "subject_name": subject_name,
            "requires_human_approval": True,
            "result": None,
            "error": None,
        }
        fields = {
            F["key"]: visual_job_id,
            F["name"]: f"APOLLO — {subject_name} — {request_key[-12:]}",
            F["arc"]: arc,
            F["purpose"]: "Other",
            F["canon"]: f"APOLLO authority packet for {subject_id}. Renderers consume authority; they do not originate it.",
            F["brief"]: command,
            F["shot_list"]: "\n".join(shot_list),
            F["continuity"]: "Field-specific authority only; generated open fields remain non-canon; SYSTEM_PASS still requires human review.",
            F["anchors"]: "\n".join(required_anchor_assets),
            F["variation"]: "Repair failing fields only; preserve passing fields unless physically necessary to fix a failure.",
            F["status"]: "Generating",
            F["provenance"]: "APOLLO Visual Director runtime job. Operational record only; not canon.",
            F["notes"]: json.dumps(notes, separators=(",", ":"), ensure_ascii=False),
        }
        response = self._request(
            self._table_url() + "?returnFieldsByFieldId=true",
            method="POST",
            payload={"records": [{"fields": fields}], "typecast": False},
        )
        return self._decode(response["records"][0])

    def _update(self, visual_job_id: str, *, runtime_status: str, batch_status: str, result: dict[str, Any] | None, error: str | None, review: str) -> VisualJobState:
        row = self._find_record(visual_job_id)
        if row is None:
            raise RuntimeError(f"VISUAL_JOB_NOT_FOUND:{visual_job_id}")
        previous = self._decode(row)
        notes = {
            "schema": "APOLLO-VISUAL-JOB-v1",
            "request_key": previous.request_key,
            "runtime_status": runtime_status,
            "subject_id": previous.subject_id,
            "subject_name": previous.subject_name,
            "requires_human_approval": True,
            "result": result,
            "error": error,
        }
        record_id = str(row["id"])
        payload = self._request(
            f"{self._table_url()}/{record_id}?returnFieldsByFieldId=true",
            method="PATCH",
            payload={"fields": {
                F["status"]: batch_status,
                F["review"]: review,
                F["notes"]: json.dumps(notes, separators=(",", ":"), ensure_ascii=False),
            }},
        )
        return self._decode(payload)

    def finish(self, visual_job_id: str, *, status: str, result: dict[str, Any]) -> VisualJobState:
        if status == "FAILED":
            batch_status = "Paused"
        elif status == "BLOCKED":
            batch_status = "Paused"
        else:
            # SYSTEM_PASS is deliberately Reviewing, never Complete.
            batch_status = "Reviewing"
        review = (
            f"APOLLO runtime finished with {status}. "
            "Human review is still required; no candidate is Approved or Gold by this status alone."
        )
        return self._update(
            visual_job_id,
            runtime_status=status,
            batch_status=batch_status,
            result=result,
            error=None,
            review=review,
        )

    def fail(self, visual_job_id: str, *, error: str) -> VisualJobState:
        safe_error = error[:1500]
        return self._update(
            visual_job_id,
            runtime_status="FAILED",
            batch_status="Paused",
            result=None,
            error=safe_error,
            review=f"APOLLO runtime failed before human review: {safe_error}",
        )

    def get(self, visual_job_id: str) -> VisualJobState | None:
        row = self._find_record(visual_job_id)
        return self._decode(row) if row else None


class InMemoryVisualJobStore:
    def __init__(self) -> None:
        self.states: dict[str, VisualJobState] = {}

    def start(self, *, visual_job_id: str, request_key: str, arc: str, subject_id: str, subject_name: str, command: str, shot_list: tuple[str, ...], required_anchor_assets: tuple[str, ...]) -> VisualJobState:
        if visual_job_id in self.states:
            raise RuntimeError(f"VISUAL_JOB_ALREADY_EXISTS:{visual_job_id}")
        state = VisualJobState(visual_job_id, request_key, "RUNNING", subject_id, subject_name)
        self.states[visual_job_id] = state
        return state

    def finish(self, visual_job_id: str, *, status: str, result: dict[str, Any]) -> VisualJobState:
        prior = self.states[visual_job_id]
        state = VisualJobState(prior.visual_job_id, prior.request_key, status, prior.subject_id, prior.subject_name, result=result)
        self.states[visual_job_id] = state
        return state

    def fail(self, visual_job_id: str, *, error: str) -> VisualJobState:
        prior = self.states[visual_job_id]
        state = VisualJobState(prior.visual_job_id, prior.request_key, "FAILED", prior.subject_id, prior.subject_name, error=error[:1500])
        self.states[visual_job_id] = state
        return state

    def get(self, visual_job_id: str) -> VisualJobState | None:
        return self.states.get(visual_job_id)
