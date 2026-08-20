# APOLLO Visual Runtime — Preview Deployment Checklist

Status: **PREP ONLY — DO NOT DEPLOY FROM THIS DOCUMENT**

This checklist exists so the APOLLO preview can be deployed deliberately after explicit approval. It does not authorize a deploy, provider spend, image generation, or canon mutation.

## 1. Deployment target

Use the APOLLO composition root rather than replacing the proven read-only module in-place:

```text
uvicorn bloom_engine.app:app --host 0.0.0.0 --port $PORT
```

`bloom_engine.app:app` composes the existing Ama/BLOOM read surface with the APOLLO router behind the same bearer boundary. The existing `bloom_engine.api:app` entrypoint remains a rollback target.

Recommended first preview:

- branch: `apollo-visual-runtime-v0.1`
- auto-deploy: disabled for the first APOLLO preview
- deploy only after GitHub CI is green at the exact head SHA
- do not merge the draft PR merely to create the preview

## 2. Required server-side environment

Never place these values in source, prompts, screenshots, public docs, or client-side code.

| Variable | Required for | Notes |
|---|---|---|
| `AIRTABLE_PAT` | planning/readiness/jobs/candidate storage | Existing BLOOM Airtable service credential |
| `BLOOM_AIRTABLE_BASE_ID` | Airtable routing | Defaults in code only for the current development base; set explicitly in preview |
| `BLOOM_API_BEARER_TOKEN_SHA256` | user-facing authenticated API | Prefer a fresh preview bearer hash |
| `BFL_API_KEY` | FLUX.2 Pro renderer | Not required for readiness/plan-only validation |
| `OPENAI_API_KEY` | GPT Image 2 repair + GPT-5.6 critic | Not required for readiness/plan-only validation |
| `BLOOM_APOLLO_ADMIN_TOKEN_SHA256` | operator-only reference attachment ingestion | Separate from the normal Ama bearer; route is excluded from public OpenAPI |

Do not configure paid-provider keys until the no-spend readiness/plan path is proven unless there is a specific reason to do so.

## 3. Gold/reference byte prerequisite

Curated authority metadata and actual image bytes are separate requirements.

Before a generation slot may become ready:

1. the Visual Asset must already have an approved status;
2. it must already have an explicit `APOLLO Authority Role`;
3. subject-scoped assets must already link to the correct Saga Entity;
4. the approved image bytes must exist in the Visual Assets attachment field;
5. the authority compiler must resolve exactly one consumed Gold authority per role.

The operator-only attachment-ingest path may attach bytes to an already-curated record. It cannot assign roles, change status/reference strength, or promote canon. Existing attachments are not silently replaced.

## 4. Zero-spend smoke test order

Run these in order after a preview is deployed:

1. `GET /health`
2. `GET /v1/capabilities`
3. `GET /v1/visual/capabilities`
4. `POST /v1/visual/readiness` for Florence
5. `POST /v1/visual/plan` for one Florence slot
6. `POST /v1/visual/plan` for the Florence production pack
7. repeat readiness/plan for at least one generic-character pack

Expected invariants:

- bearer authentication is enforced on every APOLLO user-facing route;
- readiness and plan report `spent=false`/no renderer invocation;
- missing bytes are reported separately from missing authority;
- `Aster Hollow` ARC-scoped style authority resolves into `Aster Hollow / At the Threshold`;
- duplicate unused secondary references do not block a pack;
- duplicate consumed Gold authority does block a pack;
- no candidate record is created by readiness or plan.

## 5. Paid generation gate

Do **not** use `/v1/visual/generate` during deployment smoke testing unless the current user request explicitly asks to generate/edit an image.

When a paid test is eventually authorized:

- `confirm_spend=true` must be present in that exact request;
- start with `SINGLE_ASSET` and a conservative `max_renderer_calls` value;
- verify the durable Visual Batch job record;
- verify generated candidate persistence;
- verify the critic result;
- verify `SYSTEM_PASS` remains human-review-only;
- verify no APOLLO Authority Role, Approved Anchor, or Gold Standard is assigned automatically;
- verify a host restart does not auto-retry a paid job.

## 6. Rollback

If the APOLLO preview fails before a paid run:

- restore/start the service with `bloom_engine.api:app`;
- leave the draft APOLLO PR unmerged;
- preserve diagnostics and the Visual Batch operational record where applicable.

If a paid run has started, do not automatically replay it after restart. The durable job should remain paused/recovery-required until explicitly inspected.

## 7. Promotion criteria

Do not merge or designate the APOLLO runtime release-ready until all of the following are true:

- CI green at exact candidate SHA;
- Gold/reference bytes available for the intended vertical slice;
- readiness and plan verified against live BLOOM data;
- authentication verified;
- provider keys server-side only;
- one explicitly authorized single-asset generation completes end-to-end;
- candidate remains non-canon until human approval;
- rollback path tested or independently verified.
