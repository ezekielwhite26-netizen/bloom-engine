from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from bloom_engine.contracts.resolution import Resolution
from bloom_engine.pantheon.protocol import CoreRequest, SovereignCore, resolve_with_owner_guard
from bloom_engine.pantheon.registry import owner_for


class CoreUnavailableError(LookupError):
    """Infrastructure failure: the sovereign owner exists but no resolver is installed.

    This is deliberately not represented as domain UNKNOWN. UNKNOWN means the
    sovereign core was actually asked and the fact is unresolved; a missing
    resolver is a runtime/configuration failure and must stay distinguishable.
    """


@dataclass(slots=True)
class CoreGateway:
    """Single provider-neutral call surface for a future Runtime Runner.

    The gateway routes by sovereign predicate ownership only. It does not infer
    facts, compile context, choose outcomes, render prose, or persist anything.
    """

    _cores: dict[str, SovereignCore] = field(default_factory=dict)

    def register(self, core: SovereignCore) -> None:
        name = core.name.upper()
        if name in self._cores and self._cores[name] is not core:
            raise ValueError(f"resolver already registered for sovereign core {name}")
        self._cores[name] = core

    def register_many(self, cores: Iterable[SovereignCore]) -> None:
        for core in cores:
            self.register(core)

    def resolve(self, request: CoreRequest) -> Resolution:
        owner = owner_for(request.predicate)
        core = self._cores.get(owner.name)
        if core is None:
            raise CoreUnavailableError(
                f"no executable resolver installed for sovereign owner {owner.name} "
                f"of predicate {request.predicate!r}"
            )
        return resolve_with_owner_guard(core, request)

    def resolve_many(self, requests: Iterable[CoreRequest]) -> tuple[Resolution, ...]:
        """Resolve in request order; never collapse or cross-promote results."""
        return tuple(self.resolve(request) for request in requests)

    @property
    def installed_cores(self) -> tuple[str, ...]:
        return tuple(sorted(self._cores))
