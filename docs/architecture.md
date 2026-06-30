# Telemetry & Edge-Sync SDK — Architecture

A resilient telemetry SDK for the Raspberry Pi (Python, Linux). It buffers a device's
sensor telemetry locally, batches it, and syncs it to a REST server reliably even across
network dropouts (tunnels, dead zones, weak coverage). The pipeline is sensor-agnostic;
device specifics live in small integrations — a hardware-free Raspberry Pi system-metrics
one, and the flagship **solar race car** (BMS / motor / battery-temp decoded from CAN),
which is used as the running example below. It speaks plain REST, so it syncs to our own
server rather than a locked-in third-party backend.

---

## The one thing this system guarantees

**No data is lost when the network drops, and the data arrives in correct time order.**

Everything below exists to deliver that single promise. When you feel lost, come back
to this sentence — every component and every design decision is in service of it.

---

## High-level architecture

```
  ┌─────────────────────────────┐   POST    ┌──────────────────────────┐   GET    ┌────────────────────┐
  │          Edge SDK           │  batch    │     REST API server      │  query   │  Pit-wall Dashboard │
  │  (Raspberry Pi on the car)  │ ───────►  │        (FastAPI)         │ ◄──────  │   (web + chart)    │
  └─────────────────────────────┘           └──────────────────────────┘          └────────────────────┘
        buffers + batches                       ingests + stores                      reads + visualizes
```

Data flows left to right. The interesting engineering lives on the left (surviving
dropouts) and in the middle (ingesting without duplicates and in order).

---

## Component 1 — Edge SDK

A small Python library that runs on the car's Raspberry Pi. Its job: accept telemetry
from the car's control software and get it to the server reliably, no matter the network.

**Public API (what the developer using your SDK calls):**

| Function | Role |
|---|---|
| `init(server_url, api_key, device_id)` | Set up the SDK: server target, auth, identity. |
| `track(metric, value, ts=None)` | Inject one data point. Returns immediately; never blocks the app. |
| `force_flush()` | Send everything queued right now (e.g. before shutdown). |

**Internal pipeline (what happens after `track()`):**

1. **Local queue (SQLite).** Every point is written to a local SQLite table first.
   This is the durability layer — if the network is down or the device reboots, the
   data is safe on disk.
2. **Batcher.** A background worker pulls unsent points from the queue and groups them
   into one payload (by count, e.g. 50 points, or by time, e.g. every 2 seconds).
3. **REST client / sender.** Sends the batch as one HTTP `POST` to the server.
4. **Retry + ordered resync.** Points are sent oldest-first and only marked as sent
   after the server acknowledges. So if the connection drops, the backlog drains in
   chronological order the moment it returns. Failed sends retry with backoff.

**Clean separation lives here.** The pipeline never knows what the data *means* —
`track()` takes a generic `metric / value / timestamp`. The solar-car-specific layer is
isolated in `sdk/integrations/solar_race.py`: the Pi already decodes the CAN bus into a
`vehicle_state` dict (BMS / motor / battery-temp), and `track_vehicle_state()` hands each
numeric signal to `track()`. So the car's subsystems plug in through one small file,
while the durability pipeline stays untouched. (For development off-car, a simulated
solar car generates realistic telemetry so you never depend on hardware.)

---

## Component 2 — REST API server

Your own server (FastAPI). It receives batches, stores them durably, and serves them
back for viewing.

**Endpoints:**

| Method + path | Role |
|---|---|
| `POST /api/v1/telemetry` | Ingest a batch. Auth via `X-API-Key`, validate, store. |
| `GET /api/v1/metrics?device=&metric=&from=&to=` | Read points for the dashboard. |
| `GET /api/v1/devices` | Last-seen / health per device. |

**Ingestion logic (the important part):**

1. **Authenticate** the request via the API key.
2. **Validate** the batch shape.
3. **Idempotent upsert** — each point carries a client-assigned `id`; the server upserts
   on it. Resending a batch (after a missed acknowledgement) overwrites the same rows
   instead of creating duplicates.
4. **Store by device timestamp** — the point's *device* time is the source of truth, not
   the server's arrival time. This is what makes late-arriving (buffered) data land in
   the correct historical position.

