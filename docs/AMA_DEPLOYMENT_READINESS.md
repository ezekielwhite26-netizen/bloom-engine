# Ama Deployment Readiness

Status: PRE-DEPLOYMENT ONLY. This document does not authorize hosting or persistence.

## Current safe surface

- `/health` is liveness-only.
- `/v1/capabilities` requires bearer authentication.
- `/v1/runtime/preview` requires bearer authentication and may only create PREVIEW, READ-only internal requests.
- Custom GPT Action schema remains bounded to capabilities + preview.
- No raw sovereign resolver endpoint is public.
- No persistence/commit endpoint is part of this branch.

## Secrets and logging

- `BLOOM_API_BEARER_TOKEN` must be supplied by the hosting secret store, never committed.
- Token length minimum remains 24 characters; production should use a cryptographically random value.
- BLOOM access logs contain only request ID, method, path, and status code.
- Authorization headers, request bodies, query strings, model prompts, story text, sovereign evidence, and capability tokens must not be logged.
- `X-Request-ID` may be accepted only when it matches the bounded opaque correlation format; otherwise BLOOM mints a server ID.

## Required gates before any deployment

1. Run full CI on the exact deployment commit.
2. Confirm Action OpenAPI server URL uses HTTPS and contains no embedded credentials.
3. Configure bearer token in provider secret storage.
4. Verify provider/platform request logs do not capture Authorization headers or bodies by default; disable/redact them if necessary.
5. Verify TLS termination, health check, process command, and restart behavior with a non-production fixture environment.
6. Exercise authenticated capabilities and preview over hosted HTTPS using fixture-backed runtime only.
7. Confirm responses carry `X-Request-ID` and logs can correlate failures without secrets.
8. Confirm no route matching commit/write/persist exists in the Custom GPT Action schema.
9. Do not enable live Airtable story writes, Event ID allocation, or automatic live-play persistence as part of transport acceptance.

## Later persistence gate

Persistence activation is a separate review. It requires an explicitly reviewed non-model authority path, canonical Airtable adapter acceptance, exact readback verification, retry/recovery certification, and a deliberately tiny authorized test transaction. Transport readiness alone is not persistence authorization.
