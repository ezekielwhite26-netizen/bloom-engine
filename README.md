# BLOOM Engine

Headless BLOOM cognitive runtime and Ama backend.

## Hosted Ama read surface

The Render-hosted `ama-runtime` service exposes authenticated, read-only BLOOM operations.

- `GET /v1/capabilities` — capability contract.
- `POST /v1/runtime/preview` — verified current-scene inspection only; no canonical persistence.
- `POST /v1/manuscript/context` — issues a temporary, bounded manuscript-authoring evidence context from existing BLOOM authoring/canon tables.
- `POST /v1/manuscript/review` — ADRASTEIA review of declared manuscript claims against an issued context.

### Manuscript safety contract

The hosted manuscript path is connective authoring infrastructure, not a new sovereign engine.

- CALLIOPE/Ama drafts and revises prose.
- ADRASTEIA diagnoses unsupported canon, agency violations, reader-orientation gaps, and epistemic violations.
- ADRASTEIA never returns replacement prose.
- Historical manuscript mode avoids importing later mutable state backward into earlier chapters.
- Only approved Gold Prose is loaded as Gold.
- Reader state is reconstructed only from Writing Runs explicitly marked committed.
- Hosted manuscript preview cannot commit the Reader Knowledge Ledger.
- Manuscript endpoints never invoke CLIO and never persist story canon.

Production regression coverage includes the contracts represented by `BLM-TST-000145`, `BLM-TST-000146`, and `BLM-TST-000147`.
