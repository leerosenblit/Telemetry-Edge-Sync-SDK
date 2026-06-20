"""One-command launcher for the whole demo.

    python run.py

Starts the REST server *and* a small fleet of simulated edge devices streaming
telemetry into it over different (simulated) network links, then opens the
portal in a browser:

    http://127.0.0.1:8000/

Each device buffers durably, so you can kill and restart the server while this
runs and watch every device's backlog drain in order once it's back -- that's
the resilience demo. Some metrics are tuned to trip the server's alert rules,
so the Alerts panel fills in too. Ctrl+C to stop.
"""

import threading
import time
import webbrowser

import uvicorn

from sdk.client import Client
from sdk.sensors import SimulatedSensor

HOST, PORT = "127.0.0.1", 8000
URL = f"http://{HOST}:{PORT}/"

# A small fleet across the deck's target industries, each on a different link.
FLEET = [
    {"id": "car-01",     "type": "solar-car",  "metrics": ("speed", "temperature"), "network": "lte"},
    {"id": "ecg-07",     "type": "ecg-monitor", "metrics": ("heart_rate", "spo2"),  "network": "wifi"},
    {"id": "scooter-12", "type": "e-scooter",  "metrics": ("speed", "battery"),      "network": "edge"},
]


def start_fleet():
    for d in FLEET:
        sdk = Client(
            URL.rstrip("/"), "dev-key", d["id"],
            metadata={"fw": "1.2.0", "type": d["type"]},
            db_path=f"sdk_outbox_{d['id']}.db",
            network=d["network"],
        )
        SimulatedSensor(sdk, metrics=d["metrics"], hz=5).start()
        print(f"  device {d['id']:<11} [{d['network']}]  metrics={','.join(d['metrics'])}")


def open_browser_when_ready():
    time.sleep(1.5)
    try:
        webbrowser.open(URL)
    except Exception:
        pass
    print(f"\n  Portal:   {URL}\n  API docs: {URL}docs\n")


if __name__ == "__main__":
    print("Starting Edge-Sync fleet:")
    threading.Thread(target=start_fleet, daemon=True).start()
    threading.Thread(target=open_browser_when_ready, daemon=True).start()
    # uvicorn.run blocks in the main thread until Ctrl+C.
    uvicorn.run("server.main:app", host=HOST, port=PORT, log_level="warning")
