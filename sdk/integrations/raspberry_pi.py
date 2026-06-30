"""Raspberry Pi system-metrics integration — a hardware-free starting point.

Reads the Pi's own health from the OS (CPU temperature, load, memory, uptime)
and feeds it to the SDK. It needs **no extra sensors**, so it runs on any
Raspberry Pi out of the box — useful on its own, and a demonstration that the
SDK serves *any* Pi project, not one specific device.

Reads are best-effort: anything the platform doesn't expose (e.g. off a Pi) is
simply skipped, so this never crashes on a dev laptop. Standard library only.

    from sdk.client import auto_init
    from sdk.integrations.raspberry_pi import SystemMonitor

    auto_init()
    SystemMonitor(client=None, hz=1).start()   # streams cpu_temp_C, load, mem…
"""

import os
import threading
import time

from ..client import track as _default_track


def _read_cpu_temp_c():
    """CPU temperature in °C from the thermal zone, or None if unavailable."""
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except Exception:
        return None


def _read_loadavg():
    """(1m, 5m, 15m) load averages, or None (os.getloadavg is Unix-only)."""
    try:
        return os.getloadavg()
    except (OSError, AttributeError):
        return None


def _read_mem_used_percent():
    """Used memory as a percentage from /proc/meminfo, or None."""
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, _, rest = line.partition(":")
                info[key] = int(rest.strip().split()[0])  # value is in kB
        total, avail = info.get("MemTotal"), info.get("MemAvailable")
        if total and avail is not None:
            return round((total - avail) / total * 100.0, 1)
    except Exception:
        pass
    return None


def _read_uptime_s():
    """Uptime in seconds from /proc/uptime, or None."""
    try:
        with open("/proc/uptime") as f:
            return round(float(f.read().split()[0]), 0)
    except Exception:
        return None


def read_system_metrics() -> dict:
    """A dict of the Pi system metrics available on this host (skips missing)."""
    metrics = {}
    temp = _read_cpu_temp_c()
    if temp is not None:
        metrics["cpu_temp_C"] = temp
    load = _read_loadavg()
    if load is not None:
        metrics["cpu_load_1m"] = round(load[0], 2)
        metrics["cpu_load_5m"] = round(load[1], 2)
    mem = _read_mem_used_percent()
    if mem is not None:
        metrics["mem_used_percent"] = mem
    uptime = _read_uptime_s()
    if uptime is not None:
        metrics["uptime_s"] = uptime
    return metrics


def track_system_metrics(client=None, ts: int | None = None) -> int:
    """Read the Pi's system metrics and hand each to the SDK via track()."""
    track = client.track if client is not None else _default_track
    n = 0
    for name, value in read_system_metrics().items():
        track(name, float(value), ts)
        n += 1
    return n


class SystemMonitor:
    """Polls the Pi's system metrics at `hz` and streams them through the SDK.

    Drop-in like the solar-car simulator, but for the Pi itself — no hardware.
    """

    def __init__(self, client, hz: float = 1.0):
        self.client = client
        self.period = 1.0 / hz
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> "SystemMonitor":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            # One device timestamp per sample, shared by all its metrics.
            track_system_metrics(self.client, ts=int(time.time() * 1000))
            time.sleep(self.period)
