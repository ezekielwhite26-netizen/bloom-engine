from __future__ import annotations

from dataclasses import dataclass, field
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


class RendererCallBudgetExhausted(RuntimeError):
    pass


@dataclass(slots=True)
class _RunBudget:
    limit: int
    used: int = 0

    def consume(self) -> None:
        if self.used >= self.limit:
            raise RendererCallBudgetExhausted("RENDER_CALL_BUDGET_EXHAUSTED")
        self.used += 1

    @property
    def exhausted(self) -> bool:
        return self.used >= self.limit


@dataclass(slots=True)
class _JobState:
    job: CompiledVisualJob
    candidates: list[PersistedVisualCandidate] = field(default_factory=list)
    best_candidate: PersistedVisualCandidate | None = None
    best_qa: VisualQAReport | None = None
    best_score: float = float("-inf")
    non_improving: int = 0
    iteration: int = 0
    terminal_status: VisualRunStatus | None = None
    stop_reason: str = ""

    @property
    def active(self) -> bool:
        return self.terminal_status is None

    def finish(self, status: VisualRunStatus, reason: str) -> None:
        self.terminal_status = status
        self.stop_reason = reason

    def to_run(self) -> VisualJobRun:
        status = self.terminal_status or VisualRunStatus.HUMAN_REVIEW_REQUIRED
        return VisualJobRun(
            job_key=self.job.job_key,
            output_type=self.job.output_type,
            status=status,
            candidates=tuple(self.candidates),
            best_candidate=self.best_candidate,
            best_qa=self.best_qa,
            stop_reason=self.stop_reason or "INCOMPLETE_VISUAL_JOB",
        )


