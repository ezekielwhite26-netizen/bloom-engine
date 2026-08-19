# BLOOM Cold Boot Fixture Contract v0.1

Status: TEST HARNESS ONLY. This does not implement the Runtime Runner, Context Compiler, CLIO/SCRIBE executor, or story-state mutation.

## Purpose

Cold boot must reconstruct bounded runtime state without turning attention, missing structured backfill, later-saga knowledge, ownership, or stale caches into new truth.

This harness maps existing BLOOM Integrity Tests BLM-TST-000020 through BLM-TST-000024 into provider-neutral executable fixtures.

## Invariants

- BLM-TST-000020 / CB-006: dormant or background threads are retained but cannot become opening-plot candidates merely because they exist or have high attention. A matured trigger is required.
- BLM-TST-000021 / CB-007: context compilation includes only explicitly relevant records. High-attention cosmology and dormant mysteries are not pulled in merely because they are salient. Missing requested records remain absent/unknown rather than fabricated.
- BLM-TST-000022 / CB-008: unfulfilled obligations and temporary possession survive reconstruction exactly. Current holder must not reset to canonical owner; unknown exact location remains unknown.
- BLM-TST-000023 / CB-009: ordinary scene boot may use only facts temporally valid for that scene. Later-saga facts require explicit author-side cross-book mode and must not leak backward into character/world state.
- BLM-TST-000024 / CB-010: an empty or missing structured subsystem is UNKNOWN/unbackfilled, never evidence that the represented thing does not exist.

## Authority boundary

These helpers model fail-closed boot behavior only. They do not decide sovereign predicates. Real runtime integration must obtain facts from the appropriate Pantheon owners and preserve owner attribution, evidence, UNKNOWN/BLOCKED/NOT_APPLICABLE semantics, and current Aster Hollow compendium/source authority.

## Runner handoff

When the Runtime Runner is ported into `bloom-engine`, it may reuse these fixtures as regression gates. The Runner should provide its own orchestration around sovereign outputs rather than importing story truth into this module.
