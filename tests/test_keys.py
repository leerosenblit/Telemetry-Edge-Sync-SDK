"""API-key issuance and validation: generated keys authenticate ingestion,
revoked/unknown keys are rejected, and the seeded default key still works."""

DEFAULT_KEY = "dev-key"


def _ingest(server, key):
    batch = {
        "device_id": "solar-car-01", "metadata": {},
        "points": [{"id": f"p-{key[:4]}", "metric": "bms_soc_percent", "value": 80.0, "ts": 1}],
    }
    return server.post("/api/v1/telemetry", json=batch, headers={"X-API-Key": key})


def test_seeded_default_key_works(server):
    assert _ingest(server, DEFAULT_KEY).status_code == 200


def test_unknown_key_rejected(server):
    assert _ingest(server, "not-a-real-key").status_code == 401


def test_generated_key_authenticates_then_revoked_is_rejected(server):
    # Generate a key via the Setup endpoint.
    created = server.post("/api/v1/keys", json={"label": "solar-car-01"})
    assert created.status_code == 201
    key = created.json()["key"]
    assert key and key != DEFAULT_KEY

    # It now authenticates ingestion.
    assert _ingest(server, key).status_code == 200

    # It appears in the list as active.
    listed = {k["key"]: k for k in server.get("/api/v1/keys").json()}
    assert listed[key]["revoked"] == 0

    # Revoke it -> ingestion with it is rejected; the row is kept as revoked.
    assert server.delete(f"/api/v1/keys/{key}").status_code == 200
    assert _ingest(server, key).status_code == 401
    assert {k["key"]: k for k in server.get("/api/v1/keys").json()}[key]["revoked"] == 1

    # The default key is unaffected.
    assert _ingest(server, DEFAULT_KEY).status_code == 200
