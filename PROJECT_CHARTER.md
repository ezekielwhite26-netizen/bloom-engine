# BLOOM Engine — Clean Runtime Charter

This repository is the clean, headless home for the BLOOM Runtime and Ama integration.

## Scope

This repo owns executable runtime code, sovereign-core interfaces, resolver contracts, model/provider adapters, persistence adapters, tests, observability, and the API surface used by Ama or other clients.

It does **not** require the legacy web/game builder. `bloomenginev1` is a prototype/reference source only; useful backend code may be ported deliberately after review.

## Core runtime principles

- Sovereign cores own truth in their domains; orchestration does not.
- UNKNOWN fails closed for required predicates.
- Context Packets and traces are disposable operational artifacts, not canon.
- Model output is a proposal until validated by BLOOM.
- ATHENA may choose only among upstream-eligible options.
- CALLIOPE renders; it does not change reality.
- CLIO persists only realized, authorized durable changes.
- ADRASTEIA may block invalid commits and never silently repairs authority violations.
- The language model/provider must remain replaceable.

## Pantheon

THEMIS · CHRONOS · ATLAS · HEPHAESTUS · MNEMOSYNE · HERA · ANANKE · HECATE · APOLLO · HERMES · EUNOMIA · ATHENA · CALLIOPE · CLIO · ADRASTEIA

## Development rule

Track implementation maturity explicitly:

`DESIGNED -> BACKFILLED -> WIRED -> TESTED -> LIVE`

Do not call an architecture item LIVE merely because its schema or design exists.

## Concurrency

Concurrent development should use isolated branches. Avoid editing the same files on the same branch from multiple chats/jobs. Runtime Runner work already active elsewhere should be reviewed and selectively ported rather than independently reimplemented here.
