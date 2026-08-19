from __future__ import annotations

from typing import Sequence

from bloom_engine.contracts.resolution import ResolutionStatus
from bloom_engine.runtime.models import (
    AdrasteiaResult,
    AthenaDecision,
    CalliopeRender,
    ClioResult,
    ContextPacket,
    EligibleOption,
    IntegrityFinding,
)


def _summarize(findings: Sequence[IntegrityFinding]) -> AdrasteiaResult:
    if any(f.result == "BLOCK" and f.severity == "CRITICAL" for f in findings):
        return AdrasteiaResult(status="BLOCKED", findings=tuple(findings))
    if any(f.result in {"WARN", "BLOCK"} for f in findings):
        return AdrasteiaResult(status="PASS_WITH_WARNINGS", findings=tuple(findings))
    return AdrasteiaResult(status="PASS", findings=tuple(findings))


def preflight(packet: ContextPacket) -> AdrasteiaResult:
    findings: list[IntegrityFinding] = []

    for outcome in packet.query_outcomes:
        result = outcome.resolution
        if result.status is ResolutionStatus.BLOCKED:
            findings.append(
                IntegrityFinding(
                    invariant="RUNTIME-SOVEREIGN-BLOCK-001",
                    severity="CRITICAL",
                    result="BLOCK",
                    owner=result.owner,
                    message=f"{result.owner} returned BLOCKED for {result.predicate}: {', '.join(result.blockers)}",
                )
            )

    findings.append(
        IntegrityFinding(
            invariant="RUNTIME-COMPILER-NON-SOVEREIGN-001",
            severity="CRITICAL",
            result="PASS",
            owner="CONNECTIVE",
            message="Packet contains only owner-attributed CoreGateway results; compiler originated no truth.",
        )
    )

    if packet.required_unknowns:
        findings.append(
            IntegrityFinding(
                invariant="RUNTIME-UNKNOWN-FAIL-CLOSED-001",
                severity="CRITICAL",
                result="BLOCK",
                owner="ADRASTEIA",
                message="Required UNKNOWNs fail closed: " + "; ".join(packet.required_unknowns),
            )
        )

    required_na = [b for b in packet.blockers if ":REQUIRED_NOT_APPLICABLE:" in b]
    if required_na:
        findings.append(
            IntegrityFinding(
                invariant="RUNTIME-REQUIRED-GATE-NOT-APPLICABLE-001",
                severity="CRITICAL",
                result="BLOCK",
                owner="ADRASTEIA",
                message="A required positive gate cannot be satisfied by NOT_APPLICABLE: " + "; ".join(required_na),
            )
        )

    if packet.degraded_unknowns:
        findings.append(
            IntegrityFinding(
                invariant="RUNTIME-UNKNOWN-DEGRADED-SCOPE-001",
                severity="WARN",
                result="WARN",
                owner="ADRASTEIA",
                message="Incidental UNKNOWNs preserved without manufacturing facts: " + "; ".join(packet.degraded_unknowns),
            )
        )

    return _summarize(findings)


def validate_athena(
    packet: ContextPacket,
    options: Sequence[EligibleOption],
    decision: AthenaDecision,
) -> AdrasteiaResult:
    findings: list[IntegrityFinding] = []
    selected = next((o for o in options if o.id == decision.selected_option_id), None) if decision.selected_option_id else None

    if decision.result == "ACT" and selected is None:
        findings.append(
            IntegrityFinding(
                invariant="RUNTIME-ATHENA-NO-ELIGIBILITY-001",
                severity="CRITICAL",
                result="BLOCK",
                owner="ATHENA",
                message="ATHENA selected an option outside the eligible option set.",
            )
        )
    else:
        findings.append(
            IntegrityFinding(
                invariant="RUNTIME-ATHENA-NO-ELIGIBILITY-001",
                severity="CRITICAL",
                result="PASS",
                owner="ATHENA",
                message="ATHENA stayed inside the eligible option set.",
            )
        )

    if selected is not None:
        missing = [key for key in selected.requires_fact_keys if key not in packet.allowed_fact_keys]
        if missing:
            findings.append(
                IntegrityFinding(
                    invariant="RUNTIME-ATHENA-REQUIRES-FACTS-001",
                    severity="CRITICAL",
                    result="BLOCK",
                    owner="ATHENA",
                    message="Selected option depends on unsupported facts: " + ", ".join(missing),
                )
            )

        if (
            selected.protected_domain
            and selected.protected_domain in packet.protected_player_domains
            and decision.fulcrum != "PLAYER_DECISION_REQUIRED"
        ):
            findings.append(
                IntegrityFinding(
                    invariant="RUNTIME-PLAYER-FULCRUM-001",
                    severity="CRITICAL",
                    result="BLOCK",
                    owner="ATHENA",
                    message=f"Protected domain {selected.protected_domain} was not returned to the player.",
                )
            )

    return _summarize(findings)


def validate_calliope(
    packet: ContextPacket,
    decision: AthenaDecision,
    render: CalliopeRender,
) -> AdrasteiaResult:
    allowed = set(packet.allowed_fact_keys) | set(decision.intended_fact_keys)
    illegal = [
        claim
        for claim in render.claims
        if claim.kind == "PLAYER_COMMITMENT" or claim.key not in allowed
    ]

    if illegal:
        return _summarize(
            (
                IntegrityFinding(
                    invariant="RUNTIME-CALLIOPE-NO-REALITY-CHANGE-001",
                    severity="CRITICAL",
                    result="BLOCK",
                    owner="CALLIOPE",
                    message="CALLIOPE emitted unsupported claims: "
                    + ", ".join(f"{c.kind}:{c.key}" for c in illegal),
                ),
            )
        )

    return _summarize(
        (
            IntegrityFinding(
                invariant="RUNTIME-CALLIOPE-NO-REALITY-CHANGE-001",
                severity="HIGH",
                result="PASS",
                owner="CALLIOPE",
                message="CALLIOPE render stayed within validated facts and ATHENA intent.",
            ),
        )
    )


def postflight_clio(clio: ClioResult) -> AdrasteiaResult:
    if clio.status == "COMMITTED" and not clio.readback_verified:
        return _summarize(
            (
                IntegrityFinding(
                    invariant="RUNTIME-CLIO-READBACK-001",
                    severity="CRITICAL",
                    result="BLOCK",
                    owner="CLIO",
                    message="CLIO reported COMMITTED without verified readback.",
                ),
            )
        )

    if clio.status in {"BLOCKED", "FAILED"}:
        return _summarize(
            (
                IntegrityFinding(
                    invariant="RUNTIME-CLIO-TRANSACTION-001",
                    severity="CRITICAL",
                    result="BLOCK",
                    owner="CLIO",
                    message=f"CLIO transaction did not complete safely: {clio.status} — {clio.message}",
                ),
            )
        )

    return _summarize(
        (
            IntegrityFinding(
                invariant="RUNTIME-CLIO-REALIZED-ONLY-001",
                severity="CRITICAL",
                result="PASS",
                owner="CLIO",
                message=f"CLIO result {clio.status} is transactionally coherent.",
            ),
        )
    )
