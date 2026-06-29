"""The SolarRace-OS bridge: a decoded `vehicle_state` dict flattens into one
`track()` call per *meaningful* numeric signal — per-cell voltages collapse to a
min/max/spread summary, and identifiers/codes/flags are skipped."""

from sdk.integrations.solar_race import track_vehicle_state


class FakeClient:
    """Captures track() calls instead of sending them."""
    def __init__(self):
        self.tracked = []

    def track(self, metric, value, ts=None):
        self.tracked.append((metric, value))


def test_tracks_meaningful_signals_and_skips_noise():
    # A realistic snapshot straight out of the Pi's parsers.
    state = {
        "battery": {
            "bms_voltage_V": 108.4,
            "bms_current_A": 22.1,
            "bms_soc_percent": 76,
            "bms_string_count": 30,                 # spec -> skipped
            "bms_error_code": 0,                    # code -> skipped
            "bms_has_error": False,                 # bool -> skipped
            "bms_protections": ["Cell Overvoltage"],  # list -> skipped
        },
        "motor": {"mms_rpm": 3120, "mms_temperature_C": 71, "mms_limit_code": 4},
        "temp_controller": {"battery_temp_C": 46, "battery_temp_avg_C": 46,  # dup -> skipped
                            "temp_module": 1},
    }
    c = FakeClient()
    n = track_vehicle_state(state, client=c)

    names = {m for m, _ in c.tracked}
    assert n == len(c.tracked)
    # meaningful telemetry came through...
    assert {"bms_voltage_V", "bms_current_A", "bms_soc_percent",
            "mms_rpm", "mms_temperature_C", "battery_temp_C"} <= names
    # ...and the noise did not.
    for skipped in ("bms_string_count", "bms_error_code", "bms_has_error",
                    "bms_protections", "mms_limit_code", "battery_temp_avg_C",
                    "temp_module"):
        assert skipped not in names
    assert all(isinstance(v, float) for _, v in c.tracked)


def test_per_cell_voltages_collapse_to_summary():
    state = {"battery": {f"bms_cell_{i:02d}_V": 3.9 + i * 0.01 for i in range(1, 31)}}
    c = FakeClient()
    track_vehicle_state(state, client=c)
    names = {m for m, _ in c.tracked}
    # 30 individual cells are NOT tracked...
    assert not any(n.startswith("bms_cell_") and n.endswith("_V")
                   and n[9:11].isdigit() for n in names)
    # ...instead a compact summary is.
    assert {"bms_cell_min_V", "bms_cell_max_V", "bms_cell_spread_V"} <= names
    vals = dict(c.tracked)
    assert vals["bms_cell_min_V"] == 3.91          # cell 01
    assert vals["bms_cell_max_V"] == 4.2           # cell 30
    assert round(vals["bms_cell_spread_V"], 2) == 0.29


def test_handles_empty_and_partial_sections():
    c = FakeClient()
    assert track_vehicle_state({"battery": {}, "motor": {}, "temp_controller": {}}, client=c) == 0
    assert c.tracked == []
