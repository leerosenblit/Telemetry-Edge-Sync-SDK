# Future Work & Scope

This project deliberately implements the **defensible core** of the
Telemetry & Edge-Sync vision (see the pitch deck and `ARCHITECTURE.md`) and
defers the heavy production infrastructure. This document maps every feature
from the vision to its status, so the scope is explicit and the deferred items
are framed as intentional future work — not gaps.

The guiding principle: **prove the one guarantee end-to-end first** — *no data
is lost across network dropouts, and it arrives in correct time order without
duplicates* — then stop before the build becomes unfinishable solo.

## Implemented (the core)

| Vision feature | Where |
|---|---|
| Durable offline queue (SQLite) | `sdk/queue.py` |
| Smart batching (by count + time) | `sdk/client.py` |
| Auto-sync recovery, oldest-first, chronological order | `sdk/client.py` |
| Retry with exponential backoff | `sdk/client.py` |
| Crash / reboot recovery (durable at `track()` time) | `sdk/queue.py`, `tests/test_recovery.py` |
| Public API: `init` / `track` / `force_flush` | `sdk/client.py` |
| Idempotent ingestion (client-assigned id + upsert) | `server/main.py` |
| Store by **device** timestamp (late-arrival correctness) | `server/main.py` |
| API-key auth | `server/main.py` |
| Read / devices / health endpoints | `server/main.py` |
| Server-side alert rule engine (threshold rules) | `server/main.py` |
| Network-aware sync policy (batch/interval by link + battery) | `sdk/sync_policy.py` |
| SolarRace-OS integration bridge (`vehicle_state` → `track()`) | `sdk/integrations/solar_race.py` |
| Off-car solar-car simulator (for testing without hardware) | `sdk/integrations/solar_race.py`, `run.py` |
| Alert rules editor in the portal (add/enable/disable/delete, live) | `server/main.py`, `dashboard/index.html` |
| Management portal: live charts, device status, alerts, rules | `dashboard/index.html` |
| No-loss / idempotency / recovery / policy / bridge tests | `tests/` |

## Deferred (future work) — and why

| Vision feature | Why deferred | Path to add it |
|---|---|---|
| **Time-Series DB** (InfluxDB / TimescaleDB) | A plain indexed SQLite/Postgres table handles this project's scale. A TSDB matters only at sustained thousands-of-writes/sec. | Swap the storage layer behind the same REST contract; ingest/query endpoints stay identical. |
| **Message broker** (Kafka / RabbitMQ) | An in-process durable queue already absorbs spikes at single-server scale; a broker adds ops overhead with no benefit here. | Insert a broker between the ingest API and the writer when horizontal scale is needed. |
| **Protobuf payloads** | Gzipped JSON is sufficient and far easier to debug; the metadata/points split already minimizes payload size. | Add a content-type negotiation step in the sender + ingest endpoint. |
| **WebSocket live push** | The dashboard polls every 1.5 s — simpler and adequate for a demo. | Add a `/ws` endpoint and push on ingest; the chart already renders incrementally. |
| **CAN reading on the SDK side** | The car's Pi already decodes the CAN bus (SolarRace OS); the SDK takes the decoded `vehicle_state`, so it needs no `python-can`/DBC layer. | If a device ever streams raw CAN, add a decode adapter alongside `solar_race.py`. |
| **Continuous aggregates / downsampling** | Only needed when serving months of raw points; current scale renders raw data fine. | Pre-compute 1m/1h/1d rollups (native in a TSDB) and serve downsampled buckets by range. |
| **Advanced alerting** (compound conditions, hysteresis, notifications) | The portal already does single-threshold rules with live CRUD; multi-condition logic and push/email notifications are product polish. | Extend the `rules` model with condition groups + add a notifier on alert insert. |
| **Multi-car fleet + per-car API keys** | One car with a single static key proves the pipeline; managing several cars and key lifecycle is operational tooling. | Add a keys table + issue/revoke endpoints, and group the portal by `device_id`. |

## The REST boundary makes deferral safe

Because the SDK speaks plain HTTP and the server exposes a stable REST contract,
every deferred item above can be added **without changing the other side**: swap
SQLite for a TSDB, add a broker, switch JSON for Protobuf, or build native SDKs —
the contract is the generalization boundary, so today's components keep working.
