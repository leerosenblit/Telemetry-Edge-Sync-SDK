"""Server-side alert rule engine: threshold breaches raise alerts, alerts are
idempotent across resends, and per-device metadata (incl. link state) is stored.
"""

HEADERS = {"X-API-Key": "dev-key"}


def _post(server, batch):
    return server.post("/api/v1/telemetry", json=batch, headers=HEADERS)


def test_alert_fires_and_is_idempotent(server):
    batch = {
        "device_id": "solar-car-01",
        "metadata": {"type": "solar-car", "network": "lte"},
        "points": [
            {"id": "c-1-1000", "metric": "battery_temp_C", "value": 50.0, "ts": 1000},
            {"id": "c-2-1001", "metric": "battery_temp_C", "value": 30.0, "ts": 1001},
        ],
    }
    r = _post(server, batch)
    assert r.status_code == 200
    assert r.json()["alerts"] == 1                   # only the 50°C point breaches

    alerts = server.get("/api/v1/alerts").json()
    assert len(alerts) == 1
    a = alerts[0]
    assert a["metric"] == "battery_temp_C" and a["severity"] == "critical"
    assert a["value"] == 50.0 and a["threshold"] == 45

    # Resending the same batch (at-least-once delivery) must not duplicate it.
    _post(server, batch)
    assert len(server.get("/api/v1/alerts").json()) == 1


def test_multiple_rules_and_device_metadata(server):
    batch = {
        "device_id": "solar-car-01",
        "metadata": {"type": "solar-car", "network": "lte"},
        "points": [
            {"id": "s-1", "metric": "bms_soc_percent", "value": 12.0, "ts": 2000},     # < 20 -> warning
            {"id": "s-2", "metric": "bms_temp_1_C", "value": 55.0, "ts": 2001},        # > 50 -> critical
            {"id": "s-3", "metric": "mms_temperature_C", "value": 95.0, "ts": 2002},   # > 80 -> warning
            {"id": "s-4", "metric": "bms_voltage_V", "value": 100.0, "ts": 2003},      # no rule
        ],
    }
    assert _post(server, batch).json()["alerts"] == 3

    sevs = sorted(a["severity"] for a in server.get("/api/v1/alerts").json())
    assert sevs == ["critical", "warning", "warning"]

    # Latest device metadata (including link state) is exposed on /devices.
    dev = next(d for d in server.get("/api/v1/devices").json()
               if d["device_id"] == "solar-car-01")
    assert dev["metadata"]["network"] == "lte"
    assert dev["metadata"]["type"] == "solar-car"


def test_rule_crud_takes_effect_live(server):
    # A new metric with no rule yet -> no alert.
    pt = {"device_id": "solar-car-01", "metadata": {},
          "points": [{"id": "rpm-1", "metric": "mms_rpm", "value": 9000.0, "ts": 1}]}
    assert _post(server, pt).json()["alerts"] == 0

    # Add a rule at runtime.
    created = server.post("/api/v1/rules", json={
        "metric": "mms_rpm", "op": ">", "threshold": 8000, "severity": "warning",
        "message": "Overspeed RPM"}).json()
    rule_id = created["id"]

    # A new point now breaches it (different point id so it's a fresh alert).
    pt2 = {"device_id": "solar-car-01", "metadata": {},
           "points": [{"id": "rpm-2", "metric": "mms_rpm", "value": 9500.0, "ts": 2}]}
    assert _post(server, pt2).json()["alerts"] == 1

    # Disable the rule -> stops firing.
    server.patch(f"/api/v1/rules/{rule_id}", params={"enabled": False})
    pt3 = {"device_id": "solar-car-01", "metadata": {},
           "points": [{"id": "rpm-3", "metric": "mms_rpm", "value": 9900.0, "ts": 3}]}
    assert _post(server, pt3).json()["alerts"] == 0

    # Delete it.
    assert server.delete(f"/api/v1/rules/{rule_id}").status_code == 200
    assert all(r["id"] != rule_id for r in server.get("/api/v1/rules").json())
