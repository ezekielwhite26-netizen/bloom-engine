# Ama external API boundary v0.1

Status: **TEST CANDIDATE / NOT LIVE**

This boundary is the intended first HTTPS-facing surface for Ama. It is not a sovereign core and owns no world truth.

## Trust boundary

External clients, including a Custom GPT, are untrusted with respect to authoritative BLOOM state.

The client may send ordinary intent such as:

- project/arc
- command
- requested actor stable ID
- requested target location stable ID
- requested object stable ID
- whether a visual result was requested

The client may **not** send:

- sovereign query manifests
- authoritative evidence
- pre-resolved facts
- KNOWN / UNKNOWN / BLOCKED status assertions
- write capability tokens
- persistence manifests

A trusted server-side `AmaRequestBuilder` converts client intent into an internal `SceneRequest`. That builder is responsible for consulting BLOOM and constructing explicit owner-routed queries.

## v0.1 endpoints

### `GET /health`

Public liveness only. It exposes no project/runtime state.

### `GET /v1/capabilities`

Bearer-authenticated. Advertises the actual boundary rather than implying features that are not live.

Current values intentionally include:

- runtime preview: enabled
- runtime commit: disabled
- production persistence: disabled
- raw sovereign query API: disabled
- client-supplied authoritative evidence: disabled
- model-minted write authority: disabled

### `POST /v1/runtime/preview`

Bearer-authenticated and read/preview only.

The server rejects its own request builder if it produces any of the following:

- `realization != PREVIEW`
- an authorization capability token
- a sovereign query whose permission mode is not `READ`

This is defense in depth: a future bug in request-building code should fail closed before the Runtime Runner executes.

## Authentication

v0.1 uses a server-configured bearer secret. The application factory refuses secrets shorter than 24 characters. Credentials are compared with constant-time comparison and are never written into runtime requests or traces.

A production host should inject the secret through its secret manager/environment. Never commit credentials to GitHub.

## What remains before LIVE

1. Implement the authoritative `AmaRequestBuilder` against the current BLOOM read model.
2. Run hosted transport acceptance against a private HTTPS deployment.
3. Add request/trace correlation and bounded logging with secret redaction.
4. Decide the production authentication mechanism for the first Ama client.
5. Produce the external OpenAPI schema used by the Ama Custom GPT Action.
6. Keep write endpoints closed until the non-model permission service, CLIO production executor, stable-ID allocation, readback, and recovery path all pass hosted acceptance.

## Non-negotiable law

```text
external model output != authoritative evidence
external model output != permission
preview != realization
proposal != persistence
```

Ama may ask BLOOM questions and render validated answers. The external model cannot manufacture the facts or authority that make those answers true.
