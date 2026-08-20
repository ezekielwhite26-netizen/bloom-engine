from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from bloom_engine.apollo.models import (
    CompiledVisualJob,
    PersistedVisualCandidate,
    RenderedVisual,
    VisualGateStatus,
    VisualQAGate,
    VisualQAReport,
)


def _json_request(url: str, *, method: str = "GET", headers: dict[str, str] | None = None, payload: Any = None, timeout: int = 180) -> Any:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class VisualRenderer(Protocol):
    provider_id: str

    def render(
        self,
        job: CompiledVisualJob,
        *,
        iteration: int,
        previous_candidate: PersistedVisualCandidate | None = None,
        repair_plan: tuple[str, ...] = (),
        preserve: tuple[str, ...] = (),
    ) -> RenderedVisual: ...


class VisualCritic(Protocol):
    def review(
        self,
        job: CompiledVisualJob,
        candidate: PersistedVisualCandidate,
        previous_best: PersistedVisualCandidate | None = None,
    ) -> VisualQAReport: ...


def _renderer_prompt(
    job: CompiledVisualJob,
    previous_candidate: PersistedVisualCandidate | None,
    repair_plan: tuple[str, ...],
    preserve: tuple[str, ...],
) -> str:
    lines = [job.prompt]
    offset = 1
    if previous_candidate is not None:
        lines.append("image 1: current best candidate; edit this candidate rather than redesigning the subject")
        offset = 2
    for index, ref in enumerate(job.references, start=offset):
        controls = ", ".join(ref.controls) or "the authority explicitly recorded for this asset"
        not_controls = ", ".join(ref.does_not_control) or "anything not explicitly established"
        lines.append(f"image {index}: {ref.role}; controls {controls}; does NOT control {not_controls}")
    lines.append("Hard gates: " + " | ".join(job.hard_gates))
    lines.append("Style rules: " + " | ".join(job.style_rules))
    lines.append("Anti-drift: " + " | ".join(job.anti_drift))
    if job.open_fields:
        lines.append("OPEN/presentation-only fields: " + " | ".join(job.open_fields))
    if repair_plan:
        lines.append("Repair ONLY these failures: " + " | ".join(repair_plan))
    if preserve:
        lines.append("Preserve these passing fields: " + " | ".join(preserve))
    lines.append("Never change a passing field just to make the image prettier.")
    lines.append("This is the same established subject, not a new design.")
    return "\n".join(lines)


@dataclass(slots=True)
class Flux2ProRenderer:
    """Pinned FLUX.2 Pro primary renderer.

    Uses the fixed `flux-2-pro` endpoint rather than the preview endpoint. BFL
    delivery URLs are copied to BLOOM storage immediately by the caller.
    """

    api_key: str | None = None
    endpoint: str = "https://api.bfl.ai/v1/flux-2-pro"
    poll_seconds: float = 0.75
    timeout_seconds: int = 180
    width: int = 1024
    height: int = 1536
    provider_id: str = "flux-2-pro"

    def render(self, job: CompiledVisualJob, *, iteration: int, previous_candidate: PersistedVisualCandidate | None = None, repair_plan: tuple[str, ...] = (), preserve: tuple[str, ...] = ()) -> RenderedVisual:
        key = self.api_key or os.getenv("BFL_API_KEY")
        if not key:
            raise RuntimeError("MISSING_ENV:BFL_API_KEY")
        refs = ([previous_candidate.preview_url] if previous_candidate else []) + [ref.uri for ref in job.references if ref.uri]
        if len(refs) > 8:
            raise RuntimeError(f"FLUX_REFERENCE_BUDGET_EXCEEDED:{len(refs)}>8")
        payload: dict[str, Any] = {
            "prompt": _renderer_prompt(job, previous_candidate, repair_plan, preserve),
            "width": self.width,
            "height": self.height,
            "output_format": "png",
        }
        for index, uri in enumerate(refs, start=1):
            payload["input_image" if index == 1 else f"input_image_{index}"] = uri
        headers = {"accept": "application/json", "content-type": "application/json", "x-key": key}
        submitted = _json_request(self.endpoint, method="POST", headers=headers, payload=payload, timeout=self.timeout_seconds)
        polling_url = submitted.get("polling_url")
        if not polling_url:
            raise RuntimeError("FLUX_MISSING_POLLING_URL")
        deadline = time.monotonic() + self.timeout_seconds
        while time.monotonic() < deadline:
            time.sleep(self.poll_seconds)
            result = _json_request(str(polling_url), headers={"accept": "application/json", "x-key": key}, timeout=30)
            status = result.get("status")
            if status == "Ready":
                sample = (result.get("result") or {}).get("sample")
                if not sample:
                    raise RuntimeError("FLUX_READY_WITHOUT_SAMPLE")
                seed = (result.get("result") or {}).get("seed")
                return RenderedVisual(
                    provider_id=self.provider_id,
                    model="flux-2-pro",
                    mime_type="image/png",
                    temporary_url=str(sample),
                    provider_request_id=str(submitted.get("id")) if submitted.get("id") else None,
                    seed=int(seed) if isinstance(seed, int) else None,
                    provider_cost=float(submitted["cost"]) if isinstance(submitted.get("cost"), (int, float)) else None,
                )
            if status in {"Error", "Failed", "Request Moderated", "Content Moderated", "Task not found"}:
                raise RuntimeError(f"FLUX_GENERATION_{status}:{result}")
        raise RuntimeError("FLUX_GENERATION_TIMEOUT")


