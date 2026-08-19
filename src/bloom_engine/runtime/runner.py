from __future__ import annotations

import json
import re
from dataclasses import dataclass

from bloom_engine.pantheon.gateway import CoreGateway
from bloom_engine.runtime.adrasteia import postflight_clio, preflight, validate_athena, validate_calliope
from bloom_engine.runtime.compiler import compile_context
from bloom_engine.runtime.contracts import AthenaAdapter, CalliopeAdapter, ClioPort, OptionBuilder, RuntimeRepository
from bloom_engine.runtime.models import (
    ClioHandoff,
    ClioManifest,
    RunnerOutput,
    RuntimeTrace,
    SceneRequest,
)


def _slug(command: str) -> str:
    normalized = re.sub(r"[^A-Z0-9]+", "-", command.strip().upper()).strip("-")
    return normalized or "REQUEST"


def _run_key(scene_key: str, command: str) -> str:
    return f"RUN::{scene_key}::{_slug(command)}"


def _transaction_key(run_key: str) -> str:
    return f"TXN::{run_key}"


@dataclass(slots=True)
class RunnerDeps:
    repository: RuntimeRepository
    gateway: CoreGateway
    options: OptionBuilder
    athena: AthenaAdapter
    calliope: CalliopeAdapter
    clio: ClioPort


class RuntimeRunner:
    """Clean Python port of the certified Runtime v0.3.1 execution spine.

    The Runner is connective infrastructure. It compiles owner outputs, runs
    deterministic integrity gates, invokes ATHENA/CALLIOPE adapters, and hands
    structured persistence intent to CLIO. It owns no sovereign predicate.
    """

    def __init__(self, deps: RunnerDeps):
        self.deps = deps

    def _write_trace(self, trace: RuntimeTrace) -> None:
        writer = getattr(self.deps.repository, "write_runtime_trace", None)
        if callable(writer):
            writer(trace)

    def run(self, request: SceneRequest) -> RunnerOutput:
        anchor = self.deps.repository.load_scene_anchor(request)
        trace = RuntimeTrace(run_key=_run_key(anchor.scene_key, request.command), request=request)

        try:
            packet = compile_context(request, anchor, self.deps.gateway)
            trace.packet = packet

            pre = preflight(packet)
            trace.adrasteia_preflight = pre
            if pre.status == "BLOCKED":
                trace.final_status = "BLOCKED"
                self._write_trace(trace)
                return RunnerOutput(status="BLOCKED", trace=trace)

            options = tuple(self.deps.options.build(packet, request))
            trace.eligible_options = options

            decision = self.deps.athena.decide(packet, options)
            trace.athena = decision
            athena_gate = validate_athena(packet, options, decision)
            trace.adrasteia_postflight = athena_gate
            if athena_gate.status == "BLOCKED":
                trace.final_status = "BLOCKED"
                self._write_trace(trace)
                return RunnerOutput(status="BLOCKED", trace=trace)

            if decision.result == "PLAYER_DECISION_REQUIRED":
                trace.final_status = "PLAYER_DECISION_REQUIRED"
                self._write_trace(trace)
                return RunnerOutput(status="PLAYER_DECISION_REQUIRED", trace=trace)

            selected = (
                next((option for option in options if option.id == decision.selected_option_id), None)
                if decision.selected_option_id
                else None
            )

            render = self.deps.calliope.render(packet, decision, selected)
            trace.calliope = render
            calliope_gate = validate_calliope(packet, decision, render)
            trace.adrasteia_postflight = calliope_gate
            if calliope_gate.status == "BLOCKED":
                trace.final_status = "BLOCKED"
                self._write_trace(trace)
                return RunnerOutput(status="BLOCKED", trace=trace)

            realized = request.mode == "LIVE_PLAY" and request.realization == "COMMIT_AFTER_RENDER"
            handoff = ClioHandoff(
                transaction_key=_transaction_key(trace.run_key),
                packet_key=packet.packet_key,
                arc=request.arc,
                source_run=trace.run_key,
                expected_pre_state_digest=json.dumps(
                    {
                        "scene_key": packet.anchor.scene_key,
                        "source_refs": list(packet.source_snapshot_refs),
                    },
                    sort_keys=True,
                ),
                # Production story writes remain deliberately closed in this port.
                # The future transaction executor must build this manifest from a
                # realized, validated action rather than free-text rendering.
                manifest=ClioManifest(
                    readback_assertions=(
                        "No Event row appended.",
                        "No owner-state delta applied.",
                    )
                ),
                realized=realized,
                persistence_authorized=realized and bool(request.authorization_token),
                authorization_token=request.authorization_token,
            )
            clio = self.deps.clio.commit(handoff)
            trace.clio = clio
            clio_gate = postflight_clio(clio)
            trace.adrasteia_postflight = clio_gate
            if clio_gate.status == "BLOCKED":
                trace.final_status = "BLOCKED"
                self._write_trace(trace)
                return RunnerOutput(status="BLOCKED", trace=trace)

            trace.final_status = "COMPLETE"
            self._write_trace(trace)
            return RunnerOutput(status="COMPLETE", text=render.text, trace=trace)

        except Exception:
            trace.final_status = "FAILED"
            self._write_trace(trace)
            raise
