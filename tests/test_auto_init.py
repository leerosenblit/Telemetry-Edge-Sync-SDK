"""auto_init() configures the SDK from environment variables or a config file,
so a provisioned device starts syncing without hand-coding init()."""

import json

import pytest

from sdk.client import auto_init


def test_auto_init_from_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)        # keep the default outbox db in tmp
    monkeypatch.setenv("TELEMETRY_SERVER_URL", "http://unused:9999")
    monkeypatch.setenv("TELEMETRY_API_KEY", "k-env")
    monkeypatch.setenv("TELEMETRY_DEVICE_ID", "solar-car-01")
    monkeypatch.setenv("TELEMETRY_NETWORK", "lte")

    c = auto_init()
    try:
        assert c.server_url == "http://unused:9999"
        assert c.api_key == "k-env"
        assert c.device_id == "solar-car-01"
        assert c.network == "lte"
    finally:
        c.close()


def test_auto_init_from_config_file(tmp_path):
    cfg = tmp_path / "telemetry.json"
    cfg.write_text(json.dumps({
        "server_url": "http://unused:9999",
        "api_key": "k-file",
        "device_id": "solar-car-02",
        "network": "edge",
        "db_path": str(tmp_path / "out.db"),
        "metadata": {"fw": "RaceOS-2.0", "type": "solar-car"},
    }))

    c = auto_init(str(cfg))
    try:
        assert c.device_id == "solar-car-02"
        assert c.network == "edge"
        assert c.queue.db_path == str(tmp_path / "out.db")   # extra opt passed through
        assert c.metadata == {"fw": "RaceOS-2.0", "type": "solar-car"}
    finally:
        c.close()


def test_auto_init_missing_config_raises(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)        # no telemetry.json here
    for var in ("TELEMETRY_SERVER_URL", "TELEMETRY_API_KEY",
                "TELEMETRY_DEVICE_ID", "TELEMETRY_NETWORK"):
        monkeypatch.delenv(var, raising=False)

    with pytest.raises(RuntimeError) as exc:
        auto_init()
    assert "missing" in str(exc.value).lower()
