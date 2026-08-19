# Ama integration notes v0.1

## Purpose

This note records how the currently separate Ama/BLOOM preparation branches relate to one another without merging authority surfaces or duplicating legacy implementation. It is documentation only.

## Certified clean-runtime stack

The clean `bloom-engine` Ama stack currently forms this sequence:

1. `runtime-persistence-v0.3.3` / draft PR #6 — production-shaped CLIO persistence machinery, still not connected to live story writes.
2. `ama-api-boundary-v0.1` / draft PR #7 — authenticated read/preview-only FastAPI boundary; no persistence endpoint.
3. `ama-authoritative-builder-v0.1` / draft PR #8 — provider-neutral trusted request builder that maps reviewed high-level Ama intents to owner-routed READ-only SceneRequests and fails closed on unsupported intent.
4. `ama-action-schema-v0.1` / draft PR #9 — bounded Custom GPT/OpenAPI export containing capabilities + preview only; no health, raw resolver, commit, or persistence operation.
5. `ama-ops-hardening-v0.1` / draft PR #11 — secret-redacted request correlation and deployment-readiness gates; no hosting or persistence enablement.
6. `ama-transport-recovery-tests-v0.1` / draft PR #12 — hosted-shaped transport fixtures and CLIO recovery regressions using mocks/in-memory fixtures only.

PR #12 is certified by BLOOM CI #31 PASS at head `abd9b5934d8743ca6c37d358d714c5ed755f1cd9`.

## Legacy Ama branches inspected

Repository: `ezekielwhite26-netizen/bloomenginev1`.

### `ama-gpt-shell-v0.1`

Inspected head: `0c9dd1c45164261791eb6c445962f76b88482121`.
Latest commit: `Add Ama custom GPT instructions` (2026-08-19 10:30:27Z).

Integration decision:
- Treat this branch as human-facing identity/instruction preparation only.
- Do not copy legacy runtime authority into the GPT shell.
- The private GPT should call the bounded Action schema from the clean stack rather than asserting sovereign facts directly.
- GPT instructions may shape tone, collaboration style, uncertainty handling, and request intent, but they must not grant write capability, fabricate evidence, select sovereign answers, or bypass UNKNOWN.

### `ama-runtime-v0.3.3`

Inspected head: `db97c4761f9ce8eacff7233aa71aec87d1ce0455`.
Latest commit: `Document Ama runtime v0.3.3 continuity bridge` (2026-08-19 17:28:18Z).

Integration decision:
- Its persistence/recovery behavior has already been deliberately ported into the clean Python runtime through PR #6 rather than merging the legacy web/game repository.
- Do not re-import the legacy runner, UI/game code, model adapters, or old orchestration wholesale.
- Future parity checks should compare behavior/contracts, not file-for-file implementation.

## Parallel clean-runtime branch requiring explicit review

### `ama-api-v0.1` / draft PR #10

This branch exposes a separate HTTP design including a gated commit route. The read-only Custom GPT stack intentionally does not adopt that route.

Before any future integration, review must answer all of the following:

- Is a public/hosted commit endpoint needed at all for Ama's first private-GPT phase?
- If retained later, is write authority minted exclusively server-side and independently of model/client input?
- Does the endpoint remain disabled by default and fail closed when persistence capability is absent?
- Are CLIO, ADRASTEIA, one-owner sovereignty, exact stable identities, and idempotent persistence still mandatory downstream gates?
- Is the Custom GPT Action schema kept read/preview-only even if an internal commit service eventually exists?

Until those questions are explicitly resolved, PR #10 should remain an isolated alternative authority surface and must not be silently stacked into the private GPT path.

## Private Ama integration boundary

Recommended first-phase data flow:

`Ama GPT shell -> bounded Action intent -> authenticated read/preview API -> trusted AmaRequestBuilder -> owner-routed SceneRequest -> sovereign cores -> ADRASTEIA -> preview response`

The following must stay outside client/model control:

- authoritative evidence
- sovereign query manifests
- core answer/resolution status
- capability/write tokens
- CLIO authorization
- persistence-enable flags
- stable Event ID allocation
- direct canon mutation

A model may ask a question. It may not make the answer authoritative.

## Aster Hollow continuity note

The Aster Hollow Compendium remains the campaign's highest canon source unless deliberately revised. Runtime/context packets are disposable working state, not a replacement for authoritative canon. Any future Ama live-play integration must therefore preserve source provenance, stable identity, and UNKNOWN on absent structured facts rather than backfilling from conversational convenience.

## Current blockers before real hosting or persistence

The safe engineering queue is not blocked, but actual hosting/live persistence remains intentionally gated. Before any deployment or live-story write, the project still needs explicit review of secrets/hosting configuration, provider-side logging behavior, real hosted transport acceptance, final authority-surface selection, and a separately authorized live-write rehearsal plan that does not begin with Aster Hollow production canon.

## No-actions statement

This integration-note branch does not merge PRs, deploy services, publish a GPT, spend paid credits, reserve `BLM-EVT-*` IDs, mutate Aster Hollow canon, write live Airtable story state, enable automatic live-play persistence, or grant a model write authority.
