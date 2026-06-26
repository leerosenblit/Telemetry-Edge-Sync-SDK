# Telemetry & Edge-Sync SDK

Resilient telemetry SDK for the Raspberry Pi on a solar race car: buffers the car's
telemetry (BMS / motor controller / battery-temp controller) locally, batches it, and
syncs to a REST server reliably across network dropouts. Python, solo course project.

See @ARCHITECTURE.md for the full design.

## Project layout
- server/    — FastAPI REST API (build this first)
- sdk/       — edge SDK: local queue, batcher, sender; solar-car integration in sdk/integrations/
- dashboard/ — simple web view (pit-wall command center)
- tests/     — including the kill-network no-loss test

## Commands
- Run the server: uvicorn server.main:app --reload
- Run tests:      pytest
- Install deps:   pip install -r requirements.txt

## Conventions
- Python, 4-space indentation.
- Keep the SDK pipeline generic (it only moves metric/value/timestamp): no
  solar-car-specific code in the queue/batcher/sender. The car-specific layer —
  turning the Pi's decoded `vehicle_state` into track() calls — lives only in
  sdk/integrations/solar_race.py.
- The SDK speaks plain REST only — sync to our own server, not a third-party backend.

## Key rules (do not break these)
- Store telemetry by the device timestamp, never the server arrival time.
- Ingestion must be idempotent: upsert points by their client-assigned id.
- Send queued points oldest-first; mark sent only after the server acknowledges.
- Get the full vertical slice working end-to-end before polishing any one component.