"""The Raspberry Pi system-metrics integration: reads available OS metrics and
hands each to the SDK, skipping anything the platform doesn't expose."""

from sdk.integrations import raspberry_pi as rpi


class FakeClient:
    def __init__(self):
        self.tracked = []

    def track(self, metric, value, ts=None):
        self.tracked.append((metric, value))


def test_tracks_available_system_metrics(monkeypatch):
    monkeypatch.setattr(rpi, "_read_cpu_temp_c", lambda: 54.2)
    monkeypatch.setattr(rpi, "_read_loadavg", lambda: (0.5, 0.4, 0.3))
    monkeypatch.setattr(rpi, "_read_mem_used_percent", lambda: 61.0)
    monkeypatch.setattr(rpi, "_read_uptime_s", lambda: 3600.0)

    c = FakeClient()
    n = rpi.track_system_metrics(client=c)

    names = {m for m, _ in c.tracked}
    assert n == len(c.tracked)
    assert {"cpu_temp_C", "cpu_load_1m", "cpu_load_5m",
            "mem_used_percent", "uptime_s"} <= names
    assert all(isinstance(v, float) for _, v in c.tracked)


def test_skips_metrics_unavailable_off_pi(monkeypatch):
    # Off a Pi (or on a dev laptop) the readers return None — nothing is tracked,
    # and it must not crash.
    for fn in ("_read_cpu_temp_c", "_read_loadavg",
               "_read_mem_used_percent", "_read_uptime_s"):
        monkeypatch.setattr(rpi, fn, lambda: None)

    assert rpi.read_system_metrics() == {}
    c = FakeClient()
    assert rpi.track_system_metrics(client=c) == 0
