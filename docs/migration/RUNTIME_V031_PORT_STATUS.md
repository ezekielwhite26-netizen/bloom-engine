# Runtime v0.3.1 Clean-Port Status

Status: **TESTED IN ISOLATED INTEGRATION BRANCH**

Branch: `runtime-integration-v0.1`
Draft PR: #5
Source reviewed: legacy `bloomenginev1` branch `ama-runtime-v0.3`

## Ported and certified in clean `bloom-engine`

- Runtime Runner execution spine
- explicit sovereign query manifest
- Context Compiler over `CoreGateway`
- required UNKNOWN fail-closed
- incidental UNKNOWN degraded-scope preservation
- ADRASTEIA preflight
- ATHENA eligible-option / protected-fulcrum validation
- CALLIOPE claim validation
- capability-gated idempotent CLIO in-memory transaction layer
- Ama non-model permission/capability policy
- direct Runner -> CoreGateway -> HECATE integration

## CI evidence

GitHub Actions BLOOM CI run #17 completed successfully on 2026-08-19.

`pytest -q` => **54 passed**.

The integration suite proves at minimum:

1. a KNOWN HECATE `working.eligible` result can pass through the clean Runner and expose only the declared fact key;
2. required HECATE UNKNOWN blocks before ATHENA;
3. HECATE BLOCKED endpoint state blocks before ATHENA;
4. CALLIOPE cannot emit an unsupported reality claim;
5. CLIO rejects a realized write without an `AMA-CAP::` capability;
6. a structured in-memory CLIO manifest commits exactly once with verified readback;
7. preview-only candidate persistence performs no write;
8. ordinary requested live play can receive a one-run capability from the non-model Ama policy;
9. protected creative decisions return to the user;
10. destructive actions do not self-authorize.

## Deliberately not production-live

The port does **not** enable:

- real Airtable Event append;
- owner-specific mutable state execution;
- runtime `BLM-EVT-*` reservation/allocation;
- Context Packet invalidation after real commit;
- automatic ordinary live-play persistence;
- hosted HTTPS Ama API.

Those remain separate certification milestones. No story canon was changed by this port or its tests.

## Next integration milestone

Build the production CLIO transaction executor behind the same manifest/capability/ADRASTEIA gates, then prove one deliberately tiny authorized non-protected Event + owner delta can be committed, read back, recompiled, and resumed exactly once.
