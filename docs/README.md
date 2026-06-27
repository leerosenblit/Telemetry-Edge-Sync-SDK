# Telemetry & Edge-Sync SDK — Documentation

Resilient telemetry for the **Raspberry Pi on a solar race car**: buffer locally, sync
reliably across network dropouts, in correct time order, with no duplicates.

> **The one guarantee:** no data is lost when the car loses signal, and it arrives in
> correct chronological order, with no duplicates.

This is the full documentation set. Once the repository is on GitHub, this folder's URL is
the docs **permalink** (e.g. `https://github.com/<you>/<repo>/tree/main/docs`).

## Contents

1. [Overview](index.md) — what it is and the problem it solves.
2. [Use cases](use-cases.md) — where it's used.
3. [Features](features.md) — what it does.
4. [Getting started](getting-started.md) — install, get a key, send your first reading.
5. [SDK reference](sdk-reference.md) — every public function, with examples.
6. [User init & API keys](user-init.md) — dashboard key issuance + `auto_init()`.
7. [Dashboard](dashboard.md) — the pit-wall portal, tab by tab.
8. [Implementation](implementation.md) — how the guarantee is delivered.
9. [REST API](rest-api.md) — endpoint reference.
10. [Diagrams](diagrams.md) — architecture, ERD, sequence, state.

## Example docs we model after

Professional SDK docs like the **Google Maps Platform SDK** and **Firebase** docs: a short
overview, clear getting-started, a complete function reference with examples, and diagrams.