**Storage:** SQLite to start (zero setup), Postgres if you want to sound production-ready.

---

## Component 3 — Dashboard

A simple web page that reads from the server's `GET` endpoints and renders charts. It
polls every second or two for new data and offers CSV export. Deliberately minimal — it
exists to *show* that the pipeline works, not to be a product.

---

## Data model

**A telemetry point** (what `track()` produces):

```json
{
  "id": "solar-car-01-000042-1718900000123",
  "metric": "battery_temp_C",
  "value": 46.2,
  "ts": 1718900000123
}
```

`id` is client-assigned (device + sequence + timestamp) — this is what enables
idempotent ingestion. `ts` is the device timestamp in epoch milliseconds.

**A batch** (what the SDK `POST`s):

```json
{
  "device_id": "solar-car-01",
  "metadata": { "fw": "RaceOS-2.0", "type": "solar-car", "network": "lte" },
  "points": [ { "...point..." }, { "...point..." } ]
}
```

Static `metadata` is separated from dynamic `points` so it's sent once per batch, not
repeated per sample — smaller payloads, better compression.

**Server table:**

```sql
CREATE TABLE telemetry (
  id          TEXT PRIMARY KEY,   -- client-assigned -> idempotent upsert
  device_id   TEXT NOT NULL,
  metric      TEXT NOT NULL,
  value       REAL NOT NULL,
  device_ts   INTEGER NOT NULL,   -- order + late-arrival by this, NOT arrival time
  received_ts INTEGER NOT NULL    -- when the server got it (diagnostics only)
);
```

---

## Key design decisions (the interesting computer science)

1. **Durable local queue.** Buffering to SQLite (not memory) means data survives both
   network dropouts *and* device reboots. This is the core of "no data loss."

2. **Smart batching.** Many samples in one request instead of one request per sample —
   fewer network round-trips, less radio/battery cost, less server load.

3. **Idempotent ingestion = effectively-once delivery.** Unreliable networks force
   *at-least-once* sending (you resend when unsure a batch arrived). Client-assigned ids
   + server upsert turn that into *effectively-once* — no duplicates. This is the single
   most important correctness property in the system.

4. **Ordering by device timestamp.** Sending oldest-first preserves order on the wire;
   storing by device time (not arrival time) means buffered data slots into history
   correctly, with no time distortion in the graphs.

5. **REST as the boundary = our own backend, no lock-in.** Because the SDK speaks plain
   HTTP rather than a proprietary backend SDK, the car syncs to *our* server — no
   third-party dependency or cloud credentials on the car, and the backend can change
   without touching the car. The REST contract is the clean boundary between the car and
   whatever stores its telemetry.

---

## End-to-end flows

**Happy path (online):**
`track()` → queue in SQLite → batcher groups points → `POST` batch → server upserts and
stores → dashboard polls `GET` and renders.

**Disconnect + recovery (this is your demo):**
Network drops → `track()` keeps writing to the local queue (the backlog grows) → sends
fail and retry → network returns → the SDK drains the backlog oldest-first → server
upserts (no duplicates even if a batch is resent) → dashboard backfills the gap, in
correct time order, with nothing lost.

---

## Tech stack

- **Language:** Python (one language across device and server).
- **SDK:** `sqlite3` (standard library) for the queue, `httpx`/`requests` for sending.
- **Server:** FastAPI (validation + auto-generated API docs), SQLite or Postgres.
- **Dashboard:** a small web page with Chart.js (or equivalent).

---

## Scope and non-goals (future work)

Deliberately out of scope to keep the project finishable solo, and framed as future work
in the write-up:

- Message broker (Kafka/RabbitMQ) — an in-process queue replaces it.
- Time-series database — a plain table with a timestamp column is enough at this scale.
- Protobuf — gzipped JSON is sufficient.
- WebSocket live push — the dashboard polls instead.

Implemented stretch goals (on-theme for a cellular course): a network-aware sync policy
(adapt batch size and frequency to link type and battery) and a server-side alert rule
engine (threshold rules over the car's signals, editable from the pit dashboard).
See future-work.md for the full implemented-vs-deferred breakdown.