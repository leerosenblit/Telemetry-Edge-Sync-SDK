# Getting started

## 1. Install

```bash
pip install -r requirements.txt
```

The SDK itself needs only `httpx` (plus the standard-library `sqlite3`). The server and
portal use FastAPI + uvicorn (already in `requirements.txt`).

## 2. Run the server + portal

**Server only** (no simulator — for a real Pi, and what the cloud runs):

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

**Or the all-in-one local demo** (server **+** a simulated solar car, opens a browser — no
hardware needed):

```bash
python scripts/run.py
```

Either way:

- **Portal:** http://127.0.0.1:8000/
- **API reference (Swagger):** http://127.0.0.1:8000/docs

## 3. Get an API key (dashboard)

Open the portal, go to the **Setup** tab, enter a label (e.g. `solar-car-01`) and click
**Generate API key**. The page shows the key plus a ready-to-paste `auto_init()` snippet.
(Details: [user init & API keys](user-init.md).)

## 4. Send your first reading

**Option A — explicit `init()`:**

```python
from sdk.client import init, track, force_flush

init("http://127.0.0.1:8000", api_key="<your-key>", device_id="solar-car-01")
track("battery_temp_C", 46.2)      # returns immediately, persisted to disk
track("bms_soc_percent", 74)
force_flush()                       # push everything before exit
```

**Option B — `auto_init()` from environment** (what the dashboard snippet uses):

```bash
export TELEMETRY_SERVER_URL="http://127.0.0.1:8000"
export TELEMETRY_API_KEY="<your-key>"
export TELEMETRY_DEVICE_ID="solar-car-01"
```
```python
from sdk.client import auto_init, track
auto_init()                        # reads the env vars above (or a telemetry.json)
track("mms_rpm", 3200)
```

**Option C — the SolarRace-OS bridge** (real car): hand the whole decoded dict over in one
call — see [user init](user-init.md) and [SDK reference](sdk-reference.md):

```python
from sdk.integrations.solar_race import track_vehicle_state
track_vehicle_state(self.vehicle_state, ts=snapshot_ts_ms)
```

## 5. See it in the portal

Back in the portal's **Overview** tab, your metrics appear on the live chart within a
second or two. **Devices** shows the car's health; **Alerts** shows any threshold breaches.

## 6. Try the resilience demo

While `scripts/run.py` is running, **stop the server** (Ctrl+C) for a few seconds, then start it
again. The car keeps buffering during the outage and drains the backlog **in order** when
the server returns — nothing is lost. That is the core guarantee, live.

Next: the full [SDK reference](sdk-reference.md) or the [dashboard guide](dashboard.md).
