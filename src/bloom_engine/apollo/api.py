from __future__ import annotations

import hashlib
import os
import unicodedata
import uuid
from hmac import compare_digest
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from bloom_engine.apollo.authority import AirtableVisualAuthoritySource, AirtableVisualHTTP, ApolloVisualAuthorityCompiler
from bloom_engine.apollo.director import ApolloVisualDirector
from bloom_engine.apollo.gpt_image import OpenAIGPTImage2Transport
from bloom_engine.apollo.job_store import AirtableVisualJobStore, VisualJobStore
from bloom_engine.apollo.models import VisualJobRequest, VisualRequestKind, VisualSubjectKind
from bloom_engine.apollo.providers import Flux2ProRenderer, GPTImage2Renderer, OpenAIVisualCritic
from bloom_engine.apollo.reference_ingest import AirtableReferenceAttachmentIngestor
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
    max_renderer_calls: int = Field(default=12, ge=1, le=60)


class VisualGenerateBody(VisualPlanBody):
    # This must be true in the current request. A previous chat decision, project
    # preference, or model inference may not silently authorize paid generation.
    confirm_spend: bool = False


class VisualReferenceIngestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_key: str = Field(min_length=1, max_length=200)
    filename: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=1, max_length=100)
    image_base64: str = Field(min_length=1)
    expected_sha256: str | None = Field(default=None, pattern=r"^[A-Fa-f0-9]{64}$")


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


def _reference_ingestor() -> AirtableReferenceAttachmentIngestor:
    base_id, token = _airtable_config()
    return AirtableReferenceAttachmentIngestor(base_id=base_id, token=token)


