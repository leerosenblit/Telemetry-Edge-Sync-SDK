"""Stream a Raspberry Pi's own system metrics to the server — works on ANY Pi,
with no extra sensors. A minimal example of using the SDK for general Pi
telemetry (the same pipeline the solar-car integration uses).

Configure the connection via a `telemetry.json` or `TELEMETRY_*` env vars (see
docs/getting-started.md), run the server, then:

    python examples/pi_metrics.py
"""

import os
import sys
import time

# Make the repo root importable when run as `python examples/pi_metrics.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sdk.client import auto_init, force_flush
from sdk.integrations.raspberry_pi import SystemMonitor


def main():
    sdk = auto_init()                      # reads telemetry.json / TELEMETRY_* env
    SystemMonitor(sdk, hz=1).start()       # cpu_temp_C, cpu_load_1m, mem_used_percent, …
    print("Streaming Raspberry Pi system metrics — Ctrl+C to stop.")
    try:
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nFlushing and stopping...")
    finally:
        force_flush(timeout=10)
        print("Done.")


if __name__ == "__main__":
    main()
