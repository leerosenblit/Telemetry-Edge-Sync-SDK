# SDK reference

All public functions live in `sdk.client` (plus the solar-car bridge in
`sdk.integrations.solar_race`). Import the module-level functions for the common case, or
use the `Client` class directly for multiple instances.

---

## `init(server_url, api_key, device_id, **opts) -> Client`

Configure the module-level SDK once, at startup.

```python
from sdk.client import init
init("http://127.0.0.1:8000", api_key="<key>", device_id="solar-car-01", network="lte")
```

**Options (`**opts`, passed to `Client`):**

| Option | Default | Meaning |
|---|---|---|
| `db_path` | `"sdk_outbox.db"` | Path to the durable on-device queue. |
| `batch_size` | `50` | Points per request (overridden when `network` is set). |
| `flush_interval` | `2.0` | Seconds between send attempts (overridden when `network` is set). |
| `max_backoff` | `30.0` | Cap on exponential retry backoff (seconds). |
| `network` | `None` | Link type → enables the network-aware policy: `wifi/5g/lte/3g/edge/offline`. |
| `battery` | `None` | Battery % (0–100); low battery backs off further. |
| `metadata` | `{}` | Static metadata sent once per batch (e.g. `{"fw": "RaceOS-2.0", "type": "solar-car"}`). |

---

## `auto_init(config_path=None) -> Client`

Configure the SDK without hand-coding `init()`. Resolves settings in order:

1. an explicit JSON file at `config_path`,
2. a `telemetry.json` in the working directory (if present),
3. environment variables `TELEMETRY_SERVER_URL`, `TELEMETRY_API_KEY`,
   `TELEMETRY_DEVICE_ID`, optional `TELEMETRY_NETWORK`.

A config file may also set any `Client` option (`db_path`, `batch_size`, `metadata`, …).

```python
from sdk.client import auto_init
auto_init()                       # from env vars
auto_init("conf/telemetry.json")  # from a file
```

```json
// telemetry.json
{ "server_url": "http://127.0.0.1:8000", "api_key": "<key>",
  "device_id": "solar-car-01", "network": "lte",
  "metadata": { "fw": "RaceOS-2.0", "type": "solar-car" } }
```

Raises `RuntimeError` listing what's missing if `server_url`/`api_key`/`device_id` aren't found.

---

## `track(metric, value, ts=None) -> str`

Record one data point. **Non-blocking** — it persists to the local queue and returns
immediately, even with no network. `ts` is the device timestamp in epoch ms (defaults to
now). Returns the client-assigned point id.

```python
from sdk.client import track
point_id = track("battery_temp_C", 46.2)
track("bms_soc_percent", 74, ts=1718900000123)
```

---

## `force_flush(timeout=15.0) -> bool`

Block until the queue is fully drained or `timeout` elapses. Returns `True` if everything
was acknowledged. Call before shutdown.

```python
from sdk.client import force_flush
force_flush()           # e.g. on Ctrl+C / before reboot
```

---

## `class Client(server_url, api_key, device_id, **opts)`

The object behind the module API. Use it directly when you need more than one instance
(e.g. testing, or several logical devices in one process). Methods: `track()`,
`force_flush()`, `set_link()`, `close()`.

```python
from sdk.client import Client
sdk = Client("http://127.0.0.1:8000", "<key>", "solar-car-01", network="lte")
sdk.track("mms_rpm", 3200)
sdk.close()             # stop the worker, flush handles, close the db
```

### `Client.set_link(network=None, battery=None) -> None`

Update link conditions at runtime; the batcher adapts its batch size / flush interval
immediately. Use it when the car detects a change in cellular signal or battery state.

```python
sdk.set_link(network="edge", battery=15)   # weak link, low battery -> bigger, rarer batches
sdk.set_link(network="offline")            # buffer only, don't even try to send
```

---

## `track_vehicle_state(vehicle_state, client=None, ts=None) -> int`

(From `sdk.integrations.solar_race`.) Hand a SolarRace-OS `vehicle_state` dict to the SDK:
it walks each section (`battery` / `motor` / `temp_controller` / …) and calls
`track(name, value, ts)` for every **numeric** signal, skipping booleans/lists/identifiers.
Pass `ts` (the snapshot's device timestamp) so all signals in one frame share it. Returns
the number of points tracked.

```python
from sdk.client import auto_init
from sdk.integrations.solar_race import track_vehicle_state

auto_init()
# in the Pi's decode loop, where it used to push to the cloud:
n = track_vehicle_state(self.vehicle_state, ts=snapshot_ts_ms)
```

### `class SimulatedSolarCar(client, hz=5.0)`

Off-car simulator: generates a realistic `vehicle_state` and feeds it through
`track_vehicle_state()` at `hz` Hz. Used by `scripts/run.py` so the demo works with no hardware.

```python
from sdk.client import Client
from sdk.integrations.solar_race import SimulatedSolarCar
sdk = Client("http://127.0.0.1:8000", "<key>", "solar-car-01", network="lte")
SimulatedSolarCar(sdk, hz=5).start()
```
