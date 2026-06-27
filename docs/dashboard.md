# Dashboard (pit-wall portal)

A single web page served by the server at **http://127.0.0.1:8000/** — no build step, no
CDN, works offline. The pit crew uses it with zero code. Five tabs:

![Portal overview](media/overview.png)
> *Screenshot placeholder — see [media/SHOTLIST.md](media/SHOTLIST.md).*

## Overview

Live charts of the car's metrics, polled every ~1.5 s.

- **Device / Metric** filters to focus the chart.
- **Live** toggle to pause/resume polling.
- **Export CSV** to download the currently-shown points.
- KPI cards: points stored, active devices, recent alerts, last sync.

*Example:* select `device = solar-car-01`, `metric = battery_temp_C` to watch pack
temperature; hover any point for its exact value and time.

## Devices

Per-device health: online / idle / offline (by last-sync age), point count, last-sync
time, and link metadata (network type, firmware, type).

*Example:* if the car enters a tunnel, its row flips to **idle** then **offline**; when it
re-emerges and the backlog drains, it returns to **online** and the point count jumps.

## Alerts

Threshold breaches from the rule engine, newest first, colored by severity
(critical / warning). Each row shows the device, metric, value vs. threshold, and time.

*Example:* `battery_temp_C = 50 (> 45)` appears as a **critical** alert.

## Rules

The alert rule engine, edited live (no restart):

- **Add** a rule: metric, operator (`>`/`<`), threshold, severity, message.
- **Enable / disable** a rule with its toggle.
- **Delete** a rule.

Changes take effect on the **next ingested batch**. (Backed by `GET/POST/PATCH/DELETE
/api/v1/rules`.)

![Rules editor](media/rules.png)
> *Screenshot placeholder.*

*Example:* add `mms_temperature_C > 80 → warning "Motor controller hot"`; the next time the
simulated car crosses 80 °C, a warning appears in **Alerts**.

## Setup

Issue and manage the **API keys** a car authenticates with, and copy a ready-to-paste
`auto_init()` snippet. See [user init & API keys](user-init.md).

*Example:* generate a key labelled `solar-car-01`, copy the snippet into the Pi's
environment, and the car connects on next boot.
