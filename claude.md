# Telemetry & Edge-Sync SDK

Resilient telemetry SDK for edge devices: buffers sensor data locally, batches it,
and syncs to a REST server reliably across network dropouts. Python, solo course project.

See @ARCHITECTURE.md for the full design.

## Project layout
- server/    — FastAPI REST API (build this first)
- sdk/       — edge SDK: local queue, batcher, sender, sensor adapter
- dashboard/ — simple web view
- tests/     — including the kill-network no-loss test

## Commands
- Run the server: uvicorn server.main:app --reload
- Run tests:      pytest
- Install deps:   pip install -r requirements.txt

## Conventions
- Python, 4-space indentation.
- Keep the SDK core device-agnostic: no sensor-specific code in the pipeline.
  Sensor reading lives only in sdk/sensors.py adapters.
- The SDK speaks plain REST only — never couple it to a specific backend.

## Key rules (do not break these)
- Store telemetry by the device timestamp, never the server arrival time.
- Ingestion must be idempotent: upsert points by their client-assigned id.
- Send queued points oldest-first; mark sent only after the server acknowledges.
- Get the full vertical slice working end-to-end before polishing any one component.