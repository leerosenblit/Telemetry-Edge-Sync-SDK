"""Minimal integration example — how SolarRace-OS feeds the SDK.

This mirrors what you'd add to the Pi's main loop: initialise the SDK once, then
hand each decoded `vehicle_state` to `track_vehicle_state()`. Run the server
first (`uvicorn server.main:app` or `python scripts/run.py` in another terminal),
then `python examples/demo.py`.

It builds a couple of sample `vehicle_state` snapshots by hand so you can see the
exact integration without any CAN hardware.
"""

import os
import sys
import time

# Make the repo root importable when run as `python examples/demo.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sdk.client import init, force_flush
from sdk.integrations.solar_race import track_vehicle_state

SERVER = "http://localhost:8000"


def main():
    # 1. Once, at startup.
    init(SERVER, api_key="dev-key", device_id="solar-car-01",
         metadata={"fw": "RaceOS-2.0", "type": "solar-car"}, network="lte")

    # 2. Each time the Pi decodes a frame and updates vehicle_state, hand it over.
    #    (Here we fake two snapshots; on the car this is your live dict.)
    snapshots = [
        {
            "battery": {"bms_voltage_V": 108.4, "bms_current_A": 22.1, "bms_soc_percent": 76,
                        "bms_temp_1_C": 47.2},
            "motor": {"mms_rpm": 3120, "mms_power_W": 1840, "mms_temperature_C": 71},
            "temp_controller": {"battery_temp_C": 46, "battery_temp_high_C": 49},
        },
        {
            "battery": {"bms_voltage_V": 107.9, "bms_current_A": 25.3, "bms_soc_percent": 74,
                        "bms_temp_1_C": 51.0},                       # trips a critical alert
            "motor": {"mms_rpm": 3340, "mms_power_W": 1990, "mms_temperature_C": 83},  # warning
            "temp_controller": {"battery_temp_C": 44, "battery_temp_high_C": 47},
        },
    ]

    for state in snapshots:
        n = track_vehicle_state(state)
        print(f"tracked {n} signals")
        time.sleep(1)

    # 3. Before shutdown, make sure everything is synced.
    force_flush()
    print("done — open the portal to see the data and alerts")


if __name__ == "__main__":
    main()
