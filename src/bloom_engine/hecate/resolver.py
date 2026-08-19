from __future__ import annotations

from typing import Any, Mapping

from bloom_engine.contracts.resolution import Resolution, ResolutionStatus
from bloom_engine.hecate.store import HecateStore
from bloom_engine.pantheon.protocol import CoreRequest, assert_core_may_answer


class HecateResolver:
    name = "HECATE"

    def __init__(self, store: HecateStore):
        self.store = store

    def resolve(self, request: CoreRequest) -> Resolution:
        assert_core_may_answer(self.name, request.predicate)
        if request.predicate == "magic.applicable":
            return self._resolve_applicability(request)
        if request.predicate == "magic.capability":
            return self._resolve_capability(request)
        if request.predicate == "magic.form":
            return self._resolve_form(request)
        if request.predicate == "focus.is_focus":
            return self._resolve_focus(request)
        if request.predicate == "magical_condition.behavior":
            return self._resolve_condition(request)
        if request.predicate == "working.eligible":
            return self._resolve_working_eligibility(request)
        return Resolution(
            owner=self.name,
            predicate=request.predicate,
            status=ResolutionStatus.UNKNOWN,
            evidence=tuple(request.evidence),
            missing_required=("HECATE resolver implementation for this predicate",),
            do_not_infer=("unsupported HECATE predicate must not be guessed",),
        )

    def _resolve_applicability(self, request: CoreRequest) -> Resolution:
        magical_question = request.inputs.get("magical_question")
        if magical_question is False:
            return Resolution(
                owner=self.name,
                predicate=request.predicate,
                status=ResolutionStatus.NOT_APPLICABLE,
                value={"applicable": False},
                metadata={"reason": "No magical predicate is required for the requested ordinary action."},
            )
        if magical_question is True:
            return Resolution(
                owner=self.name,
                predicate=request.predicate,
                status=ResolutionStatus.KNOWN,
                value={"applicable": True},
                evidence=({"source": "request", "fact": "magical_question=true"},),
            )
        return Resolution(
            owner=self.name,
            predicate=request.predicate,
            status=ResolutionStatus.UNKNOWN,
            evidence=tuple(request.evidence),
            missing_required=("whether the request contains an actual magical predicate",),
        )

    def _resolve_capability(self, request: CoreRequest) -> Resolution:
        practitioner_ref = request.inputs.get("practitioner_ref")
        if not practitioner_ref:
            return self._unknown(request, "practitioner_ref")
        profile = self.store.get_profile(str(practitioner_ref))
        if profile is None:
            return self._unknown(request, "Magic Profile for practitioner")
        return Resolution(
            owner=self.name,
            predicate=request.predicate,
            status=ResolutionStatus.KNOWN,
            value={
                "profile_key": profile.key,
                "form_keys": tuple(profile.form_keys),
                "capability_envelope": profile.capability_envelope,
                "constraints": tuple(profile.constraints),
                "resolver_readiness": profile.resolver_readiness,
            },
            evidence=tuple(profile.evidence),
            do_not_infer=tuple(profile.do_not_infer),
        )

    def _resolve_form(self, request: CoreRequest) -> Resolution:
        form_key = request.inputs.get("form_key")
        if not form_key:
            return self._unknown(request, "form_key")
        form = self.store.get_form(str(form_key))
        if form is None:
            return self._unknown(request, "Magic Form record")
        return Resolution(
            owner=self.name,
            predicate=request.predicate,
            status=ResolutionStatus.KNOWN,
            value={
                "form_key": form.key,
                "name": form.name,
                "capability_statement": form.capability_statement,
                "requirements": tuple(form.requirements),
                "focus_roles": tuple(form.focus_roles),
                "costs_or_strain": tuple(form.costs_or_strain),
                "hard_limits": tuple(form.hard_limits),
                "clearing_requirements": tuple(form.clearing_requirements),
                "resolver_readiness": form.resolver_readiness,
            },
            evidence=tuple(form.evidence),
            do_not_infer=tuple(form.do_not_infer),
        )

    def _resolve_focus(self, request: CoreRequest) -> Resolution:
        practitioner_ref = request.inputs.get("practitioner_ref")
        focus_name = request.inputs.get("focus_name")
        if not practitioner_ref or not focus_name:
            return self._unknown(request, "practitioner_ref and focus_name")
        bond = self.store.get_focus_bond(str(practitioner_ref), str(focus_name))
        if bond is None:
            return self._unknown(request, "Focus Bond or explicit non-Focus evidence")
        return Resolution(
            owner=self.name,
            predicate=request.predicate,
            status=ResolutionStatus.KNOWN,
            value={
                "is_focus": bond.is_focus,
                "focus_bond_key": bond.key,
                "roles": tuple(bond.roles),
                "object_ref": bond.object_ref,
                "resolver_readiness": bond.resolver_readiness,
            },
            evidence=tuple(bond.evidence),
            external_prerequisites=(
                ({"owner": "HEPHAESTUS", "predicate": "object.available", "subject_ref": bond.object_ref},)
                if bond.is_focus and bond.object_ref
                else ()
            ),
            do_not_infer=tuple(bond.do_not_infer),
        )

    def _resolve_condition(self, request: CoreRequest) -> Resolution:
        condition_key = request.inputs.get("condition_key")
        if not condition_key:
            return self._unknown(request, "condition_key")
        condition = self.store.get_condition(str(condition_key))
        if condition is None:
            return self._unknown(request, "Magical Condition record")
        if not condition.exact_behavior_known:
            return Resolution(
                owner=self.name,
                predicate=request.predicate,
                status=ResolutionStatus.UNKNOWN,
                value={
                    "condition_key": condition.key,
                    "state": condition.state,
                    "effect_summary": condition.effect_summary,
                },
                evidence=tuple(condition.evidence),
                missing_required=("exact magical behavior/mechanics",),
                do_not_infer=tuple(condition.do_not_infer),
            )
        return Resolution(
            owner=self.name,
            predicate=request.predicate,
            status=ResolutionStatus.KNOWN,
            value={
                "condition_key": condition.key,
                "state": condition.state,
                "effect_summary": condition.effect_summary,
                "requirements_to_maintain": tuple(condition.requirements_to_maintain),
                "costs_or_consequences": tuple(condition.costs_or_consequences),
                "clearing_requirements": tuple(condition.clearing_requirements),
            },
            evidence=tuple(condition.evidence),
            do_not_infer=tuple(condition.do_not_infer),
        )

    def _resolve_working_eligibility(self, request: CoreRequest) -> Resolution:
        practitioner_ref = request.inputs.get("practitioner_ref")
        form_key = request.inputs.get("form_key")
        if not practitioner_ref or not form_key:
            return self._unknown(request, "practitioner_ref and form_key")

        profile = self.store.get_profile(str(practitioner_ref))
        form = self.store.get_form(str(form_key))
        checked_evidence: list[Mapping[str, Any]] = []
        missing: list[str] = []

        if profile is None:
            missing.append("Magic Profile for practitioner")
        else:
            checked_evidence.extend(profile.evidence)
        if form is None:
            missing.append("Magic Form record")
        else:
            checked_evidence.extend(form.evidence)
        if missing:
            return Resolution(
                owner=self.name,
                predicate=request.predicate,
                status=ResolutionStatus.UNKNOWN,
                evidence=tuple(checked_evidence),
                missing_required=tuple(missing),
            )

        assert profile is not None and form is not None
        if form.key not in profile.form_keys:
            return Resolution(
                owner=self.name,
                predicate=request.predicate,
                status=ResolutionStatus.BLOCKED,
                value={"eligible": False, "form_key": form.key},
                evidence=tuple(checked_evidence),
                blockers=("practitioner profile does not establish this form as available",),
            )

        blockers: list[str] = []
        missing_required: list[str] = []
        external_prerequisites: list[Mapping[str, Any]] = []

        # Passage has a locked hard limit: it cannot invent an endpoint.
        if form.key == "HEC-FORM-SIG-PASSAGE":
            endpoint_state = request.inputs.get("genuine_connected_endpoint")
            if endpoint_state is False:
                blockers.append("Passage cannot invent a genuine connected endpoint")
            elif endpoint_state is None:
                missing_required.append("whether a genuine connected endpoint exists")
                external_prerequisites.append(
                    {"owner": "ATLAS", "predicate": "access.connected_endpoint", "required_for": "Passage"}
                )

        known_failed_requirements = tuple(request.inputs.get("known_failed_requirements", ()))
        blockers.extend(str(item) for item in known_failed_requirements)

        if blockers:
            return Resolution(
                owner=self.name,
                predicate=request.predicate,
                status=ResolutionStatus.BLOCKED,
                value={"eligible": False, "form_key": form.key},
                evidence=tuple(checked_evidence),
                blockers=tuple(blockers),
                external_prerequisites=tuple(external_prerequisites),
                do_not_infer=tuple(form.do_not_infer) + tuple(profile.do_not_infer),
            )

        if missing_required:
            return Resolution(
                owner=self.name,
                predicate=request.predicate,
                status=ResolutionStatus.UNKNOWN,
                value={"form_key": form.key},
                evidence=tuple(checked_evidence),
                missing_required=tuple(missing_required),
                external_prerequisites=tuple(external_prerequisites),
                do_not_infer=tuple(form.do_not_infer) + tuple(profile.do_not_infer),
            )

        return Resolution(
            owner=self.name,
            predicate=request.predicate,
            status=ResolutionStatus.KNOWN,
            value={
                "eligible": True,
                "form_key": form.key,
                "requirements": tuple(form.requirements),
                "focus_roles": tuple(form.focus_roles),
                "costs_or_strain": tuple(form.costs_or_strain),
                "hard_limits": tuple(form.hard_limits),
                "clearing_requirements": tuple(form.clearing_requirements),
            },
            evidence=tuple(checked_evidence),
            external_prerequisites=tuple(external_prerequisites),
            do_not_infer=tuple(form.do_not_infer) + tuple(profile.do_not_infer),
        )

    def _unknown(self, request: CoreRequest, missing: str) -> Resolution:
        return Resolution(
            owner=self.name,
            predicate=request.predicate,
            status=ResolutionStatus.UNKNOWN,
            evidence=tuple(request.evidence),
            missing_required=(missing,),
        )
