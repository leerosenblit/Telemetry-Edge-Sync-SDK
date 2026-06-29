# Use cases

## Primary: solar race car telemetry

The SDK runs on the car's **Raspberry Pi**, which decodes the CAN bus into live telemetry:

- **BMS** — pack voltage, current, state of charge, cell voltages, probe temperatures.
- **MMS (motor controller)** — RPM, power, controller temperature, fault/limit words.
- **Battery-temperature controller** — pack low/high/average temperatures.

During a race the car repeatedly loses its uplink (tunnels, grandstands, far side of the
circuit). The SDK guarantees that telemetry generated during those gaps is **buffered and
delivered in order** once the link returns — so the pit wall's strategy decisions and the
post-race analysis are based on complete, correctly-ordered data.

### Why it matters here

- **Strategy** — energy and thermal decisions depend on a continuous, trustworthy feed.
- **Safety** — over-temperature and undervoltage breaches must not be missed because of a
  dropout; the alert engine fires as soon as the buffered breach arrives.
- **Analysis** — a gap-free, chronologically-correct history after the race.

## Why on-device buffering matters

A naive "push straight to the cloud" only works while the car has signal — when the
*car itself* drops (tunnel, weak coverage), there is nothing to push to and those samples
are lost. The SDK fixes that at the source: it buffers to the car's own disk **first**, then
syncs to your REST server in order once the link returns — so a car-side outage loses
nothing.

## Beyond the car

The SDK pipeline only moves `metric / value / timestamp`, and the car-specific part is one
small integration file. The same durability core therefore suits any
connectivity-constrained edge device that produces numeric time-series — but this project
targets, builds, and documents the **Raspberry Pi solar car** specifically.
