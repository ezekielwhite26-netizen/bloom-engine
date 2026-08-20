from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from bloom_engine.apollo.authority import AirtableVisualAuthoritySource, AirtableVisualHTTP, ApolloVisualAuthorityCompiler
from bloom_engine.apollo.director import ApolloVisualDirector
from bloom_engine.apollo.gpt_image import OpenAIGPTImage2Transport
from bloom_engine.apollo.job_store import AirtableVisualJobStore, VisualJobStore
from bloom_engine.apollo.models import VisualJobRequest, VisualRequestKind, VisualSubjectKind
from bloom_engine.apollo.providers import Flux2ProRenderer, GPTImage2Renderer, OpenAIVisualCritic
from bloom_engine.apollo.storage import AirtableVisualAssetStore

router = APIRouter(prefix="/v1/visual", tags=["APOLLO Visual Director"])


class VisualPlanBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arc: str = Field(min_length=1)
    command: str = Field(min_length=1)
    subject_query: str = Field(min_length=1)
    subject_kind: VisualSubjectKind = VisualSubjectKind.CHARACTER
    request_kind: VisualRequestKind = VisualRequestKind.PRODUCTION_PACK
    output_type: str | None = None
    max_iterations: int = Field(default=5, ge=1, le=6)


class VisualGenerateBody(VisualPlanBody):
    # This must be true in the current request. A previous chat decision, project
    # preference, or model inference may not silently authorize paid generation.
    confirm_spend: bool = False


def _env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"MISSING_ENV:{name}")
    return value


def _airtable_config() -> tuple[str, str]:
    return os.getenv("BLOOM_AIRTABLE_BASE_ID", "appNhl43NzKfbsTAw"), _env("AIRTABLE_PAT")


def _compiler() -> ApolloVisualAuthorityCompiler:
    base_id, token = _airtable_config()
    source = AirtableVisualAuthoritySource(AirtableVisualHTTP(base_id=base_id, token=token))
    return ApolloVisualAuthorityCompiler(source)


def _job_store() -> VisualJobStore:
    base_id, token = _airtable_config()
    return AirtableVisualJobStore(base_id=base_id, token=token)


def _request(body: VisualPlanBody, authorization_token: str | None = None) -> VisualJobRequest:
    return VisualJobRequest(
        arc=body.arc,
        command=body.command,
        subject_query=body.subject_query,
        subject_kind=body.subject_kind,
        request_kind=body.request_kind,
        output_type=body.output_type,
        max_iterations=body.max_iterations,
        authorization_token=authorization_token,
    )


def _plan_dict(plan) -> dict[str, Any]:
    return {
        "request_key": plan.request_key,
        "subject_id": plan.subject.stable_id,
        "subject_name": plan.subject.display_name,
        "subject_kind": plan.subject.kind.value,
        "warnings": list(plan.warnings),
        "jobs": [
            {
                "job_key": job.job_key,
                "output_type": job.output_type,
                "ready": job.ready,
                "reference_assets": [
                    {
                        "asset_key": ref.asset_key,
                        "role": ref.role,
                        "status": ref.status,
                        "reference_strength": ref.reference_strength,
                        "has_image": ref.has_image,
                    }
                    for ref in job.references
                ],
                "missing_dependencies": list(job.missing_dependencies),
            }
            for job in plan.jobs
        ],
        "requires_human_approval_after_system_pass": True,
    }


def _director() -> ApolloVisualDirector:
    base_id, token = _airtable_config()
    compiler = _compiler()
    flux = Flux2ProRenderer()
    gpt_image = GPTImage2Renderer(OpenAIGPTImage2Transport())
    critic = OpenAIVisualCritic()
    assets = AirtableVisualAssetStore(base_id=base_id, token=token)
    return ApolloVisualDirector(
        compiler=compiler,
        renderers={flux.provider_id: flux, gpt_image.provider_id: gpt_image},
        critic=critic,
        assets=assets,
        primary_renderer="flux-2-pro",
        repair_renderer="gpt-image-2",
        fallback_renderer="gpt-image-2",
    )


def _execute(job_id: str, request: VisualJobRequest) -> None:
    store = _job_store()
    try:
        output = _director().run(request)
        store.finish(job_id, status=output.status.value, result=output.to_public_dict())
    except Exception as exc:
        # Keep failures reviewable without exposing credentials. Provider errors
        # may be useful, but job_store truncates the durable error envelope.
        store.fail(job_id, error=f"{type(exc).__name__}:{exc}")


@router.post("/plan")
def visual_plan(body: VisualPlanBody) -> dict[str, Any]:
    """Compile APOLLO authority and coverage without generating or spending."""
    try:
        plan = _compiler().compile(_request(body))
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _plan_dict(plan)


@router.post("/generate")
def visual_generate(body: VisualGenerateBody, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Start a paid visual run only after explicit current-request confirmation."""
    if body.confirm_spend is not True:
        raise HTTPException(status_code=422, detail="Explicit confirm_spend=true is required for paid visual generation")

    try:
        compiler = _compiler()
        request = _request(body, authorization_token=f"VIS-CAP::{uuid.uuid4().hex}")
        plan = compiler.compile(request)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    ready = [job for job in plan.jobs if job.ready]
    if not ready:
        return {
            "visual_job_id": None,
            "status": "BLOCKED",
            "plan": _plan_dict(plan),
            "spent": False,
            "message": "APOLLO blocked before renderer invocation; no image-generation spend occurred.",
        }

    # Do not create a durable Generating job until every paid provider required by
    # the configured primary/repair path is present.
    missing_runtime = [name for name in ("BFL_API_KEY", "OPENAI_API_KEY") if not os.getenv(name)]
    if missing_runtime:
        raise HTTPException(status_code=503, detail="Visual providers not configured: " + ", ".join(missing_runtime))

    job_id = f"APOLLO-VIS-JOB::{uuid.uuid4().hex}"
    store = _job_store()
    store.start(
        visual_job_id=job_id,
        request_key=plan.request_key,
        arc=body.arc,
        subject_id=plan.subject.stable_id,
        subject_name=plan.subject.display_name,
        command=body.command,
        shot_list=tuple(job.output_type for job in plan.jobs),
        required_anchor_assets=tuple(dict.fromkeys(
            ref.asset_key for job in ready for ref in job.references
        )),
    )
    background_tasks.add_task(_execute, job_id, request)
    return {
        "visual_job_id": job_id,
        "status": "RUNNING",
        "request_key": plan.request_key,
        "subject_id": plan.subject.stable_id,
        "subject_name": plan.subject.display_name,
        "ready_job_count": len(ready),
        "blocked_job_count": len(plan.jobs) - len(ready),
        "requires_human_approval": True,
    }


@router.get("/jobs/{job_id}")
def visual_job_status(job_id: str) -> dict[str, Any]:
    try:
        state = _job_store().get(job_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if state is None:
        raise HTTPException(status_code=404, detail="Visual job not found")
    return {
        "visual_job_id": state.visual_job_id,
        "status": state.status,
        "request_key": state.request_key,
        "subject_id": state.subject_id,
        "subject_name": state.subject_name,
        "result": state.result,
        "error": state.error,
        "requires_human_approval": True,
    }
