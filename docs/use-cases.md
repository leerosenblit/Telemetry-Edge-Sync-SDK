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

## How it replaces the previous setup

The car previously pushed telemetry **straight to a cloud database, fire-and-forget**.
That handles the *pit-side* reconnect but not the *car-side* outage: when the car itself
has no signal, there is nothing to push to, and the samples are lost. The SDK adds the
missing **on-device durability** and removes the third-party-backend dependency by syncing
to your own REST server.

## Beyond the car

The SDK pipeline only moves `metric / value / timestamp`, and the car-specific part is one
small integration file. The same durability core therefore suits any
connectivity-constrained edge device that produces numeric time-series — but this project
targets, builds, and documents the **Raspberry Pi solar car** specifically.
