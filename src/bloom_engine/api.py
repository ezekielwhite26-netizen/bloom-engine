from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from hmac import compare_digest
from typing import Any, Sequence

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.encoders import jsonable_encoder
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

API_VERSION = "AMA-BLOOM-API-v0.2-live-read"
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


class RuntimePreviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arc: str = Field(min_length=1)
    command: str = Field(min_length=1)
    mode: str = "DRY_RUN"
    requested_actor_ref: str | None = None
    requested_target_location_ref: str | None = None
    requested_object_ref: str | None = None
    visual_requested: bool = False


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
                    "User-Agent": "BLOOM-Ama-ReadOnly/0.2",
                },
            )
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            records.extend(payload.get("records", []))
            offset = payload.get("offset")
            if not offset:
                return records


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
        # No hosted durable trace writes in the read-only Ama surface.
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
    token = os.getenv("AIRTABLE_PAT")
    if not token:
        raise RuntimeError("AIRTABLE_PAT is required for live read-only Current Scene access")
    base_id = os.getenv("BLOOM_AIRTABLE_BASE_ID", "appNhl43NzKfbsTAw")
    repository = CurrentSceneRepository(AirtableReadOnlyHTTP(base_id=base_id, token=token))
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


app = FastAPI(
    title="BLOOM / Ama Live Read Runtime",
    version="0.2.0",
    description="Authenticated read-only Ama surface backed by BLOOM Current Scene.",
)
bearer = HTTPBearer(auto_error=False)


def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
    expected = os.getenv("BLOOM_API_BEARER_TOKEN")
    if not expected or credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer credentials")
    if not compare_digest(credentials.credentials, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer credentials")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "ama-runtime-live-read",
        "api_version": API_VERSION,
        "airtable_read_configured": bool(os.getenv("AIRTABLE_PAT")),
        "persistence_live": False,
    }


@app.get("/v1/capabilities", dependencies=[Depends(require_auth)])
def capabilities() -> dict[str, Any]:
    return {
        "api_version": API_VERSION,
        "runtime_preview": True,
        "runtime_commit": False,
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

    return jsonable_encoder(
        {
            "api_version": API_VERSION,
            "status": output.status,
            "text": output.text,
            "trace": output.trace,
        }
    )
