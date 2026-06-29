# Features

| Feature | What it gives you | Where |
|---|---|---|
| **Durable offline queue** | Every reading is written to on-device SQLite before any send — survives dropouts *and* reboots. | `sdk/queue.py` |
| **Smart batching** | Many samples per request (by count or time): fewer round-trips, less radio/battery cost. | `sdk/client.py` |
| **Auto-sync recovery** | Backlog drains **oldest-first** the instant the link returns. | `sdk/client.py` |
| **Retry with backoff** | Failed sends retry with exponential backoff; data stays safe on disk meanwhile. | `sdk/client.py` |
| **Crash / reboot recovery** | Because points persist at `track()` time, a fresh process drains whatever a crashed one left. | `sdk/queue.py` |
| **Idempotent ingestion** | Client-assigned point id + server upsert → at-least-once sending becomes effectively-once (no duplicates). | `server/main.py` |
| **Device-time ordering** | Stored by the car's timestamp, not arrival time, so late/buffered data lands in the right historical slot. | `server/main.py` |
| **Network-aware sync policy** | Batch size & frequency adapt to link type (wifi/5g/lte/3g/edge/offline) and battery. | `sdk/sync_policy.py` |
| **Server-side alert rules** | Threshold rules over the car's signals; breaches recorded idempotently. | `server/main.py` |
| **Live rules editor** | Add / enable / disable / delete rules from the portal — no restart. | `dashboard/index.html` |
| **API keys** | Generate / revoke keys in the dashboard; ingestion validates against them. | `server/main.py` |
| **Auto Init** | `auto_init()` configures the SDK from a config file or `TELEMETRY_*` env vars. | `sdk/client.py` |
| **Pit-wall portal** | Live charts, device health, alerts, rules, device setup — one page, no build step, no CDN. | `dashboard/index.html` |
| **Own backend** | Plain REST to your server: no vendor lock-in, no cloud credentials on the car. | `server/main.py` |
| **SolarRace-OS bridge** | One call hands the Pi's decoded `vehicle_state` to the SDK. | `sdk/integrations/solar_race.py` |
| **Off-car simulator** | Realistic solar-car telemetry with no hardware, for demos and tests. | `sdk/integrations/solar_race.py` |

See the [implementation notes](implementation.md) for how the correctness features work, and
[diagrams](diagrams.md) for the architecture.
