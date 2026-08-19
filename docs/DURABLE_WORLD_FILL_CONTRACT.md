# Durable World-Fill Contract v0.1

BLOOM may resolve ordinary OPEN world-detail gaps into durable canon, but only through a bounded server-owned policy. Narrative output never becomes canon merely because it was rendered.

## Canon classes

### EPHEMERAL
Facts useful for the current run but not durable world structure.

Example: `Amara chose the window seat today.`

These may be used by the current runtime trace and must not be promoted automatically to durable canon.

### DURABLE_GENERATED_CANON
Low-risk ordinary structure that should remain stable once established.

Examples:
- a student's recurring class period;
- a club or institutional membership;
- a recurring meeting or shift;
- an ordinary acquaintance/familiarity edge supported by durable overlap.

Once committed, later runs read the persisted fact. They do not reroll it.

### PROTECTED_CANON
High-impact creative truth that requires explicit user approval before persistence.

Examples include romance, betrayal, major relationship redefinition, death, family secrets, major magical capability, important historical revelation, or irreversible character choice.

## Required flow

1. A runtime need exposes an OPEN gap.
2. The predicate is routed to its single sovereign owner.
3. The sovereign owner proposes a bounded value using existing constraints. CALLIOPE cannot originate the fact.
4. Existing canon is checked for contradiction. Any conflict fails closed.
5. `WorldFillPolicy` classifies the proposal.
6. `DURABLE_GENERATED_CANON` is auto-commit eligible only when a server-owned world-fill rule explicitly authorizes that predicate category and the proposal records supporting constraints, reason, and provenance.
7. `PROTECTED_CANON` requires explicit user approval.
8. ADRASTEIA still validates integrity.
9. CLIO still requires appropriate persistence authority, records provenance, commits idempotently, invalidates stale projections/context, and verifies readback.
10. Subsequent runs retrieve the committed fact rather than regenerating it.

`AUTO_COMMIT_ELIGIBLE` is not itself a write capability. The model/client cannot mint permission by choosing a canon class or rule id.

## Initial bounded auto-canon catalog

The v0.1 policy intentionally starts small:

- `schedule.*` -> CHRONOS
- `institution.*` -> EUNOMIA
- `organization.*` -> EUNOMIA
- `relationship.familiarity.*` -> HERA

The HERA rule covers ordinary familiarity/acquaintance only. It does not cover romance, intimacy, hostility escalation, betrayal, or major bond changes.

New categories should be added only as explicit server-owned rules with regression tests.

## Example: Amara third-period Chemistry

Suppose Academy encounter generation needs Amara's third-period class and the value is currently OPEN.

CHRONOS may propose:

- predicate: `schedule.student_period`
- fact: `AMARA::PERIOD-3 = CHEMISTRY`
- reason: resolve ordinary Academy encounter continuity
- constraints: Amara's year, already-fixed periods, valid course availability, teacher/section capacity, no existing Period-3 assignment
- provenance: the Academy social-web generation transaction

If no canon conflict exists and ADRASTEIA passes it, CLIO may persist the schedule fact. From that point onward, asking where Amara normally is during third period must return Chemistry unless an authorized later event changes the schedule.

CALLIOPE may then render `Amara came out of Chemistry`, but the prose is downstream of the fact and never the source of it.

## Social-web application

This contract should be in place before large-scale Academy / Henry peer / Hollow Circle graph generation. Those passes will create many mundane durable facts such as class overlaps, committee memberships, recurring meeting channels, and bounded acquaintance edges.

Relationship records should still distinguish:

- ESTABLISHED
- SUPPORTED_CANDIDATE
- OPEN

A supported candidate does not become an established relationship merely because it is plausible. The world-fill policy can promote only explicitly authorized low-risk relationship predicates after constraints and provenance are recorded.
