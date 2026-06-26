"""SolarRace-OS integration for the Edge-Sync SDK.

The solar car's Raspberry Pi already reads the CAN bus and decodes it into a
nested `vehicle_state` dict (BMS / motor controller / battery-temp controller),
which today is pushed straight to the cloud fire-and-forget — so a network
dropout silently loses data.

This module is the resilient drop-in replacement. `track_vehicle_state()` takes
that exact dict and hands every numeric signal to the SDK via `track()`, which
buffers it durably, batches it, and syncs it to the REST server in order even
across dropouts. No CAN decoding happens here — the Pi already did it.

    # in your main loop, instead of (or alongside) the cloud push:
    from sdk.client import init
    from sdk.integrations.solar_race import track_vehicle_state

    init(SERVER_URL, API_KEY, device_id="solar-car-01", network="lte")
    ...
    track_vehicle_state(self.vehicle_state)     # <- one line, resilient

`SimulatedSolarCar` reproduces a realistic `vehicle_state` off-car (no hardware)
and feeds it through the very same bridge, so the demo exercises the real path.
"""

import math
import threading
import time

from ..client import track as _default_track

# Decoded fields that are identifiers/flags, not telemetry worth charting.
_SKIP_KEYS = {"temp_module", "bms_balance_mask"}


def track_vehicle_state(vehicle_state: dict, client=None, ts: int | None = None) -> int:
    """Hand every numeric signal in a `vehicle_state` dict to the SDK.

    Walks each section (battery / motor / temp_controller / …) and calls
    `track(name, value, ts)` for every int/float leaf. Booleans, strings, and
    lists (e.g. `bms_protections`) are skipped — `track()` carries numeric values.

    Pass `ts` (the car's snapshot timestamp, epoch ms) so every signal in one
    decoded frame shares the same device time — that's what keeps the history
    chronologically correct, exactly like the car's own `timestamp` field. When
    omitted, the SDK stamps each point at track() time.

    Pass `client` to target a specific SDK instance; otherwise the module-level
    SDK configured via `init()` is used. Returns how many points were tracked.
    """
    track = client.track if client is not None else _default_track
    n = 0
    for section, signals in vehicle_state.items():
        if not isinstance(signals, dict):
            continue
        for name, value in signals.items():
            if name in _SKIP_KEYS or isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                track(name, float(value), ts)
                n += 1
    return n


class SimulatedSolarCar:
    """Off-car simulator: produces a SolarRace-OS-shaped `vehicle_state` and
    feeds it through `track_vehicle_state()`, so `python run.py` on a laptop
    looks like the real car. Several signals are tuned to cross the server's
    alert thresholds so the Alerts panel has something to show.
    """

    def __init__(self, client, hz: float = 5.0):
        self.client = client
        self.period = 1.0 / hz
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> "SimulatedSolarCar":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)

    def _state(self, t: float) -> dict:
        battery_temp = round(42 + 6 * math.sin(t / 7), 1)        # ~36-48, crosses 45
        return {
            "battery": {
                "bms_voltage_V": round(108 + 6 * math.sin(t / 20), 2),
                "bms_current_A": round(18 + 12 * math.sin(t / 5), 2),
                "bms_soc_percent": round(max(2.0, 100 - (t * 1.2) % 100), 1),  # drains <20
                "bms_temp_1_C": round(44 + 8 * math.sin(t / 13), 1),           # crosses 50
                "bms_temp_2_C": round(40 + 5 * math.sin(t / 15), 1),
            },
            "motor": {
                "mms_rpm": int(2500 + 1800 * math.sin(t / 4)),
                "mms_power_W": int(1500 + 1200 * math.sin(t / 4)),
                "mms_temperature_C": round(72 + 15 * math.sin(t / 11), 1),     # crosses 80
            },
            "temp_controller": {
                "battery_temp_C": battery_temp,
                "battery_temp_high_C": round(battery_temp + 3, 1),
                "battery_temp_low_C": round(battery_temp - 3, 1),
            },
        }

    def _run(self) -> None:
        t = 0.0
        while not self._stop.is_set():
            # One device timestamp per snapshot, shared by all its signals.
            ts = int(time.time() * 1000)
            track_vehicle_state(self._state(t), self.client, ts=ts)
            t += self.period
            time.sleep(self.period)
