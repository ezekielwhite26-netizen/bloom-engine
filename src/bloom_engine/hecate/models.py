from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class MagicForm:
    key: str
    name: str
    capability_statement: str
    requirements: Sequence[str] = field(default_factory=tuple)
    focus_roles: Sequence[str] = field(default_factory=tuple)
    costs_or_strain: Sequence[str] = field(default_factory=tuple)
    hard_limits: Sequence[str] = field(default_factory=tuple)
    clearing_requirements: Sequence[str] = field(default_factory=tuple)
    resolver_readiness: str = "PARTIAL"
    evidence: Sequence[Mapping[str, str]] = field(default_factory=tuple)
    do_not_infer: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class MagicProfile:
    key: str
    practitioner_ref: str
    form_keys: Sequence[str]
    capability_envelope: str
    constraints: Sequence[str] = field(default_factory=tuple)
    resolver_readiness: str = "PARTIAL"
    evidence: Sequence[Mapping[str, str]] = field(default_factory=tuple)
    do_not_infer: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class FocusBond:
    key: str
    practitioner_ref: str
    focus_name: str
    is_focus: bool
    related_form_keys: Sequence[str] = field(default_factory=tuple)
    roles: Sequence[str] = field(default_factory=tuple)
    object_ref: str | None = None
    resolver_readiness: str = "PARTIAL"
    evidence: Sequence[Mapping[str, str]] = field(default_factory=tuple)
    do_not_infer: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class MagicalCondition:
    key: str
    subject_ref: str
    state: str
    effect_summary: str | None = None
    exact_behavior_known: bool = False
    requirements_to_maintain: Sequence[str] = field(default_factory=tuple)
    costs_or_consequences: Sequence[str] = field(default_factory=tuple)
    clearing_requirements: Sequence[str] = field(default_factory=tuple)
    evidence: Sequence[Mapping[str, str]] = field(default_factory=tuple)
    do_not_infer: Sequence[str] = field(default_factory=tuple)
