"""Telemetry & Edge-Sync edge SDK."""

from .client import Client, auto_init, force_flush, init, track

__all__ = ["Client", "init", "auto_init", "track", "force_flush"]
