# Screenshots & video — capture guide

The README and docs reference images in this folder. Capture them from a running portal and
drop the PNGs here with the **exact filenames** below, and the placeholders resolve.

## Setup before capturing

```bash
python scripts/run.py
```
Open http://127.0.0.1:8000/ and let it run ~60 s so the charts fill and a few alerts fire.

## Screenshots to capture

| Filename | Tab / screen | What to show |
|---|---|---|
| `overview.png` | **Overview** | Live chart with several solar signals (e.g. `battery_temp_C`, `bms_soc_percent`, `mms_rpm`); KPI cards visible at top. |
| `devices.png` | **Devices** | `solar-car-01` row: online state, point count, last-sync, link metadata (lte). |
| `alerts.png` | **Alerts** | A few breaches, including a red **critical** one (e.g. `battery_temp_C = 50 (> 45)`). |
| `rules.png` | **Rules** | The rules list + the add-rule form at the bottom. |
| `setup.png` | **Setup** | A generated API key in the list + the `auto_init()` snippet below. |
| `swagger.png` | `/docs` | The Swagger UI endpoint list (telemetry, metrics, devices, alerts, rules, keys). |

Suggested size: ~1400 px wide, PNG. Crop to the content (no full desktop).

## Video storyboard (~75 seconds)

A single screen recording of the browser (plus a terminal for the dropout moment).

1. **0:00–0:10 — Intro.** Title slide or just the portal at http://127.0.0.1:8000/ on the
   **Overview** tab. Voiceover: "Resilient telemetry for a solar race car's Raspberry Pi."
2. **0:10–0:25 — Live data.** Show the chart updating in real time; hover a point for the
   tooltip; switch the **Metric** filter to `battery_temp_C`.
3. **0:25–0:45 — The guarantee (no loss).** In a terminal, **stop the server** (Ctrl+C) for
   ~8 s — point out the **Devices** tab going idle/offline. **Restart** the server; show the
   chart backfilling the gap in order and the device returning to online. Voiceover: "The
   car buffered everything during the outage and drained it in order — nothing lost."
4. **0:45–0:58 — Alerts & rules.** Open **Alerts** (show a critical breach). Open **Rules**,
   add `mms_temperature_C > 80 → warning`, and show it appear; mention "live, no restart".
5. **0:58–1:10 — Setup.** Open **Setup**, generate an API key, show the copyable
   `auto_init()` snippet. Voiceover: "Provision a car in two steps — generate a key, drop it
   in the Pi's config."
6. **1:10–1:15 — Close.** Back to Overview. "Three lines on the car, zero for the pit crew."

Once recorded, add the link in `README.md` under **Video** (and `docs/index.md`).
