"""End-to-end demo: run the simulated sensor through the SDK to a live server.

Usage (two terminals):
    uvicorn server.main:app --reload      # terminal 1
    python demo.py                        # terminal 2

Then open dashboard/index.html in a browser to watch the data arrive. To see
the resilience guarantee, stop the server mid-run and restart it: the SDK keeps
buffering and drains the backlog in order once the server is back.
"""

import time

from sdk.client import Client
from sdk.sensors import SimulatedSensor

SERVER = "http://localhost:8000"
API_KEY = "dev-key"
DEVICE = "car-01"


def main():
    sdk = Client(
        SERVER, API_KEY, DEVICE,
        metadata={"fw": "1.2.0", "type": "solar-car"},
        db_path="sdk_outbox.db",
    )
    sensor = SimulatedSensor(sdk, metrics=("speed", "temperature"), hz=5).start()
    print(f"Streaming telemetry as '{DEVICE}' to {SERVER} -- Ctrl+C to stop.")
    try:
        while True:
            time.sleep(2)
            print(f"  queued (unsent): {sdk.queue.unsent_count()}")
    except KeyboardInterrupt:
        print("\nStopping; flushing remaining points...")
    finally:
        sensor.stop()
        sdk.force_flush(timeout=10)
        sdk.close()
        print("Done.")


if __name__ == "__main__":
    main()
