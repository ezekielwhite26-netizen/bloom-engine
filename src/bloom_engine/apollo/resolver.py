from __future__ import annotations

from bloom_engine.apollo.authority import ApolloVisualAuthorityCompiler
from bloom_engine.apollo.models import VisualJobRequest, VisualRequestKind, VisualSubjectKind
from bloom_engine.contracts.resolution import Resolution, ResolutionStatus
from bloom_engine.pantheon.protocol import CoreRequest, assert_core_may_answer


class ApolloResolver:
    """Sovereign APOLLO resolver for visual authority/readiness.

    Generation is deliberately not performed by the resolver. The resolver owns
    visual truth and readiness; the Visual Director is a bounded worker that may
    consume those resolved constraints after separate spend authorization.
    """

    name = "APOLLO"

    def __init__(self, compiler: ApolloVisualAuthorityCompiler):
        self.compiler = compiler

    def resolve(self, request: CoreRequest) -> Resolution:
        assert_core_may_answer(self.name, request.predicate)
        if request.predicate in {"visual.authority", "visual.coverage", "visual.job_ready"}:
            return self._resolve_visual(request)
        return Resolution(
            owner=self.name,
            predicate=request.predicate,
            status=ResolutionStatus.UNKNOWN,
            evidence=tuple(request.evidence),
            missing_required=("APOLLO resolver implementation for this visual predicate",),
            do_not_infer=("unsupported APOLLO visual predicate must not be guessed",),
        )

    def _resolve_visual(self, request: CoreRequest) -> Resolution:
        arc = str(request.inputs.get("arc") or "").strip()
        subject_query = str(request.inputs.get("subject_query") or "").strip()
        kind_text = str(request.inputs.get("subject_kind") or "CHARACTER").strip().upper()
        output_type = request.inputs.get("output_type")
        if not arc or not subject_query:
            return Resolution(
                owner=self.name,
                predicate=request.predicate,
                status=ResolutionStatus.UNKNOWN,
                evidence=tuple(request.evidence),
                missing_required=("arc and subject_query",),
            )
        try:
            kind = VisualSubjectKind(kind_text)
            plan = self.compiler.compile(VisualJobRequest(
                arc=arc,
                command=f"APOLLO resolve {request.predicate}",
                subject_query=subject_query,
                subject_kind=kind,
                request_kind=VisualRequestKind.SINGLE_ASSET if output_type else VisualRequestKind.PRODUCTION_PACK,
                output_type=str(output_type) if output_type else None,
            ))
        except (ValueError, KeyError) as exc:
            return Resolution(
                owner=self.name,
                predicate=request.predicate,
                status=ResolutionStatus.UNKNOWN,
                evidence=tuple(request.evidence),
                missing_required=(str(exc),),
                do_not_infer=("visual identity or missing authority must not be guessed",),
            )

        blocked = [job for job in plan.jobs if not job.ready]
        evidence = tuple(
            {
                "source": "Visual Assets",
                "asset_key": ref.asset_key,
                "asset_record_id": ref.record_id,
                "role": ref.role,
                "status": ref.status,
                "reference_strength": ref.reference_strength,
            }
            for job in plan.jobs
            for ref in job.references
        )
        # A blocked result still needs authoritative evidence. If required assets
        # exist but have no attachments, include their blocker source explicitly.
        if blocked and not evidence:
            evidence = ({"source": "APOLLO authority compiler", "subject_id": plan.subject.stable_id},)

        value = {
            "subject_id": plan.subject.stable_id,
            "subject_name": plan.subject.display_name,
            "request_key": plan.request_key,
            "jobs": [
                {
                    "output_type": job.output_type,
                    "ready": job.ready,
                    "reference_roles": [ref.role for ref in job.references],
                    "missing_dependencies": list(job.missing_dependencies),
                }
                for job in plan.jobs
            ],
        }
        if blocked:
            return Resolution(
                owner=self.name,
                predicate=request.predicate,
                status=ResolutionStatus.BLOCKED,
                value=value,
                evidence=evidence,
                blockers=tuple(dict.fromkeys(dep for job in blocked for dep in job.missing_dependencies)),
                do_not_infer=("missing Gold image bytes cannot be replaced by prose or a newly generated lookalike",),
            )
        return Resolution(
            owner=self.name,
            predicate=request.predicate,
            status=ResolutionStatus.KNOWN,
            value=value,
            evidence=evidence,
            do_not_infer=("SYSTEM_PASS does not equal user approval or Gold promotion",),
        )
