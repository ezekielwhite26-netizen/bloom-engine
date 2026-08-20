from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


class VisualSubjectKind(str, Enum):
    CHARACTER = "CHARACTER"
    LOCATION = "LOCATION"
    OBJECT = "OBJECT"
    SCENE = "SCENE"


class VisualRequestKind(str, Enum):
    SINGLE_ASSET = "SINGLE_ASSET"
    PRODUCTION_PACK = "PRODUCTION_PACK"


class VisualGateStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class VisualRunStatus(str, Enum):
    SYSTEM_PASS = "SYSTEM_PASS"
    HUMAN_REVIEW_REQUIRED = "HUMAN_REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class VisualSubjectIdentity:
    stable_id: str
    display_name: str
    kind: VisualSubjectKind
    record_id: str
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VisualReferenceAuthority:
    asset_key: str
    asset_name: str
    subject_name: str
    role: str
    uri: str | None
    controls: tuple[str, ...]
    does_not_control: tuple[str, ...]
    status: str
    reference_strength: str
    record_id: str
    width: int | None = None
    height: int | None = None

    @property
    def has_image(self) -> bool:
        return bool(self.uri)


@dataclass(frozen=True, slots=True)
class VisualJobRequest:
    arc: str
    command: str
    subject_query: str
    subject_kind: VisualSubjectKind
    request_kind: VisualRequestKind
    output_type: str | None = None
    max_iterations: int = 5
    authorization_token: str | None = None


@dataclass(frozen=True, slots=True)
class VisualPackJobDefinition:
    output_type: str
    priority: int
    prompt: str
    required_reference_roles: tuple[str, ...]
    hard_gates: tuple[str, ...]
    soft_criteria: tuple[str, ...] = ()
    style_rules: tuple[str, ...] = ()
    anti_drift: tuple[str, ...] = ()
    open_fields: tuple[str, ...] = ()
    approved_dependencies: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VisualPackDefinition:
    key: str
    subject_id: str
    jobs: tuple[VisualPackJobDefinition, ...]


@dataclass(frozen=True, slots=True)
class CompiledVisualJob:
    job_key: str
    arc: str
    subject_id: str
    subject_name: str
    subject_kind: VisualSubjectKind
    output_type: str
    prompt: str
    references: tuple[VisualReferenceAuthority, ...]
    hard_gates: tuple[str, ...]
    soft_criteria: tuple[str, ...]
    style_rules: tuple[str, ...]
    anti_drift: tuple[str, ...]
    open_fields: tuple[str, ...]
    max_iterations: int
    missing_dependencies: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return not self.missing_dependencies


@dataclass(frozen=True, slots=True)
class CompiledVisualRequest:
    request_key: str
    subject: VisualSubjectIdentity
    jobs: tuple[CompiledVisualJob, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RenderedVisual:
    provider_id: str
    model: str
    mime_type: str
    temporary_url: str | None = None
    image_base64: str | None = None
    provider_request_id: str | None = None
    seed: int | None = None
    provider_cost: float | None = None


@dataclass(frozen=True, slots=True)
class PersistedVisualCandidate:
    candidate_id: str
    asset_key: str
    asset_record_id: str
    job_key: str
    iteration: int
    provider_id: str
    model: str
    preview_url: str
    parent_candidate_id: str | None
    status: str
    created_at: str


@dataclass(frozen=True, slots=True)
class VisualQAGate:
    gate: str
    status: VisualGateStatus
    evidence: str
    repair: str


@dataclass(frozen=True, slots=True)
class VisualQAReport:
    overall_pass: bool
    hard_gate_results: tuple[VisualQAGate, ...]
    identity_score: float
    style_score: float
    period_score: float
    production_score: float
    regressions: tuple[str, ...]
    repair_plan: tuple[str, ...]
    preserve: tuple[str, ...]
    summary: str


@dataclass(frozen=True, slots=True)
class VisualJobRun:
    job_key: str
    output_type: str
    status: VisualRunStatus
    candidates: tuple[PersistedVisualCandidate, ...]
    best_candidate: PersistedVisualCandidate | None
    best_qa: VisualQAReport | None
    stop_reason: str


@dataclass(frozen=True, slots=True)
class VisualRunOutput:
    request_key: str
    subject_id: str
    subject_name: str
    status: VisualRunStatus
    jobs: tuple[VisualJobRun, ...]
    warnings: tuple[str, ...]
    requires_human_approval: bool = True

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "request_key": self.request_key,
            "subject_id": self.subject_id,
            "subject_name": self.subject_name,
            "status": self.status.value,
            "requires_human_approval": True,
            "warnings": list(self.warnings),
            "jobs": [
                {
                    "job_key": job.job_key,
                    "output_type": job.output_type,
                    "status": job.status.value,
                    "stop_reason": job.stop_reason,
                    "best_candidate": None if job.best_candidate is None else {
                        "candidate_id": job.best_candidate.candidate_id,
                        "asset_key": job.best_candidate.asset_key,
                        "preview_url": job.best_candidate.preview_url,
                        "status": job.best_candidate.status,
                    },
                    "qa_summary": None if job.best_qa is None else job.best_qa.summary,
                }
                for job in self.jobs
            ],
        }
