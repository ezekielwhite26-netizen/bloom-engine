# Runtime v0.3.1 Port Plan

Status: INTEGRATION BRANCH PREP

This document records the clean-port boundary for the certified `ama-runtime-v0.3` work in legacy `bloomenginev1`.

## Source branch

- Repository: `ezekielwhite26-netizen/bloomenginev1`
- Branch: `ama-runtime-v0.3`
- Current milestone reviewed: Ama Runtime v0.3.1

## Port, do not merge wholesale

The legacy branch contains useful headless runtime logic, but the clean `bloom-engine` repository already owns the 15-core registry, sovereign predicate routing, HECATE resolver, and Python test harness. The runtime is therefore being translated onto the clean contracts rather than copied as a second authority system.

## Preserved behaviors

1. User/agent request enters a connective runtime layer, not a sixteenth sovereign core.
2. Context compilation only assembles owner-attributed core results.
3. Required UNKNOWN fails closed; incidental UNKNOWN remains explicit degraded scope.
4. ATHENA may choose only from eligible options and may not invent supporting facts.
5. Protected player/creative fulcrums return control to the user.
6. CALLIOPE may render validated reality but may not create unsupported factual claims.
7. Permission and write authority are outside the model path.
8. CLIO receives explicit realization + authorization, is idempotent by transaction key, and requires readback before a commit can count as verified.
9. ADRASTEIA preflight/postflight validation is independent of the producing component.
10. Runtime traces remain operational evidence, not canon.

## Clean-repo adaptations

- Legacy BODY resolver arrays are replaced by `CoreGateway` and the 15-core predicate registry.
- Scene requests carry explicit `CoreRequest` query manifests rather than forcing every core to answer every turn.
- Existing clean `Resolution` and HECATE contracts remain controlling.
- Missing resolver implementation is an infrastructure error (`CoreUnavailableError`), never domain UNKNOWN.
- Real Airtable Event/state writes remain disabled in this port until the production CLIO executor, stable-ID reservation, owner-specific delta execution, invalidation, and readback path are separately certified.

## First integration target

`Ama/runtime request -> RuntimeRunner -> ContextCompiler -> CoreGateway -> HECATE -> ADRASTEIA -> ATHENA adapter -> CALLIOPE adapter -> gated CLIO -> verified result`

The first certification fixtures must prove KNOWN, UNKNOWN, BLOCKED, NOT_APPLICABLE, unsupported CALLIOPE claims, protected fulcrums, no-token/no-write, and idempotent CLIO retry behavior.