@dataclass(slots=True)
class ApolloVisualDirector:
    compiler: ApolloVisualAuthorityCompiler
    renderers: Mapping[str, VisualRenderer]
    critic: VisualCritic
    assets: VisualAssetStore
    primary_renderer: str = "flux-2-pro"
    repair_renderer: str = "gpt-image-2"
    fallback_renderer: str = "gpt-image-2"
    absolute_renderer_call_ceiling: int = 60

    def run(self, request: VisualJobRequest) -> VisualRunOutput:
        if not request.authorization_token:
            raise PermissionError("VISUAL_GENERATION_AUTHORIZATION_REQUIRED")
        compiled = self.compiler.compile(request)
        call_limit = max(1, min(int(request.max_renderer_calls), self.absolute_renderer_call_ceiling))
        budget = _RunBudget(limit=call_limit)
        states: list[_JobState] = []

        for job in compiled.jobs:
            state = _JobState(job=job)
            if not job.ready:
                state.finish(
                    VisualRunStatus.BLOCKED,
                    "MISSING_DEPENDENCIES:" + ",".join(job.missing_dependencies),
                )
            states.append(state)

        # Breadth-first/round-robin execution is deliberate. A full production
        # pack gets one candidate per ready slot before APOLLO spends repeatedly
        # repairing the first difficult view. Later rounds target failed views.
        while any(state.active for state in states):
            if budget.exhausted:
                self._stop_for_budget(states)
                break
            progressed = False
            for state in states:
                if not state.active:
                    continue
                if budget.exhausted:
                    self._stop_for_budget(states)
                    break
                self._advance_job(state, budget)
                progressed = True
            if not progressed:
                break

        runs = tuple(state.to_run() for state in states)
        if not runs or all(run.status is VisualRunStatus.BLOCKED for run in runs):
            status = VisualRunStatus.BLOCKED
        elif any(run.status is VisualRunStatus.FAILED for run in runs):
            status = VisualRunStatus.FAILED
        elif all(run.status in {VisualRunStatus.SYSTEM_PASS, VisualRunStatus.BLOCKED} for run in runs) and any(
            run.status is VisualRunStatus.SYSTEM_PASS for run in runs
        ):
            # A partially blocked pack still needs human/authority follow-up even
            # when every runnable slot passed.
            status = VisualRunStatus.SYSTEM_PASS if all(run.status is VisualRunStatus.SYSTEM_PASS for run in runs) else VisualRunStatus.HUMAN_REVIEW_REQUIRED
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
            renderer_calls_used=budget.used,
            renderer_call_limit=budget.limit,
        )

    @staticmethod
    def _stop_for_budget(states: list[_JobState]) -> None:
        for state in states:
            if state.active:
                state.finish(VisualRunStatus.HUMAN_REVIEW_REQUIRED, "RENDER_CALL_BUDGET_EXHAUSTED")

    def _renderer(self, provider_id: str) -> VisualRenderer:
        renderer = self.renderers.get(provider_id)
        if renderer is None:
            raise RuntimeError(f"VISUAL_RENDERER_NOT_CONFIGURED:{provider_id}")
        return renderer

    @staticmethod
    def _fallback_allowed(error: Exception) -> bool:
        text = str(error).upper()
        # A fallback provider must never be used as a way around another
        # provider's moderation/safety decision.
        blocked_markers = ("MODERAT", "SAFETY", "CONTENT_POLICY", "CONTENT POLICY")
        return not any(marker in text for marker in blocked_markers)

    def _render_with_fallback(self, provider_id: str, job: CompiledVisualJob, budget: _RunBudget, **kwargs):
        budget.consume()
        try:
            return self._renderer(provider_id).render(job, **kwargs)
        except Exception as error:
            if self.fallback_renderer == provider_id or not self._fallback_allowed(error):
                raise
            budget.consume()
            return self._renderer(self.fallback_renderer).render(job, **kwargs)

    def _advance_job(self, state: _JobState, budget: _RunBudget) -> None:
        job = state.job
        if state.iteration >= job.max_iterations:
            state.finish(VisualRunStatus.HUMAN_REVIEW_REQUIRED, "MAX_ITERATIONS_REACHED")
            return

        state.iteration += 1
        iteration = state.iteration
        repairing = iteration > 1 and state.best_candidate is not None and state.best_qa is not None
        preferred = self.repair_renderer if repairing else self.primary_renderer

        try:
            # Repair instructions are always paired with the candidate that
            # produced them. A worse candidate's QA never edits an older best.
            rendered = self._render_with_fallback(
                preferred,
                job,
                budget,
                iteration=iteration,
                previous_candidate=state.best_candidate if repairing else None,
                repair_plan=state.best_qa.repair_plan if repairing and state.best_qa else (),
                preserve=state.best_qa.preserve if repairing and state.best_qa else (),
            )
            candidate = self.assets.persist_generated(
                job,
                rendered,
                iteration=iteration,
                parent_candidate_id=state.best_candidate.candidate_id if repairing and state.best_candidate else None,
            )
            state.candidates.append(candidate)
            qa = self.critic.review(job, candidate, state.best_candidate)
        except RendererCallBudgetExhausted:
            state.finish(VisualRunStatus.HUMAN_REVIEW_REQUIRED, "RENDER_CALL_BUDGET_EXHAUSTED")
            return
        except Exception as exc:
            state.finish(VisualRunStatus.FAILED, str(exc))
            return

        score = visual_quality_score(qa)
        if score > state.best_score:
            state.best_score = score
            state.best_candidate = candidate
            state.best_qa = qa
            state.non_improving = 0
        else:
            state.non_improving += 1

        if _system_pass(qa):
            passed = self.assets.mark_system_pass(candidate, qa.summary)
            state.candidates[-1] = passed
            state.best_candidate = passed
            state.best_qa = qa
            state.finish(VisualRunStatus.SYSTEM_PASS, "ALL_HARD_GATES_PASS")
            return

        if state.non_improving >= 2:
            state.finish(
                VisualRunStatus.HUMAN_REVIEW_REQUIRED,
                "TWO_CONSECUTIVE_NON_IMPROVING_ITERATIONS",
            )
            return

        if state.iteration >= job.max_iterations:
            state.finish(VisualRunStatus.HUMAN_REVIEW_REQUIRED, "MAX_ITERATIONS_REACHED")
