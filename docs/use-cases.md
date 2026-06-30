# Use cases

The SDK fits **any Raspberry Pi project** that produces numeric time-series over an
unreliable link. The pipeline only moves `metric / value / timestamp`, so the
device-specific part is one small integration — or just direct `track()` calls.

## Any Raspberry Pi project

- **Environmental / weather stations** — temperature, humidity, air quality in the field.
- **Robotics & drones** — battery, motor, and IMU telemetry where coverage comes and goes.
- **Home & industrial IoT** — energy use, machine health, cold-chain monitoring.
- **Wearables / remote monitors** — vitals or readings while out of coverage.
- **The Pi's own health** — CPU temperature, load, memory, uptime, via the built-in
  [`raspberry_pi`](sdk-reference.md) integration (no extra hardware).

Anything that keeps generating data while the link is down — and must not lose it —
benefits from on-device buffering plus ordered, idempotent resync.

## Flagship example: solar race car

The reference integration runs on a solar car's **Raspberry Pi**, which decodes the CAN
bus into live telemetry:

- **BMS** — pack voltage, current, state of charge, cell voltages, probe temperatures.
- **MMS (motor controller)** — RPM, power, controller temperature, fault/limit words.
- **Battery-temperature controller** — pack low/high/average temperatures.

During a race the car repeatedly loses its uplink (tunnels, grandstands, far side of the
circuit). The SDK guarantees that telemetry generated during those gaps is **buffered and
delivered in order** once the link returns — so strategy decisions and post-race analysis
rest on complete, correctly-ordered data. Over-temperature and undervoltage breaches
aren't missed because of a dropout: the alert engine fires as soon as the buffered breach
arrives.

## Why on-device buffering matters

A naive "push straight to the cloud" only works while the device has signal — when the
*device itself* drops (tunnel, weak coverage), there is nothing to push to and those
samples are lost. The SDK fixes that at the source: it buffers to the device's own disk
**first**, then syncs to your REST server in order once the link returns — so a device-side
outage loses nothing.
