from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
    started_at: str | None = None
    updated_at: str | None = None
    recovery_required: bool = False


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
    def pause_orphaned_running_jobs(self) -> tuple[VisualJobState, ...]: ...


@dataclass(slots=True)
class AirtableVisualJobStore:
    """Durable operational job registry backed by BLOOM Visual Batches.

    Visual Batches is an orchestration table, not canon. A generated job reaches
    `Reviewing` when APOLLO finishes. It never becomes `Complete` merely because
    SYSTEM_PASS succeeded; `Complete` remains reserved for explicit human review.

    Crash recovery is fail-safe rather than automatic: if a host restarts while a
    job is RUNNING, the replacement process marks that job RECOVERY_REQUIRED and
    Paused. It never resubmits the paid renderer automatically, because the prior
    process may have spent money immediately before it died.
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
    def _notes(record: dict[str, Any]) -> dict[str, Any]:
        fields = record.get("fields") or {}
        raw = str(fields.get(F["notes"], "") or "").strip()
        if not raw:
            return {}
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}

    @classmethod
    def _decode(cls, record: dict[str, Any]) -> VisualJobState:
        fields = record.get("fields") or {}
        notes = cls._notes(record)
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
            started_at=str(notes.get("started_at") or record.get("createdTime") or "") or None,
            updated_at=str(notes.get("updated_at") or "") or None,
            recovery_required=bool(notes.get("recovery_required", False)),
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
        now = _now()
        notes = {
            "schema": "APOLLO-VISUAL-JOB-v1",
            "request_key": request_key,
            "runtime_status": "RUNNING",
            "subject_id": subject_id,
            "subject_name": subject_name,
            "started_at": now,
            "updated_at": now,
            "recovery_required": False,
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

    def _update(
        self,
        visual_job_id: str,
        *,
        runtime_status: str,
        batch_status: str,
        result: dict[str, Any] | None,
        error: str | None,
        review: str,
        recovery_required: bool = False,
    ) -> VisualJobState:
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
            "started_at": previous.started_at,
            "updated_at": _now(),
            "recovery_required": recovery_required,
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
        batch_status = "Paused" if status in {"FAILED", "BLOCKED"} else "Reviewing"
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

    def pause_orphaned_running_jobs(self) -> tuple[VisualJobState, ...]:
        recovered: list[VisualJobState] = []
        for row in self._list_all():
            fields = row.get("fields") or {}
            notes = self._notes(row)
            if notes.get("schema") != "APOLLO-VISUAL-JOB-v1":
                continue
            if str(notes.get("runtime_status") or "") != "RUNNING":
                continue
            visual_job_id = str(fields.get(F["key"], ""))
            if not visual_job_id:
                continue
            recovered.append(self._update(
                visual_job_id,
                runtime_status="RECOVERY_REQUIRED",
                batch_status="Paused",
                result=None,
                error="HOST_RESTART_DURING_VISUAL_JOB",
                recovery_required=True,
                review=(
                    "APOLLO host restarted while this paid job was RUNNING. The job was paused, not retried. "
                    "Inspect persisted candidates/provider history before explicitly authorizing any new spend."
                ),
            ))
        return tuple(recovered)

    def get(self, visual_job_id: str) -> VisualJobState | None:
        row = self._find_record(visual_job_id)
        return self._decode(row) if row else None


class InMemoryVisualJobStore:
    def __init__(self) -> None:
        self.states: dict[str, VisualJobState] = {}

    def start(self, *, visual_job_id: str, request_key: str, arc: str, subject_id: str, subject_name: str, command: str, shot_list: tuple[str, ...], required_anchor_assets: tuple[str, ...]) -> VisualJobState:
        if visual_job_id in self.states:
            raise RuntimeError(f"VISUAL_JOB_ALREADY_EXISTS:{visual_job_id}")
        now = _now()
        state = VisualJobState(visual_job_id, request_key, "RUNNING", subject_id, subject_name, started_at=now, updated_at=now)
        self.states[visual_job_id] = state
        return state

    def finish(self, visual_job_id: str, *, status: str, result: dict[str, Any]) -> VisualJobState:
        prior = self.states[visual_job_id]
        state = VisualJobState(
            prior.visual_job_id, prior.request_key, status, prior.subject_id, prior.subject_name,
            result=result, started_at=prior.started_at, updated_at=_now(),
        )
        self.states[visual_job_id] = state
        return state

    def fail(self, visual_job_id: str, *, error: str) -> VisualJobState:
        prior = self.states[visual_job_id]
        state = VisualJobState(
            prior.visual_job_id, prior.request_key, "FAILED", prior.subject_id, prior.subject_name,
            error=error[:1500], started_at=prior.started_at, updated_at=_now(),
        )
        self.states[visual_job_id] = state
        return state

    def pause_orphaned_running_jobs(self) -> tuple[VisualJobState, ...]:
        recovered: list[VisualJobState] = []
        for job_id, prior in list(self.states.items()):
            if prior.status != "RUNNING":
                continue
            state = VisualJobState(
                prior.visual_job_id,
                prior.request_key,
                "RECOVERY_REQUIRED",
                prior.subject_id,
                prior.subject_name,
                error="HOST_RESTART_DURING_VISUAL_JOB",
                started_at=prior.started_at,
                updated_at=_now(),
                recovery_required=True,
            )
            self.states[job_id] = state
            recovered.append(state)
        return tuple(recovered)

    def get(self, visual_job_id: str) -> VisualJobState | None:
        return self.states.get(visual_job_id)
