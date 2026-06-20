"""Telemetry & Edge-Sync edge SDK."""

from .client import Client, force_flush, init, track

__all__ = ["Client", "init", "track", "force_flush"]
