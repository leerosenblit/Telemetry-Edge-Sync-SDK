"""Server-side alert rule engine: threshold breaches raise alerts, alerts are
idempotent across resends, and per-device metadata (incl. link state) is stored.
"""

HEADERS = {"X-API-Key": "dev-key"}


def _post(server, batch):
    return server.post("/api/v1/telemetry", json=batch, headers=HEADERS)


def test_alert_fires_and_is_idempotent(server):
    batch = {
        "device_id": "car-01",
        "metadata": {"type": "solar-car", "network": "lte", "battery": 80},
        "points": [
            {"id": "car-01-1-1000", "metric": "temperature", "value": 50.0, "ts": 1000},
            {"id": "car-01-2-1001", "metric": "temperature", "value": 30.0, "ts": 1001},
        ],
    }
    r = _post(server, batch)
    assert r.status_code == 200
    assert r.json()["alerts"] == 1                   # only the 50°C point breaches

    alerts = server.get("/api/v1/alerts").json()
    assert len(alerts) == 1
    a = alerts[0]
    assert a["metric"] == "temperature" and a["severity"] == "critical"
    assert a["value"] == 50.0 and a["threshold"] == 45

    # Resending the same batch (at-least-once delivery) must not duplicate it.
    _post(server, batch)
    assert len(server.get("/api/v1/alerts").json()) == 1


def test_multiple_rules_and_device_metadata(server):
    batch = {
        "device_id": "scooter-12",
        "metadata": {"type": "e-scooter", "network": "edge", "battery": 12},
        "points": [
            {"id": "s-1", "metric": "battery", "value": 12.0, "ts": 2000},   # < 20 -> warning
            {"id": "s-2", "metric": "spo2", "value": 88.0, "ts": 2001},      # < 92 -> warning
            {"id": "s-3", "metric": "heart_rate", "value": 130.0, "ts": 2002},  # > 120 -> critical
            {"id": "s-4", "metric": "speed", "value": 18.0, "ts": 2003},     # no rule
        ],
    }
    assert _post(server, batch).json()["alerts"] == 3

    sevs = sorted(a["severity"] for a in server.get("/api/v1/alerts").json())
    assert sevs == ["critical", "warning", "warning"]

    # Latest device metadata (including link state) is exposed on /devices.
    dev = next(d for d in server.get("/api/v1/devices").json()
               if d["device_id"] == "scooter-12")
    assert dev["metadata"]["network"] == "edge"
    assert dev["metadata"]["battery"] == 12


def test_rule_crud_takes_effect_live(server):
    # A new metric with no rule yet -> no alert.
    pt = {"device_id": "car-01", "metadata": {},
          "points": [{"id": "rpm-1", "metric": "rpm", "value": 9000.0, "ts": 1}]}
    assert _post(server, pt).json()["alerts"] == 0

    # Add a rule at runtime.
    created = server.post("/api/v1/rules", json={
        "metric": "rpm", "op": ">", "threshold": 8000, "severity": "warning",
        "message": "Overspeed RPM"}).json()
    rule_id = created["id"]

    # A new point now breaches it (different point id so it's a fresh alert).
    pt2 = {"device_id": "car-01", "metadata": {},
           "points": [{"id": "rpm-2", "metric": "rpm", "value": 9500.0, "ts": 2}]}
    assert _post(server, pt2).json()["alerts"] == 1

    # Disable the rule -> stops firing.
    server.patch(f"/api/v1/rules/{rule_id}", params={"enabled": False})
    pt3 = {"device_id": "car-01", "metadata": {},
           "points": [{"id": "rpm-3", "metric": "rpm", "value": 9900.0, "ts": 3}]}
    assert _post(server, pt3).json()["alerts"] == 0

    # Delete it.
    assert server.delete(f"/api/v1/rules/{rule_id}").status_code == 200
    assert all(r["id"] != rule_id for r in server.get("/api/v1/rules").json())
