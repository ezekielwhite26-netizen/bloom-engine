from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class CoreSpec:
    name: str
    domain: str
    predicate_prefixes: tuple[str, ...]

    def owns(self, predicate: str) -> bool:
        return any(predicate.startswith(prefix) for prefix in self.predicate_prefixes)


CORE_SPECS: tuple[CoreSpec, ...] = (
    CoreSpec("THEMIS", "canon identity, sources, authority, stable IDs", ("canon.", "identity.", "source.", "authority.", "stable_id.")),
    CoreSpec("CHRONOS", "time, schedules, temporal boundaries", ("time.", "schedule.", "temporal.")),
    CoreSpec("ATLAS", "space, locations, routes, travel, access", ("space.", "location.", "route.", "travel.", "access.")),
    CoreSpec("HEPHAESTUS", "objects, material state, possession", ("object.", "possession.", "material.")),
    CoreSpec("MNEMOSYNE", "character self, personality, personal memory", ("self.", "personality.", "personal_memory.")),
    CoreSpec("HERA", "relationships, groups, genealogy, social bonds", ("relationship.", "group.", "genealogy.", "social_bond.")),
    CoreSpec("ANANKE", "causality, fate, forecast, dependencies", ("causality.", "fate.", "forecast.", "dependency.")),
    CoreSpec("HECATE", "magic, Workings, magical conditions, Focus bonds", ("magic.", "working.", "focus.", "magical_condition.")),
    CoreSpec("APOLLO", "visual identity, art, Atelier", ("visual.", "art.", "atelier.")),
    CoreSpec("HERMES", "knowledge, claims, transmission, epistemics", ("knowledge.", "claim.", "transmission.", "epistemic.")),
    CoreSpec("EUNOMIA", "organizations, collective actors, institutional action", ("organization.", "institution.", "collective_action.")),
    CoreSpec("ATHENA", "decisions, hidden checks, foreground choice, fulcrums", ("decision.", "check.", "fulcrum.")),
    CoreSpec("CALLIOPE", "narrative and dialogue rendering", ("render.", "narrative.", "dialogue.")),
    CoreSpec("CLIO", "realized history, persistence, checkpoints, transactions", ("history.", "persist.", "checkpoint.", "transaction.")),
    CoreSpec("ADRASTEIA", "independent integrity enforcement and validation", ("integrity.", "validate.", "gate.")),
)

CORE_BY_NAME = {spec.name: spec for spec in CORE_SPECS}


class OwnershipError(ValueError):
    pass


def owners_for(predicate: str) -> tuple[CoreSpec, ...]:
    return tuple(spec for spec in CORE_SPECS if spec.owns(predicate))


def owner_for(predicate: str) -> CoreSpec:
    owners = owners_for(predicate)
    if len(owners) != 1:
        raise OwnershipError(
            f"predicate {predicate!r} must have exactly one sovereign owner; "
            f"found {[owner.name for owner in owners]}"
        )
    return owners[0]


def assert_registry_has_unique_prefix_ownership(specs: Iterable[CoreSpec] = CORE_SPECS) -> None:
    specs = tuple(specs)
    seen: dict[str, str] = {}
    for spec in specs:
        for prefix in spec.predicate_prefixes:
            if prefix in seen:
                raise OwnershipError(
                    f"predicate prefix {prefix!r} is claimed by both {seen[prefix]} and {spec.name}"
                )
            seen[prefix] = spec.name
