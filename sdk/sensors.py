"""Sensor adapters -- the only device-specific code in the SDK.

The sync pipeline never knows what data *means*; it only moves metric/value/ts.
A sensor adapter bridges a real (or simulated) sensor to the generic SDK by
reading values and calling `track()`. Swap the adapter and the same SDK serves
any device. For development we ship a simulated adapter so nothing depends on
real hardware.
"""

import math
import threading
import time


class SimulatedSensor:
    """Generates plausible fake readings and feeds them into the SDK.

    Produces a smooth, slightly noisy waveform per metric so the dashboard chart
    looks like real telemetry. Runs in its own thread; call stop() to end it.
    """

    def __init__(self, client, metrics=("speed", "temperature"), hz: float = 5.0):
        self.client = client
        self.metrics = metrics
        self.period = 1.0 / hz
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> "SimulatedSensor":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)

    def _value_for(self, metric: str, t: float) -> float:
        # Distinct shape per metric so the chart shows differentiated lines.
        # Several waveforms are tuned to occasionally cross the server's alert
        # thresholds, so the Alerts panel has something to show in the demo.
        if metric == "speed":
            return round(45 + 20 * math.sin(t / 3) + 2 * math.sin(t * 5), 2)
        if metric == "temperature":          # ~36-48°C, crosses the 45° alert
            return round(42 + 6 * math.sin(t / 7) + 0.4 * math.sin(t * 6), 2)
        if metric == "heart_rate":           # ~65-125 bpm, crosses the 120 alert
            return round(95 + 30 * math.sin(t / 9) + 1.5 * math.sin(t * 4), 1)
        if metric == "spo2":                 # ~91-99%, dips below the 92 alert
            return round(95 + 4 * math.sin(t / 13), 1)
        if metric == "battery":              # slow drain 100->0, crosses 20 alert
            return round(100 - (t * 2) % 100, 1)
        return round(50 + 10 * math.sin(t), 2)

    def _run(self) -> None:
        t = 0.0
        while not self._stop.is_set():
            for metric in self.metrics:
                self.client.track(metric, self._value_for(metric, t))
            t += self.period
            time.sleep(self.period)
