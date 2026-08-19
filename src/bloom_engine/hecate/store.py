from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from bloom_engine.hecate.models import FocusBond, MagicForm, MagicalCondition, MagicProfile


class HecateStore(Protocol):
    def get_form(self, key: str) -> MagicForm | None: ...
    def get_profile(self, practitioner_ref: str) -> MagicProfile | None: ...
    def get_focus_bond(self, practitioner_ref: str, focus_name: str) -> FocusBond | None: ...
    def get_condition(self, key: str) -> MagicalCondition | None: ...


@dataclass(slots=True)
class InMemoryHecateStore:
    forms: dict[str, MagicForm] = field(default_factory=dict)
    profiles: dict[str, MagicProfile] = field(default_factory=dict)
    focus_bonds: dict[tuple[str, str], FocusBond] = field(default_factory=dict)
    conditions: dict[str, MagicalCondition] = field(default_factory=dict)

    def get_form(self, key: str) -> MagicForm | None:
        return self.forms.get(key)

    def get_profile(self, practitioner_ref: str) -> MagicProfile | None:
        return self.profiles.get(practitioner_ref)

    def get_focus_bond(self, practitioner_ref: str, focus_name: str) -> FocusBond | None:
        return self.focus_bonds.get((practitioner_ref, focus_name))

    def get_condition(self, key: str) -> MagicalCondition | None:
        return self.conditions.get(key)