class GPTImage2Transport(Protocol):
    def edit(self, *, prompt: str, reference_urls: tuple[str, ...]) -> RenderedVisual: ...


@dataclass(slots=True)
class GPTImage2Renderer:
    """Secondary repair renderer behind an injectable GPT Image 2 transport.

    Keeping multipart/download details behind this port avoids coupling APOLLO
    to one SDK. Production transport should pin `gpt-image-2-2026-04-21`.
    """

    transport: GPTImage2Transport
    provider_id: str = "gpt-image-2"

    def render(self, job: CompiledVisualJob, *, iteration: int, previous_candidate: PersistedVisualCandidate | None = None, repair_plan: tuple[str, ...] = (), preserve: tuple[str, ...] = ()) -> RenderedVisual:
        refs = tuple(([previous_candidate.preview_url] if previous_candidate else []) + [ref.uri for ref in job.references if ref.uri])
        return self.transport.edit(prompt=_renderer_prompt(job, previous_candidate, repair_plan, preserve), reference_urls=refs)


@dataclass(slots=True)
class OpenAIVisualCritic:
    api_key: str | None = None
    endpoint: str = "https://api.openai.com/v1/responses"
    model: str = "gpt-5.6"
    timeout_seconds: int = 180

    def review(self, job: CompiledVisualJob, candidate: PersistedVisualCandidate, previous_best: PersistedVisualCandidate | None = None) -> VisualQAReport:
        key = self.api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("MISSING_ENV:OPENAI_API_KEY")
        authority = "\n".join(
            f"reference {i}: {ref.role}; controls {', '.join(ref.controls)}; does NOT control {', '.join(ref.does_not_control)}"
            for i, ref in enumerate(job.references, start=1)
        )
        instructions = "\n".join((
            "You are APOLLO's independent visual conformance critic.",
            "Judge the candidate only against supplied authority and job requirements.",
            "UNKNOWN is correct when the references do not establish a field.",
            "A generated candidate never becomes canon merely by passing review.",
            "Check every hard gate individually; any hard FAIL makes overallPass false.",
            "Repairs target failing fields only. Preserve passing fields.",
            f"Subject: {job.subject_name} ({job.subject_id})",
            f"Output type: {job.output_type}",
            "Hard gates: " + " | ".join(job.hard_gates),
            "Style rules: " + " | ".join(job.style_rules),
            "Anti-drift: " + " | ".join(job.anti_drift),
            "Open fields: " + (" | ".join(job.open_fields) or "none"),
            authority,
        ))
        content: list[dict[str, Any]] = [{"type": "input_text", "text": instructions}]
        for ref in job.references:
            if ref.uri:
                content.append({"type": "input_image", "image_url": ref.uri, "detail": "high"})
        content.append({"type": "input_text", "text": "Candidate to evaluate:"})
        content.append({"type": "input_image", "image_url": candidate.preview_url, "detail": "high"})
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["overallPass", "hardGateResults", "identityScore", "styleScore", "periodScore", "productionScore", "regressions", "repairPlan", "preserve", "summary"],
            "properties": {
                "overallPass": {"type": "boolean"},
                "hardGateResults": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["gate", "status", "evidence", "repair"], "properties": {"gate": {"type": "string"}, "status": {"type": "string", "enum": ["PASS", "FAIL", "UNKNOWN"]}, "evidence": {"type": "string"}, "repair": {"type": "string"}}}},
                "identityScore": {"type": "number", "minimum": 0, "maximum": 100},
                "styleScore": {"type": "number", "minimum": 0, "maximum": 100},
                "periodScore": {"type": "number", "minimum": 0, "maximum": 100},
                "productionScore": {"type": "number", "minimum": 0, "maximum": 100},
                "regressions": {"type": "array", "items": {"type": "string"}},
                "repairPlan": {"type": "array", "items": {"type": "string"}},
                "preserve": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"},
            },
        }
        payload = {
            "model": self.model,
            "reasoning": {"effort": "medium"},
            "input": [{"role": "user", "content": content}],
            "text": {"format": {"type": "json_schema", "name": "apollo_visual_qa", "strict": True, "schema": schema}},
        }
        response = _json_request(
            self.endpoint,
            method="POST",
            headers={"authorization": f"Bearer {key}", "content-type": "application/json"},
            payload=payload,
            timeout=self.timeout_seconds,
        )
        output_text = None
        for item in response.get("output", []):
            if item.get("type") != "message":
                continue
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    output_text = part.get("text")
                    break
        if not output_text:
            raise RuntimeError("OPENAI_CRITIC_MISSING_OUTPUT_TEXT")
        value = json.loads(output_text)
        gates = tuple(
            VisualQAGate(
                gate=str(gate["gate"]),
                status=VisualGateStatus(str(gate["status"])),
                evidence=str(gate["evidence"]),
                repair=str(gate["repair"]),
            )
            for gate in value["hardGateResults"]
        )
        return VisualQAReport(
            overall_pass=bool(value["overallPass"]),
            hard_gate_results=gates,
            identity_score=float(value["identityScore"]),
            style_score=float(value["styleScore"]),
            period_score=float(value["periodScore"]),
            production_score=float(value["productionScore"]),
            regressions=tuple(map(str, value["regressions"])),
            repair_plan=tuple(map(str, value["repairPlan"])),
            preserve=tuple(map(str, value["preserve"])),
            summary=str(value["summary"]),
        )
