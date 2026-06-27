# User init & API keys

How a car gets authenticated and connected to the server — from the dashboard, then via
the SDK.

## 1. Get an API key from the dashboard

Open the portal (http://127.0.0.1:8000/) and go to the **Setup** tab.

![Setup / API keys](media/setup.png)
> *Screenshot placeholder — see [media/SHOTLIST.md](media/SHOTLIST.md).*

- Enter a **label** for the device (e.g. `solar-car-01`) and click **Generate API key**.
- The new key appears in the list with **Copy** and **Revoke** buttons.
- The page shows a ready-to-paste setup snippet (env vars + `auto_init()`), pre-filled with
  this server's URL and the selected key.

Behind the scenes this calls `POST /api/v1/keys`; the key is stored server-side and every
ingest request is validated against it. **Revoke** marks the key revoked (soft delete) —
ingestion with a revoked key is rejected with `401`.

## 2. Initialize the SDK on the car

### Explicit init

```python
from sdk.client import init
init("http://127.0.0.1:8000", api_key="<key from dashboard>", device_id="solar-car-01")
```

### Auto Init (recommended for a provisioned device)

`auto_init()` reads configuration so you don't hard-code it in the car's source. It looks,
in order, at: an explicit config path → `telemetry.json` in the working directory →
`TELEMETRY_*` environment variables.

**Via environment variables** (the dashboard snippet):

```bash
export TELEMETRY_SERVER_URL="http://127.0.0.1:8000"
export TELEMETRY_API_KEY="<key from dashboard>"
export TELEMETRY_DEVICE_ID="solar-car-01"
export TELEMETRY_NETWORK="lte"        # optional
```
```python
from sdk.client import auto_init
auto_init()
```

**Via a config file** (`telemetry.json` next to the car's program):

```json
{
  "server_url": "http://127.0.0.1:8000",
  "api_key": "<key from dashboard>",
  "device_id": "solar-car-01",
  "network": "lte",
  "metadata": { "fw": "RaceOS-2.0", "type": "solar-car" }
}
```
```python
from sdk.client import auto_init
auto_init()                       # finds telemetry.json automatically
# or: auto_init("conf/telemetry.json")
```

This is ideal for a Raspberry Pi that's **provisioned once**: drop the key into the Pi's
environment or a config file, and the car's program calls `auto_init()` at boot and starts
syncing — no code change per device.

## 3. Provisioning flow (summary)

```
Pit engineer            Dashboard (Setup tab)        Car's Raspberry Pi
     |  generate key  ------>  POST /api/v1/keys
     |  copy key + snippet <---  key + auto_init() snippet
     |  put key in Pi env / telemetry.json  ------------------->  auto_init() at boot
                                                                  track_vehicle_state(...)
```

> **Scope note:** key-management endpoints are unauthenticated in this build (local-tool
> scope), the same as the rules editor. Putting the key endpoints behind admin auth is
> listed in [../FUTURE_WORK.md](../FUTURE_WORK.md).
