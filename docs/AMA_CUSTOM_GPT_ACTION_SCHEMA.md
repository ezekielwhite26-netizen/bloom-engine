# Ama Custom GPT Action schema v0.1

This layer exports a deliberately narrower OpenAPI contract than the hosted BLOOM FastAPI app.

## Exposed actions

- `GET /v1/capabilities` — inspect the server-advertised boundary state.
- `POST /v1/runtime/preview` — submit bounded high-level Ama intent for server-side translation into READ-only sovereign queries and a PREVIEW runtime execution.

The exporter excludes `/health` and any route not explicitly whitelisted. No commit/write route exists in this contract.

## Trust boundary

The GPT/client supplies high-level intent only. It cannot supply:

- sovereign resolution status;
- authoritative evidence;
- raw query manifests;
- permission modes;
- capability/write tokens;
- persistence instructions.

The trusted server-side request builder maps supported intent to owner-routed `CoreRequest`s. Unsupported or ambiguous intent fails closed. Sovereign cores remain the only source of their domain truth.

## Authentication

The API uses server-configured bearer authentication. The Action server URL must be an absolute HTTPS URL and may not embed credentials. Secrets belong in the GPT Action authentication configuration / hosting secret store, never in the OpenAPI document or repository.

## Current production boundary

This schema is preparation only. It does not deploy or publish the API. Runtime commit remains false, persistence live remains false, and no live Airtable story Event/state write is enabled.

## Custom GPT handoff

OpenAI's current GPT Action setup expects an OpenAPI JSON or YAML schema describing the server, endpoints, parameters, authentication, and operation IDs. When the backend is privately hosted and transport acceptance passes, generate this bounded schema with the real HTTPS server URL and configure the GPT Action bearer credential separately. Do not paste a broad auto-generated FastAPI OpenAPI document into Ama; use the bounded exporter from this module.
