from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from bloom_engine.api.app import AmaApiServices, create_app
from bloom_engine.api.authoritative_builder import CatalogAmaRequestBuilder, IntentBuildError
from bloom_engine.api.models import RuntimePreviewBody
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

CURRENT_SCENE_TABLE = "tblipTnwAEA05zs9v"
CURRENT_SCENE_FIELDS = {
    "scene_key": "fldPweqNPJwM8e5FC",
    "arc": "fldpFz4j39XtGoOFk",
    "episode": "fld66HLRpTeZvdmDU",
    "time": "fldyHoqnqks2VaoDg",
    "location": "fld1msBDbtVudey4P",
    "present": "fld5VWkQcajUDmDVh",
    "last_beat": "fldO8KBpPV8DT1m4m",
    "guardrails": "fldJXyTVX7ejF67Yy",
    "location_entity": "fldkRaTXDmB8kUKkC",
    "present_entities": "fldlFXtfSXTKMT19a",
}


@dataclass(slots=True)
class AirtableReadOnlyHTTP:
    """Minimal Airtable transport with no write methods by construction."""

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
                    "User-Agent": "BLOOM-Ama-ReadOnly/0.1",
                },
            )
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
            records.extend(payload.get("records", []))
            offset = payload.get("offset")
            if not offset:
                return records


def _linked_names(value: Any) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    names: list[str] = []
    for item in value:
        if isinstance(item, Mapping):
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                names.append(name.strip())
    return tuple(names)


@dataclass(slots=True)
class AirtableCurrentSceneRepository:
    client: Any

    def load_scene_anchor(self, request: SceneRequest) -> SceneAnchor:
        rows = self.client.list_all(CURRENT_SCENE_TABLE)
        if len(rows) != 1:
            raise RuntimeError(f"Expected exactly one Current Scene row, found {len(rows)}")

        row = rows[0]
        fields = row.get("fields", {})
        arc = str(fields.get(CURRENT_SCENE_FIELDS["arc"], "")).strip()
        if request.arc.strip() != arc:
            raise RuntimeError(
                f"Requested arc does not match active Current Scene: {request.arc!r} != {arc!r}"
            )

        scene_key = str(fields.get(CURRENT_SCENE_FIELDS["scene_key"], "")).strip()
        if not scene_key:
            raise RuntimeError("Current Scene is missing Scene Key")

        location_refs = _linked_names(fields.get(CURRENT_SCENE_FIELDS["location_entity"]))
        present_refs = _linked_names(fields.get(CURRENT_SCENE_FIELDS["present_entities"]))
        location_ref = location_refs[0] if len(location_refs) == 1 else str(
            fields.get(CURRENT_SCENE_FIELDS["location"], "")
        ).strip()

        guardrails_text = str(fields.get(CURRENT_SCENE_FIELDS["guardrails"], "")).strip()
        hard_guardrails = (guardrails_text,) if guardrails_text else ()

        return SceneAnchor(
            scene_key=scene_key,
            arc=arc,
            episode=str(fields.get(CURRENT_SCENE_FIELDS["episode"], "")).strip(),
            time_text=str(fields.get(CURRENT_SCENE_FIELDS["time"], "")).strip(),
            location_ref=location_ref,
            present_character_refs=present_refs,
            last_beat=str(fields.get(CURRENT_SCENE_FIELDS["last_beat"], "")).strip(),
            hard_guardrails=hard_guardrails,
            source_refs=(f"airtable:{CURRENT_SCENE_TABLE}:{row.get('id', 'UNKNOWN')}",),
        )

    def write_runtime_trace(self, trace: Any) -> None:
        # Hosted Ama read/preview deliberately has no durable trace writer.
        return None


class HostedAmaRequestBuilder:
    """Add one reviewed scene-inspection intent; delegate all other reviewed intents."""

    def __init__(self) -> None:
        self._delegate = CatalogAmaRequestBuilder()

    def build_preview(self, body: RuntimePreviewBody) -> SceneRequest:
        if body.mode != "DRY_RUN":
            raise IntentBuildError("external Ama preview is DRY_RUN only")

        normalized = " ".join(body.command.strip().lower().split())
        inspection_markers = (
            "inspect current",
            "inspect the current",
            "active scene",
            "current scene",
            "current aster hollow state",
            "scene pointer",
        )
        if any(marker in normalized for marker in inspection_markers):
            return SceneRequest(
                arc=body.arc,
                command=body.command,
                queries=(),
                mode="DRY_RUN",
                realization="PREVIEW",
                authorization_token=None,
                protected_player_domains=("player_choice", "player_interiority"),
            )

        return self._delegate.build_preview(body)


class SceneInspectionOptions:
    def build(self, packet: Any, request: SceneRequest) -> tuple[EligibleOption, ...]:
        return (
            EligibleOption(
                id="AMA-READ-CURRENT-SCENE",
                actor_ref="AMA",
                summary="Return the verified active Current Scene anchor without changing state.",
                requires_fact_keys=(),
                intended_fact_keys=(),
            ),
        )


class SceneInspectionAthena:
    def decide(self, packet: Any, eligible_options: Sequence[EligibleOption]) -> AthenaDecision:
        if len(eligible_options) != 1:
            raise RuntimeError("Read-only scene inspection expected exactly one eligible option")
        return AthenaDecision(
            selected_option_id=eligible_options[0].id,
            fulcrum="READ_ONLY_INSPECTION",
            result="ACT",
            basis_fact_keys=(),
            intended_fact_keys=(),
            reason_code="AUTHORITATIVE_CURRENT_SCENE_READ",
        )


class SceneInspectionCalliope:
    def render(self, packet: Any, decision: AthenaDecision, selected_option: EligibleOption | None) -> CalliopeRender:
        anchor = packet.anchor
        present = ", ".join(anchor.present_character_refs) if anchor.present_character_refs else "not linked"
        guardrails = "\n".join(anchor.hard_guardrails) if anchor.hard_guardrails else "none recorded"
        text = (
            "Verified active Aster Hollow scene from the live BLOOM Current Scene projection:\n"
            f"Scene Key: {anchor.scene_key}\n"
            f"Episode: {anchor.episode}\n"
            f"In-world time: {anchor.time_text}\n"
            f"Location: {anchor.location_ref}\n"
            f"Present character refs: {present}\n"
            f"Last established beat: {anchor.last_beat}\n"
            f"Hard guardrails: {guardrails}\n"
            "This is a read-only runtime preview. Nothing was persisted."
        )
        return CalliopeRender(
            text=text,
            claims=(),
            source_decision_option_id=selected_option.id if selected_option else None,
        )


def build_live_services(client: Any) -> AmaApiServices:
    repository = AirtableCurrentSceneRepository(client)
    runner = RuntimeRunner(
        RunnerDeps(
            repository=repository,
            gateway=CoreGateway(),
            options=SceneInspectionOptions(),
            athena=SceneInspectionAthena(),
            calliope=SceneInspectionCalliope(),
            clio=GatedClio(InMemoryClioTransactionStore()),
        )
    )
    return AmaApiServices(runner=runner, request_builder=HostedAmaRequestBuilder())


def build_app_from_env():
    bearer = os.environ["BLOOM_API_BEARER_TOKEN"]
    airtable_token = os.environ["AIRTABLE_PAT"]
    base_id = os.getenv("BLOOM_AIRTABLE_BASE_ID", "appNhl43NzKfbsTAw")
    client = AirtableReadOnlyHTTP(base_id=base_id, token=airtable_token)
    return create_app(services=build_live_services(client), bearer_token=bearer)
