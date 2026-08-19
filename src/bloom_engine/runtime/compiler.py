from __future__ import annotations

from typing import Any, Iterable

from bloom_engine.contracts.resolution import ResolutionStatus
from bloom_engine.pantheon.gateway import CoreGateway
from bloom_engine.runtime.models import ContextPacket, QueryOutcome, RuntimeQuery, SceneAnchor, SceneRequest


def _packet_key(anchor: SceneAnchor) -> str:
    return f"CTX::{anchor.scene_key}::PANTHEON-v1"


def _warning_strings(metadata: Any) -> tuple[str, ...]:
    if not isinstance(metadata, dict):
        return ()
    warnings = metadata.get("warnings", ())
    if isinstance(warnings, str):
        return (warnings,)
    if isinstance(warnings, Iterable):
        return tuple(str(item) for item in warnings)
    return ()


def compile_context(request: SceneRequest, anchor: SceneAnchor, gateway: CoreGateway) -> ContextPacket:
    """Compile a bounded packet from explicit sovereign queries only.

    The compiler never answers a predicate. It routes each query through the
    CoreGateway, preserves the exact result, and only exposes declared fact keys
    when the owning core returned KNOWN.
    """

    outcomes: list[QueryOutcome] = []
    allowed_fact_keys: set[str] = set()
    explicit_unknowns: list[str] = []
    required_unknowns: list[str] = []
    degraded_unknowns: list[str] = []
    blockers: list[str] = []
    warnings: list[str] = []

    for query in request.queries:
        resolution = gateway.resolve(query.request)
        outcomes.append(QueryOutcome(query=query, resolution=resolution))

        if resolution.status is ResolutionStatus.KNOWN:
            allowed_fact_keys.update(str(key) for key in query.fact_keys)

        elif resolution.status is ResolutionStatus.UNKNOWN:
            detail = "|".join(str(item) for item in resolution.missing_required) or "UNKNOWN"
            label = f"{resolution.owner}:{resolution.predicate}:{detail}"
            explicit_unknowns.append(label)
            if query.required_for_request:
                required_unknowns.append(label)
                blockers.append(f"{resolution.owner}:REQUIRED_UNKNOWN:{resolution.predicate}:{detail}")
            else:
                degraded_unknowns.append(label)

        elif resolution.status is ResolutionStatus.BLOCKED:
            detail = "|".join(str(item) for item in resolution.blockers) or "BLOCKED"
            blockers.append(f"{resolution.owner}:BLOCKED:{resolution.predicate}:{detail}")

        elif resolution.status is ResolutionStatus.NOT_APPLICABLE and query.required_for_request:
            blockers.append(
                f"{resolution.owner}:REQUIRED_NOT_APPLICABLE:{resolution.predicate}"
            )

        warnings.extend(
            f"{resolution.owner}:{resolution.predicate}:{warning}"
            for warning in _warning_strings(resolution.metadata)
        )

    return ContextPacket(
        packet_key=_packet_key(anchor),
        contract_version="BLOOM-PANTHEON-RUNTIME-v1",
        anchor=anchor,
        query_outcomes=tuple(outcomes),
        allowed_fact_keys=frozenset(allowed_fact_keys),
        explicit_unknowns=tuple(explicit_unknowns),
        required_unknowns=tuple(required_unknowns),
        degraded_unknowns=tuple(degraded_unknowns),
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        protected_player_domains=tuple(request.protected_player_domains),
        source_snapshot_refs=tuple(anchor.source_refs),
    )
