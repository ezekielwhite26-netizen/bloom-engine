from __future__ import annotations

import hashlib
import json
import logging
import os
import unicodedata
import urllib.parse
import urllib.request
from dataclasses import dataclass
from hmac import compare_digest
from typing import Any, Sequence

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field

from bloom_engine.pantheon.gateway import CoreGateway
from bloom_engine.runtime import (
    AthenaDecision,
    CalliopeRender,
    EligibleOption,
    GatedClio,
    InMemoryClioTransactionStore,
    RunnerDeps,
    RuntimeRunner,
    SceneAnchor,
    SceneRequest,
)
from bloom_engine.runtime.manuscript import (
    ManuscriptContextRepository,
    ManuscriptSessionStore,
    review_manuscript,
)

API_VERSION = "AMA-BLOOM-API-v0.3-manuscript-read"
DEFAULT_BEARER_SHA256 = "23060d0feb513d330823bc9762667e11982848d8cf0b68b36972a71233257b36"
CURRENT_SCENE_TABLE = "tblipTnwAEA05zs9v"
SCENE_F = {
    "key": "fldPweqNPJwM8e5FC",
    "arc": "fldpFz4j39XtGoOFk",
    "episode": "fld66HLRpTeZvdmDU",
    "time": "fldyHoqnqks2VaoDg",
    "location": "fld1msBDbtVudey4P",
    "present": "fld5VWkQcajUDmDVh",
    "last_beat": "fldO8KBpPV8DT1m4m",
    "guardrails": "fldJXyTVX7ejF67Yy",
}

logger = logging.getLogger("uvicorn.error")


def _token_fingerprint(value: str | None) -> str:
    if not value:
        return "NONE"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]


def _normalize_bearer(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(
        ch for ch in normalized
        if not ch.isspace() and unicodedata.category(ch) != "Cf"
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class RuntimePreviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arc: str = Field(min_length=1)
    command: str = Field(min_length=1)
    mode: str = "DRY_RUN"
    requested_actor_ref: str | None = None
    requested_target_location_ref: str | None = None
    requested_object_ref: str | None = None
    visual_requested: bool = False


class ManuscriptContextBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arc: str = Field(min_length=1)
    command: str = Field(min_length=1)
    scene_or_chapter: str = Field(min_length=1)
    temporal_scope: str = "HISTORICAL_MANUSCRIPT"
    character_names: list[str] = Field(default_factory=list)
    location_names: list[str] = Field(default_factory=list)


class ManuscriptClaimBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1)
    key: str = Field(min_length=1)


class ManuscriptReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_id: str = Field(min_length=1)
    phase: str
    claims: list[ManuscriptClaimBody] = Field(default_factory=list)
    reader_new_subjects: list[str] = Field(default_factory=list)
    oriented_subjects: list[str] = Field(default_factory=list)
    reader_ledger_commit_requested: bool = False


@dataclass(slots=True)
class AirtableReadOnlyHTTP:
    base_id: str
    token: str
    timeout_seconds: int = 20

    def list_all(self, table_id: str) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        offset: str | None = None
        while True:
            table = urllib.parse.quote(table_id, safe="")
            query = {"returnFieldsByFieldId": "true"}
            if offset:
                query["offset"] = offset
            url = f"https://api.airtable.com/v0/{self.base_id}/{table}?" + urllib.parse.urlencode(query)
            request = urllib.request.Request(
                url,
                method="GET",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "User-Agent": "BLOOM-Ama-ReadOnly/0.3",
                },
            )
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            records.extend(payload.get("records", []))
            offset = payload.get("offset")
            if not offset:
                return records


def build_airtable_client() -> AirtableReadOnlyHTTP:
    token = os.getenv("AIRTABLE_PAT")
    if not token:
        raise RuntimeError("AIRTABLE_PAT is required for live BLOOM read access")
    base_id = os.getenv("BLOOM_AIRTABLE_BASE_ID", "appNhl43NzKfbsTAw")
    return AirtableReadOnlyHTTP(base_id=base_id, token=token)


