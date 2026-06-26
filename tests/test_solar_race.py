"""The SolarRace-OS bridge: a decoded `vehicle_state` dict flattens into one
`track()` call per numeric signal, skipping non-numeric fields (flags, lists)."""

from sdk.integrations.solar_race import track_vehicle_state


class FakeClient:
    """Captures track() calls instead of sending them."""
    def __init__(self):
        self.tracked = []

    def track(self, metric, value, ts=None):
        self.tracked.append((metric, value))


def test_flattens_only_numeric_signals():
    # A realistic snapshot straight out of the Pi's parsers.
    state = {
        "battery": {
            "bms_voltage_V": 108.4,
            "bms_current_A": 22.1,
            "bms_soc_percent": 76,
            "bms_has_error": False,                 # bool -> skipped
            "bms_protections": ["Cell Overvoltage"],  # list -> skipped
            "bms_balance_mask": 5,                  # id-ish -> skipped
        },
        "motor": {"mms_rpm": 3120, "mms_temperature_C": 71},
        "temp_controller": {"battery_temp_C": 46, "temp_module": 1},  # temp_module skipped
        "gps": {"lat": 50.99, "lon": 5.27},
    }
    c = FakeClient()
    n = track_vehicle_state(state, client=c)

    names = {m for m, _ in c.tracked}
    assert n == len(c.tracked)
    # numeric telemetry came through...
    assert {"bms_voltage_V", "bms_current_A", "bms_soc_percent",
            "mms_rpm", "mms_temperature_C", "battery_temp_C"} <= names
    # ...and the non-telemetry fields did not.
    assert "bms_has_error" not in names
    assert "bms_protections" not in names
    assert "bms_balance_mask" not in names
    assert "temp_module" not in names
    # every tracked value is a float
    assert all(isinstance(v, float) for _, v in c.tracked)


def test_handles_empty_and_partial_sections():
    c = FakeClient()
    assert track_vehicle_state({"battery": {}, "motor": {}, "temp_controller": {}}, client=c) == 0
    assert c.tracked == []
