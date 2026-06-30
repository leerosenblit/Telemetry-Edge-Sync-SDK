# Overview

## Telemetry & Edge-Sync SDK

A Python SDK for the **Raspberry Pi** (and similar Linux edge devices). It buffers your
sensor telemetry on the device, batches it, and gets it to a REST server **reliably —
even when the device loses signal**. The pipeline is sensor-agnostic; a hardware-free
**Raspberry Pi system-metrics** integration runs on any Pi, and the **flagship example**
is a solar race car (BMS / motor / battery-temp decoded from CAN).

![Portal overview](media/overview.png)
> *Screenshot — see [media/SHOTLIST.md](media/SHOTLIST.md).*

## The problem

Many Pi projects stream data over a flaky link — a field weather station, a robot, an
environmental or industrial monitor, or a solar race car on track. Telemetry never stops
being generated, but the uplink drops (tunnels, dead zones, weak coverage). A naive
"push straight to the cloud" silently **loses every sample produced during an outage**,
and late data can land out of order, distorting the charts.

## The solution

The SDK sits on the device between your data and the network:

1. **Buffer first.** Every reading is written to an on-device SQLite queue *before* any
   network attempt — so it survives dropouts and even reboots.
2. **Batch.** A background worker groups readings into one request (by count or time).
3. **Sync + recover.** Batches are sent oldest-first and marked sent only after the
   server acknowledges. When the link drops, the backlog grows safely on disk and drains
   **in chronological order** the moment the link returns.
4. **Ingest correctly.** The server upserts each point on a client-assigned id
   (idempotent — retries never duplicate) and stores it by **device time**, not arrival
   time, so buffered data slots into history in the right place.

> **The one guarantee:** no data is lost when the device loses signal, and it arrives in
> correct chronological order, with no duplicates.

## Who uses what

- **Your device's software** embeds the SDK and calls three functions (`init` / `track` /
  `force_flush`), or `auto_init()` from config. On any Pi, `SystemMonitor` streams the
  Pi's own metrics; for the solar car, one call — `track_vehicle_state(vehicle_state)` —
  hands the whole decoded dict to the SDK.
- **Whoever monitors it** opens the web **portal** (no code): live charts, device health,
  alerts, and a rules editor.

Continue to [Use cases](use-cases.md) or jump to [Getting started](getting-started.md).