@dataclass(slots=True)
class CurrentSceneRepository:
    client: AirtableReadOnlyHTTP

    def load_scene_anchor(self, request: SceneRequest) -> SceneAnchor:
        rows = self.client.list_all(CURRENT_SCENE_TABLE)
        if len(rows) != 1:
            raise RuntimeError(f"Expected exactly one Current Scene row, found {len(rows)}")
        row = rows[0]
        fields = row.get("fields", {})

        arc = str(fields.get(SCENE_F["arc"], "")).strip()
        if request.arc.strip() != arc:
            raise RuntimeError(
                f"Requested arc does not match active Current Scene: {request.arc!r} != {arc!r}"
            )

        scene_key = str(fields.get(SCENE_F["key"], "")).strip()
        if not scene_key:
            raise RuntimeError("Current Scene is missing Scene Key")

        present_text = str(fields.get(SCENE_F["present"], "")).strip()
        present = tuple(part.strip() for part in present_text.split(";") if part.strip())
        guardrails = str(fields.get(SCENE_F["guardrails"], "")).strip()

        return SceneAnchor(
            scene_key=scene_key,
            arc=arc,
            episode=str(fields.get(SCENE_F["episode"], "")).strip(),
            time_text=str(fields.get(SCENE_F["time"], "")).strip(),
            location_ref=str(fields.get(SCENE_F["location"], "")).strip(),
            present_character_refs=present,
            last_beat=str(fields.get(SCENE_F["last_beat"], "")).strip(),
            hard_guardrails=(guardrails,) if guardrails else (),
            source_refs=(f"airtable:{CURRENT_SCENE_TABLE}:{row.get('id', 'UNKNOWN')}",),
        )

    def write_runtime_trace(self, trace: Any) -> None:
        return None


class InspectionOptions:
    def build(self, packet: Any, request: SceneRequest) -> tuple[EligibleOption, ...]:
        return (
            EligibleOption(
                id="AMA-READ-CURRENT-SCENE",
                actor_ref="AMA",
                summary="Return the verified active Current Scene anchor without changing state.",
            ),
        )


class InspectionAthena:
    def decide(self, packet: Any, eligible_options: Sequence[EligibleOption]) -> AthenaDecision:
        if len(eligible_options) != 1:
            raise RuntimeError("Scene inspection expected exactly one eligible option")
        return AthenaDecision(
            selected_option_id=eligible_options[0].id,
            fulcrum="READ_ONLY_INSPECTION",
            result="ACT",
            reason_code="AUTHORITATIVE_CURRENT_SCENE_READ",
        )


class InspectionCalliope:
    def render(self, packet: Any, decision: AthenaDecision, selected_option: EligibleOption | None) -> CalliopeRender:
        anchor = packet.anchor
        present = ", ".join(anchor.present_character_refs) if anchor.present_character_refs else "none recorded"
        guardrails = "\n".join(anchor.hard_guardrails) if anchor.hard_guardrails else "none recorded"
        return CalliopeRender(
            text=(
                "Verified active Aster Hollow scene from live BLOOM Current Scene:\n"
                f"Scene Key: {anchor.scene_key}\n"
                f"Episode: {anchor.episode}\n"
                f"In-world time: {anchor.time_text}\n"
                f"Location: {anchor.location_ref}\n"
                f"Present: {present}\n"
                f"Last established beat: {anchor.last_beat}\n"
                f"Hard guardrails: {guardrails}\n"
                "Read-only preview: nothing was persisted."
            ),
            claims=(),
            source_decision_option_id=selected_option.id if selected_option else None,
        )


def build_runner() -> RuntimeRunner:
    repository = CurrentSceneRepository(build_airtable_client())
    return RuntimeRunner(
        RunnerDeps(
            repository=repository,
            gateway=CoreGateway(),
            options=InspectionOptions(),
            athena=InspectionAthena(),
            calliope=InspectionCalliope(),
            clio=GatedClio(InMemoryClioTransactionStore()),
        )
    )


