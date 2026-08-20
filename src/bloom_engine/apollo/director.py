from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from bloom_engine.apollo.authority import ApolloVisualAuthorityCompiler
from bloom_engine.apollo.models import (
    CompiledVisualJob,
    PersistedVisualCandidate,
    VisualJobRequest,
    VisualJobRun,
    VisualQAReport,
    VisualRunOutput,
    VisualRunStatus,
)
from bloom_engine.apollo.providers import VisualCritic, VisualRenderer
from bloom_engine.apollo.storage import VisualAssetStore


def _hard_fail_count(report: VisualQAReport) -> int:
    return sum(1 for gate in report.hard_gate_results if gate.status.value == "FAIL")


def visual_quality_score(report: VisualQAReport) -> float:
    return (
        report.identity_score * 2
        + report.style_score
        + report.period_score
        + report.production_score
        - _hard_fail_count(report) * 100
    )


def _system_pass(report: VisualQAReport) -> bool:
    return report.overall_pass and _hard_fail_count(report) == 0


@dataclass(slots=True)
class ApolloVisualDirector:
    compiler: ApolloVisualAuthorityCompiler
    renderers: Mapping[str, VisualRenderer]
    critic: VisualCritic
    assets: VisualAssetStore
    primary_renderer: str = "flux-2-pro"
    repair_renderer: str = "gpt-image-2"
    fallback_renderer: str = "gpt-image-2"

    def run(self, request: VisualJobRequest) -> VisualRunOutput:
        if not request.authorization_token:
            raise PermissionError("VISUAL_GENERATION_AUTHORIZATION_REQUIRED")
        compiled = self.compiler.compile(request)
        runs = tuple(self._run_job(job) for job in compiled.jobs)
        if not runs or all(run.status is VisualRunStatus.BLOCKED for run in runs):
            status = VisualRunStatus.BLOCKED
        elif any(run.status is VisualRunStatus.FAILED for run in runs):
            status = VisualRunStatus.FAILED
        elif all(run.status is VisualRunStatus.SYSTEM_PASS for run in runs):
            status = VisualRunStatus.SYSTEM_PASS
        else:
            status = VisualRunStatus.HUMAN_REVIEW_REQUIRED
        return VisualRunOutput(
            request_key=compiled.request_key,
            subject_id=compiled.subject.stable_id,
            subject_name=compiled.subject.display_name,
            status=status,
            jobs=runs,
            warnings=compiled.warnings,
            requires_human_approval=True,
        )

    def _renderer(self, provider_id: str) -> VisualRenderer:
        renderer = self.renderers.get(provider_id)
        if renderer is None:
            raise RuntimeError(f"VISUAL_RENDERER_NOT_CONFIGURED:{provider_id}")
        return renderer

    def _render_with_fallback(self, provider_id: str, job: CompiledVisualJob, **kwargs):
        try:
            return self._renderer(provider_id).render(job, **kwargs)
        except Exception:
            if self.fallback_renderer == provider_id:
                raise
            return self._renderer(self.fallback_renderer).render(job, **kwargs)

    def _run_job(self, job: CompiledVisualJob) -> VisualJobRun:
        if not job.ready:
            return VisualJobRun(
                job_key=job.job_key,
                output_type=job.output_type,
                status=VisualRunStatus.BLOCKED,
                candidates=(),
                best_candidate=None,
                best_qa=None,
                stop_reason="MISSING_DEPENDENCIES:" + ",".join(job.missing_dependencies),
            )

        candidates: list[PersistedVisualCandidate] = []
        best_candidate: PersistedVisualCandidate | None = None
        best_qa: VisualQAReport | None = None
        best_score = float("-inf")
        non_improving = 0

        for iteration in range(1, job.max_iterations + 1):
            try:
                # Repair instructions are always paired with the candidate that
                # produced them. A worse candidate's QA never edits an older best.
                repairing = iteration > 1 and best_candidate is not None and best_qa is not None
                preferred = self.repair_renderer if repairing else self.primary_renderer
                rendered = self._render_with_fallback(
                    preferred,
                    job,
                    iteration=iteration,
                    previous_candidate=best_candidate if repairing else None,
                    repair_plan=best_qa.repair_plan if repairing and best_qa else (),
                    preserve=best_qa.preserve if repairing and best_qa else (),
                )
                candidate = self.assets.persist_generated(
                    job,
                    rendered,
                    iteration=iteration,
                    parent_candidate_id=best_candidate.candidate_id if repairing and best_candidate else None,
                )
                candidates.append(candidate)
                qa = self.critic.review(job, candidate, best_candidate)
                score = visual_quality_score(qa)
                if score > best_score:
                    best_score = score
                    best_candidate = candidate
                    best_qa = qa
                    non_improving = 0
                else:
                    non_improving += 1

                if _system_pass(qa):
                    passed = self.assets.mark_system_pass(candidate, qa.summary)
                    candidates[-1] = passed
                    return VisualJobRun(
                        job_key=job.job_key,
                        output_type=job.output_type,
                        status=VisualRunStatus.SYSTEM_PASS,
                        candidates=tuple(candidates),
                        best_candidate=passed,
                        best_qa=qa,
                        stop_reason="ALL_HARD_GATES_PASS",
                    )
                if non_improving >= 2:
                    return VisualJobRun(
                        job_key=job.job_key,
                        output_type=job.output_type,
                        status=VisualRunStatus.HUMAN_REVIEW_REQUIRED,
                        candidates=tuple(candidates),
                        best_candidate=best_candidate,
                        best_qa=best_qa,
                        stop_reason="TWO_CONSECUTIVE_NON_IMPROVING_ITERATIONS",
                    )
            except Exception as exc:
                return VisualJobRun(
                    job_key=job.job_key,
                    output_type=job.output_type,
                    status=VisualRunStatus.FAILED,
                    candidates=tuple(candidates),
                    best_candidate=best_candidate,
                    best_qa=best_qa,
                    stop_reason=str(exc),
                )

        return VisualJobRun(
            job_key=job.job_key,
            output_type=job.output_type,
            status=VisualRunStatus.HUMAN_REVIEW_REQUIRED,
            candidates=tuple(candidates),
            best_candidate=best_candidate,
            best_qa=best_qa,
            stop_reason="MAX_ITERATIONS_REACHED",
        )