def _normalize_secret(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(
        ch for ch in normalized
        if not ch.isspace() and unicodedata.category(ch) != "Cf"
    )


def _require_reference_ingest_admin(token: str | None) -> None:
    """Require a separate operator secret for reference-byte ingestion."""

    configured_hash = (os.getenv("BLOOM_APOLLO_ADMIN_TOKEN_SHA256") or "").strip().lower()
    if not configured_hash:
        raise HTTPException(status_code=503, detail="APOLLO reference ingestion is not configured")
    received = _normalize_secret(token)
    if not received:
        raise HTTPException(status_code=401, detail="Missing APOLLO admin credentials")
    received_hash = hashlib.sha256(received.encode("utf-8")).hexdigest()
    if not compare_digest(received_hash, configured_hash):
        raise HTTPException(status_code=401, detail="Invalid APOLLO admin credentials")


def _request(body: VisualPlanBody, authorization_token: str | None = None) -> VisualJobRequest:
    return VisualJobRequest(
        arc=body.arc,
        command=body.command,
        subject_query=body.subject_query,
        subject_kind=body.subject_kind,
        request_kind=body.request_kind,
        output_type=body.output_type,
        max_iterations=body.max_iterations,
        max_renderer_calls=body.max_renderer_calls,
        authorization_token=authorization_token,
    )


def _plan_dict(plan, *, renderer_call_limit: int = 12) -> dict[str, Any]:
    ready = [job for job in plan.jobs if job.ready]
    return {
        "request_key": plan.request_key,
        "subject_id": plan.subject.stable_id,
        "subject_name": plan.subject.display_name,
        "subject_kind": plan.subject.kind.value,
        "ready_job_count": len(ready),
        "blocked_job_count": len(plan.jobs) - len(ready),
        "minimum_first_pass_renderer_calls": len(ready),
        "renderer_call_limit": renderer_call_limit,
        "execution_policy": "ROUND_ROBIN_FIRST_PASS_BEFORE_REPAIRS",
        "warnings": list(plan.warnings),
        "jobs": [
            {
                "job_key": job.job_key,
                "output_type": job.output_type,
                "ready": job.ready,
                "max_iterations": job.max_iterations,
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
        store.fail(job_id, error=f"{type(exc).__name__}:{exc}")


@router.get("/capabilities")
def visual_capabilities() -> dict[str, Any]:
    airtable = bool(os.getenv("AIRTABLE_PAT"))
    flux = bool(os.getenv("BFL_API_KEY"))
    openai = bool(os.getenv("OPENAI_API_KEY"))
    admin_ingest = bool((os.getenv("BLOOM_APOLLO_ADMIN_TOKEN_SHA256") or "").strip())
    return {
        "visual_plan": airtable,
        "visual_readiness": airtable,
        "visual_generate_endpoint": True,
        "visual_generate_configured": airtable and flux and openai,
        "reference_ingest_admin_configured": airtable and admin_ingest,
        "durable_job_registry": airtable,
        "candidate_storage": "BLOOM Visual Assets" if airtable else None,
        "primary_renderer": "flux-2-pro",
        "repair_renderer": "gpt-image-2-2026-04-21",
        "critic": "gpt-5.6",
        "default_renderer_call_limit": 12,
        "absolute_renderer_call_ceiling": 60,
        "production_pack_execution": "ROUND_ROBIN_FIRST_PASS_BEFORE_REPAIRS",
        "explicit_current_request_generation_authorization_required": True,
        "explicit_spend_confirmation_required": True,
        "system_pass_requires_human_approval": True,
        "automatic_gold_promotion": False,
        "automatic_paid_retry_after_host_restart": False,
        "live_deployment_claimed": False,
    }


@router.post("/readiness")
def visual_readiness(body: VisualPlanBody) -> dict[str, Any]:
    """Explain authority-vs-byte readiness without generating or spending."""

    try:
        compiler = _compiler()
        subject = compiler.source.resolve_subject(body.subject_query, body.subject_kind, body.arc)
        if subject is None:
            raise ValueError(f"VISUAL_SUBJECT_NOT_RESOLVED:{body.subject_query}")
        refs = compiler.source.list_references(subject, body.arc)
        plan = compiler.compile(_request(body))
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    roles_present = sorted({ref.role for ref in refs})
    roles_with_bytes = sorted({ref.role for ref in refs if ref.has_image})
    roles_missing_bytes = sorted({ref.role for ref in refs if not ref.has_image})
    ready_jobs = [job.output_type for job in plan.jobs if job.ready]
    blocked_jobs = [
        {"output_type": job.output_type, "missing_dependencies": list(job.missing_dependencies)}
        for job in plan.jobs if not job.ready
    ]
    return {
        "subject_id": subject.stable_id,
        "subject_name": subject.display_name,
        "authority_metadata_present": bool(refs),
        "authority_roles_present": roles_present,
        "authority_roles_with_image_bytes": roles_with_bytes,
        "authority_roles_missing_image_bytes": roles_missing_bytes,
        "reference_records": [
            {
                "asset_key": ref.asset_key,
                "role": ref.role,
                "status": ref.status,
                "reference_strength": ref.reference_strength,
                "has_image": ref.has_image,
            }
            for ref in refs
        ],
        "ready_jobs": ready_jobs,
        "blocked_jobs": blocked_jobs,
        "ready_for_any_generation": bool(ready_jobs),
        "ready_for_full_requested_pack": bool(plan.jobs) and not blocked_jobs,
        "spent": False,
        "renderer_invoked": False,
    }


@router.post("/plan")
def visual_plan(body: VisualPlanBody) -> dict[str, Any]:
    """Compile APOLLO authority and coverage without generating or spending."""
    try:
        plan = _compiler().compile(_request(body))
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _plan_dict(plan, renderer_call_limit=body.max_renderer_calls)


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
            "plan": _plan_dict(plan, renderer_call_limit=body.max_renderer_calls),
            "spent": False,
            "message": "APOLLO blocked before renderer invocation; no image-generation spend occurred.",
        }

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
        command=f"{body.command}\nAPOLLO renderer-call limit for this run: {body.max_renderer_calls}",
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
        "renderer_call_limit": body.max_renderer_calls,
        "execution_policy": "ROUND_ROBIN_FIRST_PASS_BEFORE_REPAIRS",
        "spend_authorized_for_this_run": True,
        "spent": None,
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
        "started_at": state.started_at,
        "updated_at": state.updated_at,
        "recovery_required": state.recovery_required,
        "requires_human_approval": True,
    }


@router.post("/admin/reference-attachment", include_in_schema=False)
def visual_admin_reference_attachment(
    body: VisualReferenceIngestBody,
    x_bloom_apollo_admin: str | None = Header(default=None, alias="X-BLOOM-APOLLO-ADMIN"),
) -> dict[str, Any]:
    """Operator-only reference-byte ingestion; never changes authority metadata."""

    _require_reference_ingest_admin(x_bloom_apollo_admin)
    try:
        result = _reference_ingestor().ingest(
            asset_key=body.asset_key,
            filename=body.filename,
            mime_type=body.mime_type,
            image_base64=body.image_base64,
            expected_sha256=body.expected_sha256,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return result.to_public_dict()