def build_manuscript_repository() -> ManuscriptContextRepository:
    return ManuscriptContextRepository(build_airtable_client())


manuscript_sessions = ManuscriptSessionStore(ttl_seconds=3600)


app = FastAPI(
    title="BLOOM / Ama Live Read Runtime",
    version="0.3.0",
    description="Authenticated read-only Ama surface backed by BLOOM runtime and manuscript authoring evidence.",
)
bearer = HTTPBearer(auto_error=False)


def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
    legacy_expected = _normalize_bearer(os.getenv("BLOOM_API_BEARER_TOKEN"))
    configured_hash = (os.getenv("BLOOM_API_BEARER_TOKEN_SHA256") or "").strip().lower()
    expected_hash = configured_hash or (_sha256_text(legacy_expected) if legacy_expected else DEFAULT_BEARER_SHA256)

    received_raw = credentials.credentials if credentials is not None else None
    received = _normalize_bearer(received_raw)
    scheme = credentials.scheme if credentials is not None else None

    if credentials is None or (scheme or "").lower() != "bearer":
        logger.warning(
            "AMA_AUTH_DIAG result=missing hash_mode=True expected_configured=True received_present=%s scheme=%s",
            bool(received_raw),
            scheme or "NONE",
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer credentials")

    received_hash = _sha256_text(received)
    if not compare_digest(received_hash, expected_hash):
        logger.warning(
            "AMA_AUTH_DIAG result=mismatch mode=sha256 expected_fp=%s received_fp=%s received_len_raw=%s received_len_norm=%s",
            expected_hash[:12],
            received_hash[:12],
            len(received_raw or ""),
            len(received),
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer credentials")

    logger.info(
        "AMA_AUTH_DIAG result=match mode=sha256 token_fp=%s token_len=%s",
        expected_hash[:12],
        len(received),
    )


def _compact_runtime_trace(trace: Any, request: SceneRequest, status_text: str) -> dict[str, Any]:
    """Expose only the small proof envelope needed by the GPT Action."""
    if isinstance(trace, dict):
        return {
            "run_key": str(trace.get("run_key", "AMA-READ-PREVIEW")),
            "final_status": str(trace.get("final_status", status_text)),
            "request": {
                "arc": request.arc,
                "command": request.command,
                "mode": request.mode,
                "realization": request.realization,
            },
        }

    compact: dict[str, Any] = {
        "run_key": str(getattr(trace, "run_key", "AMA-READ-PREVIEW")),
        "final_status": str(getattr(trace, "final_status", status_text)),
        "request": {
            "arc": request.arc,
            "command": request.command,
            "mode": request.mode,
            "realization": request.realization,
        },
    }

    packet = getattr(trace, "packet", None)
    if packet is not None:
        compact["packet"] = {
            "packet_key": str(getattr(packet, "packet_key", "")),
            "contract_version": str(getattr(packet, "contract_version", "")),
            "blockers": list(getattr(packet, "blockers", ()) or ()),
            "warnings": list(getattr(packet, "warnings", ()) or ()),
        }

    athena = getattr(trace, "athena", None)
    if athena is not None:
        compact["athena"] = {
            "selected_option_id": getattr(athena, "selected_option_id", None),
            "fulcrum": str(getattr(athena, "fulcrum", "")),
            "result": str(getattr(athena, "result", "")),
            "reason_code": str(getattr(athena, "reason_code", "")),
        }

    clio = getattr(trace, "clio", None)
    if clio is not None:
        compact["clio"] = {
            "status": str(getattr(clio, "status", "")),
            "transaction_key": str(getattr(clio, "transaction_key", "")),
            "readback_verified": bool(getattr(clio, "readback_verified", False)),
            "message": str(getattr(clio, "message", "")),
        }
    else:
        compact["clio"] = {
            "status": "NOT_INVOKED",
            "transaction_key": "",
            "readback_verified": False,
            "message": "Read-only preview; no canonical persistence was attempted.",
        }

    return compact


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "ama-runtime-live-read",
        "api_version": API_VERSION,
        "airtable_read_configured": bool(os.getenv("AIRTABLE_PAT")),
        "bearer_auth_configured": True,
        "runtime_preview": True,
        "manuscript_context": True,
        "manuscript_review": True,
        "persistence_live": False,
    }


@app.get("/v1/capabilities", dependencies=[Depends(require_auth)])
def capabilities() -> dict[str, Any]:
    return {
        "api_version": API_VERSION,
        "runtime_preview": True,
        "runtime_commit": False,
        "manuscript_context": True,
        "manuscript_review": True,
        "manuscript_commit": False,
        "reader_ledger_commit": False,
        "persistence_live": False,
        "raw_sovereign_query_api": False,
        "client_may_supply_authoritative_evidence": False,
        "model_may_mint_write_authority": False,
    }


@app.post("/v1/runtime/preview", dependencies=[Depends(require_auth)])
def runtime_preview(body: RuntimePreviewBody) -> dict[str, Any]:
    if body.mode != "DRY_RUN":
        raise HTTPException(status_code=422, detail="Ama live-read preview is DRY_RUN only")

    normalized = " ".join(body.command.lower().split())
    if not any(marker in normalized for marker in ("current scene", "current aster hollow state", "active scene", "scene pointer")):
        raise HTTPException(status_code=422, detail="This live-read deployment currently supports Current Scene inspection only")

    request = SceneRequest(
        arc=body.arc,
        command=body.command,
        queries=(),
        mode="DRY_RUN",
        realization="PREVIEW",
        authorization_token=None,
        protected_player_domains=("player_choice", "player_interiority"),
    )
    try:
        output = build_runner().run(request)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=f"Runtime safety boundary rejected request: {exc}") from exc

    return {
        "api_version": API_VERSION,
        "status": output.status,
        "text": output.text,
        "trace": _compact_runtime_trace(output.trace, request, output.status),
    }


