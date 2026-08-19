# Aster Hollow Living Social Graph v0.1

Status: implementation scaffold / no canon writes

## Purpose

Build a persistent, canon-aware social graph that lets BLOOM derive who Florence and other characters can regularly encounter from actual world structure rather than narrative convenience.

The graph is connective infrastructure. It does not own relationship truth, schedules, locations, organizations, identity, knowledge, magic, or persistence. Those remain with the Pantheon sovereign cores.

## Canon sources checked for this pass

- Aster Hollow Definitive Master Compendium (2026-08-12)
- Aster Hollow Master Compendium Patch 03 (2026-08-11)
- Aster Hollow Master Compendium Patch 05 (2026-08-12)
- Aster Hollow Master Compendium Patch 07 (2026-08-12)
- Aster Hollow Definitive Runtime Master v1.1 (2026-08-17)
- BLOOM Organization Audit

Current controlling anchors include:

- Florence Maeve MacKellar is 16 and an Aster Hollow Academy junior.
- Henry Rowan MacKellar is 13 and must have his own school/friend/private life rather than existing only as Florence's sibling beat.
- Henry and Beatrice "Bea" Ashcombe, 13, are established friends.
- Anya Karpovich, 13, is a plausible natural younger-peer connection with Henry/Bea; this is not yet an established friendship and must not become a mechanical "junior Eight."
- The wider Henry peer cohort remains deliberately open.
- The Hollow Circle is a magical-community association, teaching network, mutual-aid structure, cultural center, and gathering framework, not a hidden government.
- The Academy is ordinary school life and is not a Circle school.
- Runtime presence discipline is plausibility first: determine who can actually be here before narrative rendering.

## Social layers

The first production population pass should be built as overlapping layers, not isolated protagonist satellites:

1. Florence / Academy junior layer
2. Florence teachers and recurring school staff
3. Student Council / Events-Planning layer
4. Henry / younger-teen peer layer
5. Hollow Circle living-community layer
6. Hearth household / cousin layer
7. Old-Family household overlaps
8. recurring town/business/community adults

Every created person should receive a small network of their own where supported by genealogy, household, age/cohort, geography, institutions, occupations, organizations, magical/community roles, shared history, or repeated contact.

## Relationship status

- `ESTABLISHED`: durable canon supports the relationship.
- `SUPPORTED_CANDIDATE`: existing canon strongly supports a possible connection, but the exact relationship is not yet canon.
- `OPEN`: plausible but unresolved.

The graph must never promote `SUPPORTED_CANDIDATE` or `OPEN` to `ESTABLISHED` merely because a scene would benefit from it.

## Encounter channels

A recurring encounter channel records why two people can plausibly cross paths. Examples:

- household
- family
- school cohort
- shared class
- student activity
- organization
- mentorship
- workplace
- neighborhood
- route
- community
- event

A channel is not presence proof. Runtime presence requires resolved sovereign prerequisites.

Typical owners:

- THEMIS: stable identity / canon source
- EUNOMIA: institution, organization, membership, role
- CHRONOS: schedule and temporal overlap
- ATLAS: location, route, reachability
- HERA: relationship/familiarity/kinship
- MNEMOSYNE: personal inclination, avoidance, preference when actually established
- HERMES: communication/knowledge reasons for contact
- HECATE: magical teaching/case suitability only where relevant
- HEPHAESTUS: object-created encounter channels where relevant
- ANANKE: due obligations/consequences
- ATHENA: discretionary selection only after deterministic eligibility
- CLIO: persistence of realized encounters and validated durable generated canon
- ADRASTEIA: independent integrity gate

CALLIOPE and APOLLO do not decide who is present. Rendering follows world resolution.

## Durable world-fill interaction

This branch is stacked on `durable-world-fill-v0.1`.

Ordinary structural gaps may be proposed as `DURABLE_GENERATED_CANON` only through a server-owned world-fill rule, sovereign-owner validation, conflict check, provenance, ADRASTEIA, explicit write authority, and capability-gated CLIO.

Example:

`Amara -> third period -> Chemistry`

If CHRONOS/EUNOMIA validly resolve that open mundane schedule gap and it passes the world-fill policy, it may become durable generated canon. Once persisted, later runtime requests must retrieve it rather than rerolling a different third-period class.

Relationship intimacy, romance, betrayal, major personality change, important secrets, deaths, major magical abilities, and other protected creative truths remain user-controlled canon.

## First population pass

Do not generate hundreds of students. Build a socially complete recurring network first.

Suggested initial targets:

- Academy junior recurring set: roughly 30-40 useful students, including focal teens, close/friendly classmates, Student Council/event peers, acquaintances, friction/rivalry, arts/sports overlaps, and connector students.
- Florence adult school set: every actual current teacher once timetable is resolved, plus guidance/student-support counselor, Student Council adviser, and a small set of recurring staff.
- Henry peer set: Bea as established; Anya as supported candidate; approximately 8-12 additional recurring peers generated only after structural roles/constraints are identified.
- Hollow Circle living set: a bounded cross-generational recurring cast rather than every magical resident in town.

The first canon-checked Academy population-gap map now lives in `docs/ASTER_HOLLOW_ACADEMY_POPULATION_PLAN_V01.md`. It seeds existing recurring names, identifies the Student Council / classroom / arts / athletics / friction / connector roles still missing, and deliberately leaves exact teachers and timetables unresolved until their sovereign constraints exist.

## Stable identity rule

Production graph rows must use THEMIS-resolved stable character/entity IDs. Do not invent BLM IDs in fixtures or docs. Names may be used in planning notes until exact stable identity is resolved.

## Safety boundary

This scaffold creates no new Aster Hollow person, relationship, schedule, class assignment, teacher assignment, Circle role, or story event as canon. It defines how those facts can be created and remembered safely in the next pass.
