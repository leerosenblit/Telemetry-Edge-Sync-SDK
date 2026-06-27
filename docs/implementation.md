# Implementation

How the **one guarantee** — no loss, correct order, no duplicates — is delivered. See the
[diagrams](diagrams.md) for the architecture, sequence, and state machine.

## The edge pipeline (`sdk/`)

```
track() ──▶ SQLite outbox ──▶ batcher ──▶ sender ──▶ POST /api/v1/telemetry
            (durable)         (count/time) (retry)
```

### 1. Durable queue — `sdk/queue.py`

`track()` calls `Queue.enqueue()`, which writes the point to a SQLite `outbox` table
**immediately** (`INSERT OR IGNORE`, so a duplicate id is a no-op). This is the whole
durability story: if the network is down or the Pi reboots, the data is already on disk.

- `fetch_unsent(limit)` returns the oldest unsent points (`ORDER BY ts, seq`) — this is
  what makes recovery **chronological**.
- `mark_sent(ids)` flips `sent=1`, and is only ever called **after** the server
  acknowledges — so an un-acked batch is simply retried, never dropped.

### 2. Batcher + sender — `sdk/client.py`

A daemon thread (`_run`) wakes on a timer (`flush_interval`) or a nudge (queue full /
`force_flush` / link change). It fetches a batch, calls `_send_batch` → `_http_send`
(`POST` with `X-API-Key`), and on success marks the points sent. On failure it leaves them
unsent and backs off exponentially (1s → 2s → 4s …, capped at `max_backoff`). The point id
is minted in `_next_id()` as `device-seq-ts`.

### 3. Network-aware policy — `sdk/sync_policy.py`

`plan(network, battery)` maps link conditions to `(batch_size, flush_interval,
allow_send)`. Fast/cheap links → small frequent batches (low latency); slow links → larger,
rarer batches (amortize the costly round-trip); low battery → back off further;
`offline` → buffer only (don't wake the radio). `Client.set_link()` applies changes live.

## The server (`server/main.py`)

### Idempotent ingestion

`ingest()` validates the key (`_valid_key`), then `INSERT … ON CONFLICT(id) DO UPDATE` for
every point. Resending a batch (after a missed ack) overwrites the same rows instead of
inserting duplicates — turning unavoidable *at-least-once* sending into *effectively-once*
delivery. This is the single most important correctness property.

### Order by device time

Each point stores `device_ts` (the car's timestamp) and `received_ts` (arrival,
diagnostics only). Reads order by `device_ts`, so buffered/late data slots into history in
the right place — no time distortion in the charts.

### Alert rule engine

On ingest, each point is checked against the enabled `rules`. A breach inserts an `alerts`
row with id `pointid:ruleN` (`INSERT OR IGNORE`) — so re-ingesting the same batch never
duplicates an alert. Rules are CRUD-editable from the portal at runtime.

### API keys

`api_keys` stores issued keys; `_valid_key()` accepts a key only if it exists and isn't
revoked. The default key is seeded so existing setups keep working.

## Why this maps to the car

- **Tunnels / dropouts** → durable queue + retry + ordered drain (no loss, correct order).
- **Reboots** → persistence at `track()` time (a new process recovers the backlog).
- **Resends on flaky links** → idempotent upsert (no duplicate points or alerts).
- **Weak cellular / low battery** → network-aware policy (fewer, larger transmissions).
- **No cloud lock-in** → plain REST to your own server.