@app.post("/v1/manuscript/context", dependencies=[Depends(require_auth)])
def manuscript_context(body: ManuscriptContextBody) -> dict[str, Any]:
    if body.temporal_scope not in {"CURRENT_SCENE", "HISTORICAL_MANUSCRIPT"}:
        raise HTTPException(status_code=422, detail="temporal_scope must be CURRENT_SCENE or HISTORICAL_MANUSCRIPT")
    if not body.character_names and not body.location_names:
        raise HTTPException(status_code=422, detail="At least one character or location must be requested")

    try:
        context = build_manuscript_repository().build(
            arc=body.arc,
            command=body.command,
            scene_or_chapter=body.scene_or_chapter,
            temporal_scope=body.temporal_scope,
            character_names=tuple(body.character_names),
            location_names=tuple(body.location_names),
        )
    except (RuntimeError, OSError) as exc:
        raise HTTPException(status_code=503, detail=f"Manuscript evidence service unavailable: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if context.get("status") == "BLOCKED":
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Manuscript evidence contract is blocked.",
                "blockers": context.get("blockers", []),
            },
        )

    session = manuscript_sessions.issue(context)
    return {
        "api_version": API_VERSION,
        "context_id": session.context_id,
        "expires_at_epoch": session.expires_at,
        "context": context,
        "story_canon_persisted": False,
        "reader_ledger_committed": False,
        "clio_invoked": False,
    }


@app.post("/v1/manuscript/review", dependencies=[Depends(require_auth)])
def manuscript_review(body: ManuscriptReviewBody) -> dict[str, Any]:
    session = manuscript_sessions.get(body.context_id)
    if session is None:
        raise HTTPException(status_code=410, detail="Manuscript context expired or was not issued by this service")

    try:
        result = review_manuscript(
            session=session,
            phase=body.phase,
            claims=tuple(claim.model_dump() for claim in body.claims),
            reader_new_subjects=tuple(body.reader_new_subjects),
            oriented_subjects=tuple(body.oriented_subjects),
            reader_ledger_commit_requested=body.reader_ledger_commit_requested,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "api_version": API_VERSION,
        **result,
        "clio_invoked": False,
    }
