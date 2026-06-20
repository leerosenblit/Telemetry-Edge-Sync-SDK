# Telemetry & Edge-Sync SDK

Resilient telemetry for connectivity-constrained edge devices. The SDK buffers
sensor data locally, batches it, and syncs it to a REST server **reliably even
across network dropouts** — and the data lands in correct time order with no
duplicates.

> **The one guarantee:** no data is lost when the network drops, and it arrives
> in correct chronological order.

A device developer gets that for **three lines of code**. An operator gets a
live command-center portal for **zero lines**. Neither has to build the
complex, failure-prone sync infrastructure themselves.

---

## Run the demo (30 seconds)

```bash
pip install -r requirements.txt
python run.py
```

`run.py` starts the REST server **and** a small fleet of simulated devices, then
opens the portal:

- **Portal (command center):** http://127.0.0.1:8000/
- **API reference (Swagger):** http://127.0.0.1:8000/docs

Try the resilience demo: while `run.py` runs, stop and restart the server — the
devices keep buffering and drain the backlog **in order** once it's back, with
nothing lost.

---

## Quickstart for device developers

You embed the SDK in your device's app. The entire public API is three calls:

```python
from sdk.client import init, track, force_flush

# 1. Set up once, at startup: where to send, auth, and this device's identity.
init("https://telemetry.example.com", api_key="dev-key", device_id="car-01")

# 2. Inject a reading whenever your sensor produces one. Returns immediately —
#    it never blocks your app, even with no network. The point is persisted to a
#    local SQLite queue first, then synced in the background.
track("speed", 62.5)
track("temperature", 47.1)

# 3. Before shutdown, push anything still queued.
force_flush()
```

That's it. Local buffering, batching, retry with backoff, and ordered resync
after a dropout all happen inside the SDK — you never see them.

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
     metadata={"fw": "1.2.0", "type": "solar-car"})  # static, sent once per batch
```

Setting `network=` turns on the **network-aware sync policy**: batch size and
flush frequency adapt to link quality and battery (fast links → small frequent
batches; slow links → larger, less frequent ones; low battery → backs off).

---

## Connecting a real sensor

The SDK is device-agnostic — it only ever moves `metric / value / timestamp`.
Your hardware-specific code lives in **one place**: a *sensor adapter* that reads
your sensor and calls `track()`. See [sdk/sensors.py](sdk/sensors.py) for the
shipped `SimulatedSensor`; a real adapter follows the same shape:

```python
import threading, time
from sdk.client import init, track

class GpsSpeedSensor:
    """Reads a real GPS module and feeds speed into the SDK."""
    def __init__(self, hz=5.0):
        self.period = 1.0 / hz
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start(); return self

    def stop(self):
        self._stop.set(); self._thread.join(timeout=2.0)

    def _run(self):
        while not self._stop.is_set():
            speed = read_gps_speed()        # <-- your hardware call goes here
            track("speed", speed)           # <-- hand it to the SDK
            time.sleep(self.period)

# wiring it up:
init("https://telemetry.example.com", "dev-key", "car-01")
GpsSpeedSensor(hz=10).start()
```

Swap the adapter, keep the same SDK — that's how one library serves any device.

---

## For operators — the portal

Whoever monitors the fleet uses the portal (no code). One site, four tabs:

| Tab | What it shows |
|---|---|
| **Overview** | Live charts (filter by device/metric, hover, CSV export) + KPIs |
| **Devices** | Per-device health: online/idle/offline, last sync, battery, link type |
| **Alerts** | Threshold breaches from the rule engine, newest first |
| **Rules** | Add / enable / disable / delete alert rules — takes effect live, no restart |

---

## REST API

The SDK speaks plain REST, so the backend is swappable. Endpoints:

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
sdk/         edge SDK: client (queue→batch→retry), durable queue, sensors, sync policy
server/      FastAPI REST API + alert rule engine, serves the portal
dashboard/   the single-page command-center portal (no build step, no CDN)
tests/       no-loss, idempotency, crash-recovery, alerts, sync-policy
run.py       one-command launcher: server + simulated fleet + browser
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
