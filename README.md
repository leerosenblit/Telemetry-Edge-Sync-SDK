# Telemetry & Edge-Sync SDK

Resilient telemetry for the **Raspberry Pi on a solar race car**. The SDK buffers
the car's telemetry (BMS / motor controller / battery-temp controller) locally,
batches it, and syncs it to a REST server **reliably even across network dropouts**
— and the data lands in correct time order with no duplicates.

> **The one guarantee:** no data is lost when the car loses signal, and it arrives
> in correct chronological order.

The car's Pi software gets that for **three lines of code**. The pit crew gets a
live command-center portal for **zero lines**. Neither has to build the complex,
failure-prone sync infrastructure themselves.

---

## Run the demo (30 seconds)

```bash
pip install -r requirements.txt
python run.py
```

`run.py` starts the REST server **and** a simulated solar car (a SolarRace-OS
shaped telemetry stream — BMS / motor / battery-temp signals), then opens the
portal:

- **Portal (command center):** http://127.0.0.1:8000/
- **API reference (Swagger):** http://127.0.0.1:8000/docs

Try the resilience demo: while `run.py` runs, stop and restart the server — the
car keeps buffering and drains the backlog **in order** once it's back, with
nothing lost.

---

## Quickstart (the SDK's public API)

The car's Pi software embeds the SDK. The entire public API is three calls:

```python
from sdk.client import init, track, force_flush

# 1. Set up once, at startup: where to send, auth, and the car's identity.
init("https://telemetry.example.com", api_key="dev-key", device_id="solar-car-01")

# 2. Inject a reading whenever the Pi decodes one. Returns immediately — it never
#    blocks, even with no signal. The point is persisted to a local SQLite queue
#    first, then synced in the background.
track("battery_temp_C", 46.2)
track("bms_soc_percent", 74)

# 3. Before shutdown, push anything still queued.
force_flush()
```

That's it. Local buffering, batching, retry with backoff, and ordered resync
after a dropout all happen inside the SDK — you never see them. In practice you
won't call `track()` per signal by hand; the SolarRace integration below does it
for the whole `vehicle_state` in one call.

| Call | Role |
|---|---|
| `init(server_url, api_key, device_id, **opts)` | Configure the SDK (target, auth, identity). |
| `track(metric, value, ts=None)` | Record one data point. Non-blocking; durable. `ts` defaults to now (epoch ms). |
| `force_flush(timeout=15.0)` | Block until the queue drains (e.g. before exit). Returns `True` if fully synced. |

### Useful `init` options

```python
init(url, api_key, device_id,
     db_path="sdk_outbox.db",   # where the durable local queue lives
     batch_size=50,             # points per request (when no network policy)
     flush_interval=2.0,        # seconds between sync attempts
     network="lte",             # enable network-aware sync (wifi/5g/lte/3g/edge/offline)
     metadata={"fw": "RaceOS-2.0", "type": "solar-car"})  # static, sent once per batch
```

Setting `network=` turns on the **network-aware sync policy**: batch size and
flush frequency adapt to link quality and battery (fast links → small frequent
batches; slow links → larger, less frequent ones; low battery → backs off).

---

## Integrating with SolarRace OS (Raspberry Pi)

On the car, the Raspberry Pi already reads the CAN bus and decodes it into a
nested `vehicle_state` dict (BMS / motor controller / battery-temp controller).
Today that dict is pushed to the cloud **fire-and-forget** — so a dropout
silently loses data. The SDK is the resilient replacement: same data, buffered
durably, batched, and synced **in order with no loss**.

The SDK does **no CAN decoding** — the Pi already did that. You just hand it the
decoded dict. Two changes to the Pi's `main.py`:

```python
from sdk.client import init
from sdk.integrations.solar_race import track_vehicle_state

# 1. once, at startup:
init("https://telemetry.example.com", api_key="dev-key",
     device_id="solar-car-01", network="lte")

# 2. in _decode_message(), where you currently push to the cloud — add one line:
track_vehicle_state(self.vehicle_state)   # resilient: buffers + ordered resync
```

`track_vehicle_state()` walks the dict and calls `track(name, value)` for every
numeric signal (`bms_voltage_V`, `bms_soc_percent`, `battery_temp_C`, `mms_rpm`,
…), skipping flags/lists. See [sdk/integrations/solar_race.py](sdk/integrations/solar_race.py).
The only dependency the SDK adds on the Pi is `httpx`.

> Why this matters: the fire-and-forget cloud push drops whatever it can't send
> the instant the link blips. Routed through the SDK, those points sit safely in
> the on-disk queue and drain in chronological order the moment the link returns.

### Clean separation

The SDK pipeline never sees `vehicle_state` — that flattening lives in one small
integration file ([sdk/integrations/solar_race.py](sdk/integrations/solar_race.py)). The
pipeline only moves `metric / value / timestamp`, so every car subsystem (BMS, motor
controller, battery-temp controller) plugs in through that one file while the durability
layer stays untouched.

---

## For operators — the portal

The pit crew monitors the car from the portal (no code). One site, four tabs:

| Tab | What it shows |
|---|---|
| **Overview** | Live charts (filter by device/metric, hover, CSV export) + KPIs |
| **Devices** | Per-device health: online/idle/offline, last sync, battery, link type |
| **Alerts** | Threshold breaches from the rule engine, newest first |
| **Rules** | Add / enable / disable / delete alert rules — takes effect live, no restart |

---

## REST API

The SDK speaks plain REST, so the car syncs to our own server (not a third-party
backend like Firebase). Endpoints:

| Method & path | Role |
|---|---|
| `POST /api/v1/telemetry` | Ingest a batch (auth via `X-API-Key`). Idempotent upsert by point id. |
| `GET /api/v1/metrics?device=&metric=&from=&to=` | Read points, ordered by device time. |
| `GET /api/v1/devices` | Per-device health + latest metadata. |
| `GET /api/v1/alerts?device=&limit=` | Recent alerts. |
| `GET/POST/PATCH/DELETE /api/v1/rules` | Manage alert rules. |

---

## Project layout

```
sdk/              edge SDK: client (queue→batch→retry), durable queue, sync policy
  integrations/   solar-car bridge — solar_race.py (vehicle_state → track) + simulator
server/           FastAPI REST API + alert rule engine, serves the portal
dashboard/        the single-page command-center portal (no build step, no CDN)
tests/            no-loss, idempotency, crash-recovery, alerts, sync-policy, bridge
run.py            one-command launcher: server + simulated solar car + browser
```

## Testing

```bash
pytest
```

Covers the core guarantees: no-loss across a network drop, idempotency on lost
acknowledgements, data survival across a process restart, the alert rule engine,
and the network-aware sync policy.

---

## Design & scope

- [ARCHITECTURE.md](ARCHITECTURE.md) — full design and the key engineering decisions.
- [FUTURE_WORK.md](FUTURE_WORK.md) — what's deferred (TSDB, message broker, Protobuf,
  native mobile SDKs, WebSocket push) and why, with the path to add each.
