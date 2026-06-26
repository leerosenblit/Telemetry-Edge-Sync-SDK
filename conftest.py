"""Shared test fixtures and helpers.

Also ensures the project root is importable so `sdk` and `server` resolve as
packages when tests run from anywhere.
"""

import importlib
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest
from fastapi.testclient import TestClient

API_KEY = "dev-key"
DEVICE = "solar-car-01"


@pytest.fixture
def server(tmp_path, monkeypatch):
    """A fresh server bound to a temp SQLite DB for each test."""
    monkeypatch.setenv("TELEMETRY_DB", str(tmp_path / "server.db"))
    monkeypatch.setenv("TELEMETRY_API_KEY", API_KEY)
    import server.main as srv

    importlib.reload(srv)                 # re-read env -> point at the temp DB
    with TestClient(srv.app) as client:   # lifespan creates the tables
        yield client


class FlakyNetwork:
    """Injectable SDK sender that forwards batches to the test server, but can
    be switched offline, or made to "lose" the acknowledgement after the server
    has already stored the batch (to exercise idempotent resend)."""

    def __init__(self, client: TestClient):
        self.client = client
        self.up = True
        self.drop_ack = False
        self.delivered = 0   # how many POSTs actually reached the server

    def __call__(self, batch: dict) -> None:
        if not self.up:
            raise ConnectionError("network down")
        resp = self.client.post(
            "/api/v1/telemetry", json=batch, headers={"X-API-Key": API_KEY}
        )
        resp.raise_for_status()
        self.delivered += 1
        if self.drop_ack:
            raise ConnectionError("acknowledgement lost")


@pytest.fixture
def flaky_network():
    """Factory: flaky_network(server) -> a toggleable sender."""
    return FlakyNetwork


def read_metrics(server, device=DEVICE):
    return server.get("/api/v1/metrics", params={"device": device}).json()
