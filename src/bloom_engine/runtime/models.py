from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from bloom_engine.contracts.resolution import Resolution
from bloom_engine.pantheon.protocol import CoreRequest


@dataclass(frozen=True, slots=True)
class RuntimeQuery:
    """One explicit sovereign question in a bounded runtime request.

    `fact_keys` are connective labels that become usable only when the sovereign
    resolver returns KNOWN. Declaring a label here never makes the fact true.
    """

    request: CoreRequest
    required_for_request: bool = False
    fact_keys: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SceneAnchor:
    scene_key: str
    arc: str
    episode: str = ""
    time_text: str = ""
    location_ref: str = ""
    present_character_refs: Sequence[str] = field(default_factory=tuple)
    last_beat: str = ""
    hard_guardrails: Sequence[str] = field(default_factory=tuple)
    source_refs: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SceneRequest:
    arc: str
    command: str
    queries: Sequence[RuntimeQuery] = field(default_factory=tuple)
    mode: str = "DRY_RUN"
    realization: str = "PREVIEW"
    authorization_token: str | None = None
    protected_player_domains: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class QueryOutcome:
    query: RuntimeQuery
    resolution: Resolution


@dataclass(frozen=True, slots=True)
class ContextPacket:
    packet_key: str
    contract_version: str
    anchor: SceneAnchor
    query_outcomes: Sequence[QueryOutcome]
    allowed_fact_keys: frozenset[str]
    explicit_unknowns: Sequence[str]
    required_unknowns: Sequence[str]
    degraded_unknowns: Sequence[str]
    blockers: Sequence[str]
    warnings: Sequence[str]
    protected_player_domains: Sequence[str]
    source_snapshot_refs: Sequence[str]


@dataclass(frozen=True, slots=True)
class EligibleOption:
    id: str
    actor_ref: str
    summary: str
    requires_fact_keys: Sequence[str] = field(default_factory=tuple)
    intended_fact_keys: Sequence[str] = field(default_factory=tuple)
    protected_domain: str | None = None


@dataclass(frozen=True, slots=True)
class AthenaDecision:
    selected_option_id: str | None
    fulcrum: str
    result: str
    basis_fact_keys: Sequence[str] = field(default_factory=tuple)
    intended_fact_keys: Sequence[str] = field(default_factory=tuple)
    reason_code: str = ""


@dataclass(frozen=True, slots=True)
class RenderClaim:
    kind: str
    key: str


@dataclass(frozen=True, slots=True)
class CalliopeRender:
    text: str
    claims: Sequence[RenderClaim] = field(default_factory=tuple)
    source_decision_option_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProposedDelta:
    owner: str
    kind: str
    key: str
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ClioEvent:
    event_key: str
    arc: str
    in_world_time: str
    location_ref: str
    location_name: str
    event_type: str
    summary: str
    participant_refs: Sequence[str] = field(default_factory=tuple)
    consequences: Sequence[str] = field(default_factory=tuple)
    source_provenance: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ClioManifest:
    version: str = "CLIO-MANIFEST-v0.3.1"
    event: ClioEvent | None = None
    deltas: Sequence[ProposedDelta] = field(default_factory=tuple)
    invalidations: Sequence[str] = field(default_factory=tuple)
    readback_assertions: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ClioHandoff:
    transaction_key: str
    packet_key: str
    arc: str
    source_run: str
    expected_pre_state_digest: str
    manifest: ClioManifest
    realized: bool
    persistence_authorized: bool
    authorization_token: str | None = None


@dataclass(frozen=True, slots=True)
class ClioResult:
    status: str
    transaction_key: str
    committed_event_ids: Sequence[str] = field(default_factory=tuple)
    applied_delta_keys: Sequence[str] = field(default_factory=tuple)
    readback_verified: bool = False
    message: str = ""


@dataclass(frozen=True, slots=True)
class IntegrityFinding:
    invariant: str
    severity: str
    result: str
    owner: str
    message: str


@dataclass(frozen=True, slots=True)
class AdrasteiaResult:
    status: str
    findings: Sequence[IntegrityFinding] = field(default_factory=tuple)


@dataclass(slots=True)
class RuntimeTrace:
    run_key: str
    request: SceneRequest
    packet: ContextPacket | None = None
    eligible_options: Sequence[EligibleOption] = field(default_factory=tuple)
    athena: AthenaDecision | None = None
    calliope: CalliopeRender | None = None
    clio: ClioResult | None = None
    adrasteia_preflight: AdrasteiaResult | None = None
    adrasteia_postflight: AdrasteiaResult | None = None
    final_status: str = "FAILED"


@dataclass(frozen=True, slots=True)
class RunnerOutput:
    status: str
    trace: RuntimeTrace
    text: str = ""
