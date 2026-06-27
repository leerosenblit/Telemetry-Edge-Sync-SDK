# Overview

## Telemetry & Edge-Sync SDK

A Python SDK for the **Raspberry Pi on a solar race car**. It takes the telemetry the Pi
already decodes from the car's CAN bus — battery management system (BMS), motor controller
(MMS), and battery-temperature controller — and gets it to a REST server **reliably, even
when the car loses signal**.

![Portal overview](media/overview.png)
> *Screenshot placeholder — see [media/SHOTLIST.md](media/SHOTLIST.md).*

## The problem

A solar car races for hours across a long circuit. The cellular uplink drops in tunnels,
behind grandstands, and on the far side of the track. Telemetry never stops being
generated — dozens of samples per second from the BMS and motor controller. A naive
"push straight to the cloud" silently **loses every sample produced during an outage**,
and late data can land out of order, distorting the pit wall's charts.

## The solution

The SDK sits on the car between the decoded telemetry and the network:

1. **Buffer first.** Every reading is written to an on-device SQLite queue *before* any
   network attempt — so it survives dropouts and even reboots.
2. **Batch.** A background worker groups readings into one request (by count or time).
3. **Sync + recover.** Batches are sent oldest-first and marked sent only after the
   server acknowledges. When the link drops, the backlog grows safely on disk and drains
   **in chronological order** the moment the link returns.
4. **Ingest correctly.** The server upserts each point on a client-assigned id
   (idempotent — retries never duplicate) and stores it by **device time**, not arrival
   time, so buffered data slots into history in the right place.

> **The one guarantee:** no data is lost when the car loses signal, and it arrives in
> correct chronological order, with no duplicates.

## Who uses what

- **The car's software** embeds the SDK and calls three functions (`init` / `track` /
  `force_flush`), or `auto_init()` from config. In practice one call —
  `track_vehicle_state(vehicle_state)` — hands the whole decoded dict to the SDK.
- **The pit crew** opens the web **portal** (no code): live charts, device health,
  alerts, and a rules editor.

Continue to [Use cases](use-cases.md) or jump to [Getting started](getting-started.md).
