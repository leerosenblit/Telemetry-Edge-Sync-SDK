"""One-command launcher for the demo.

    python scripts/run.py

Starts the REST server and a *simulated* solar car (a SolarRace-OS-shaped
telemetry stream — BMS / motor / battery-temp signals) flowing through the SDK,
then opens the portal:

    http://127.0.0.1:8000/

On the real car the Raspberry Pi feeds live decoded telemetry instead (see the
docs); here we simulate it so the whole pipeline and dashboard run with no
hardware. Stop/restart the server mid-run to watch the backlog buffer and drain
in order — the resilience demo. Ctrl+C ends.
"""

import os
import sys
import threading
import time
import webbrowser

# Make the repo root importable when run as `python scripts/run.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import uvicorn

from sdk.client import Client
from sdk.integrations.solar_race import SimulatedSolarCar

HOST, PORT = "127.0.0.1", 8000
URL = f"http://{HOST}:{PORT}/"


def start_car():
    sdk = Client(
        URL.rstrip("/"), "dev-key", "solar-car-01",
        metadata={"fw": "RaceOS-2.0", "type": "solar-car"},
        db_path="sdk_outbox_solar-car-01.db",
        network="lte",
    )
    SimulatedSolarCar(sdk, hz=5).start()
    print("  solar-car-01 [lte]  streaming BMS / motor / battery-temp telemetry")


def open_browser_when_ready():
    time.sleep(1.5)
    try:
        webbrowser.open(URL)
    except Exception:
        pass
    print(f"\n  Portal:   {URL}\n  API docs: {URL}docs\n")


if __name__ == "__main__":
    print("Starting Edge-Sync (simulated solar car):")
    threading.Thread(target=start_car, daemon=True).start()
    threading.Thread(target=open_browser_when_ready, daemon=True).start()
    uvicorn.run("server.main:app", host=HOST, port=PORT, log_level="warning")
