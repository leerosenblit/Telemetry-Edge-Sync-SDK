"""REST API server for the Telemetry & Edge-Sync SDK.

Receives batches from the car's Raspberry Pi, stores them durably in SQLite, and serves
them back for the dashboard. The two correctness properties that matter:

  * Idempotent ingestion  -- points are upserted on their client-assigned id, so
    resending a batch (after a missed acknowledgement) never creates duplicates.
  * Order by device time   -- points are stored and returned by their *device*
    timestamp, never the server's arrival time, so buffered/late data lands in
    the correct historical position.

A small server-side alert rule engine also runs on ingest: each point is checked
against a list of threshold RULES and any breach is recorded (idempotently) for
the dashboard's Alerts panel.
"""

import json
import os
import secrets
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

API_KEY = os.environ.get("TELEMETRY_API_KEY", "dev-key")
DB_PATH = os.environ.get("TELEMETRY_DB", "telemetry.db")
DASHBOARD = Path(__file__).resolve().parent.parent / "dashboard" / "index.html"

# --- alert rules ------------------------------------------------------------
# A deliberately simple threshold engine (one of the deck's stretch goals). Each
# rule fires when a point's value for `metric` crosses `threshold` in direction
# `op`. Breaches are stored idempotently so resent batches don't duplicate them.
# Rules live in the DB so the portal can edit them at runtime (no restart). The
# table is seeded with these defaults the first time it's created.
DEFAULT_RULES = [
    {"metric": "battery_temp_C", "op": ">", "threshold": 45, "severity": "critical",
     "message": "Pack temperature over 45°C"},
    {"metric": "bms_temp_1_C", "op": ">", "threshold": 50, "severity": "critical",
     "message": "BMS probe over-temperature"},
    {"metric": "mms_temperature_C", "op": ">", "threshold": 80, "severity": "warning",
     "message": "Motor controller over-temperature"},
    {"metric": "bms_soc_percent", "op": "<", "threshold": 20, "severity": "warning",
     "message": "Low state of charge"},
]


def _breaches(op: str, value: float, threshold: float) -> bool:
    return value > threshold if op == ">" else value < threshold


def load_rules() -> list[dict]:
    """Current alert rules from the DB (enabled ones drive the engine)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, metric, op, threshold, severity, message, enabled "
            "FROM rules ORDER BY id"
        ).fetchall()
    return [dict(r) for r in rows]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Telemetry & Edge-Sync API", version="1.0", lifespan=lifespan)

# The dashboard is a static page that fetches from this server, so allow it.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- data model -------------------------------------------------------------

class Point(BaseModel):
    id: str
    metric: str
    value: float
    ts: int          # device timestamp, epoch milliseconds


class Batch(BaseModel):
    device_id: str
    metadata: dict = {}
    points: list[Point]


# --- storage ----------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    # One connection per request keeps things thread-safe under FastAPI's
    # threadpool. WAL lets reads (dashboard) and writes (ingest) coexist.
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS telemetry (
                id          TEXT PRIMARY KEY,   -- client-assigned -> idempotent upsert
                device_id   TEXT NOT NULL,
                metric      TEXT NOT NULL,
                value       REAL NOT NULL,
                device_ts   INTEGER NOT NULL,   -- order + late-arrival by this
                received_ts INTEGER NOT NULL    -- server arrival, diagnostics only
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_telemetry_lookup "
            "ON telemetry (device_id, metric, device_ts)"
        )
        # Static per-device metadata (fw, type, link state). Sent once per batch,
        # we keep only the latest so the dashboard can show device health.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS device_meta (
                device_id   TEXT PRIMARY KEY,
                metadata    TEXT NOT NULL,      -- JSON blob
                updated_ts  INTEGER NOT NULL
            )
            """
        )
        # Alerts raised by the rule engine. id is derived from the point id +
        # rule, so re-ingesting a batch never duplicates an alert.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id          TEXT PRIMARY KEY,
                device_id   TEXT NOT NULL,
                metric      TEXT NOT NULL,
                value       REAL NOT NULL,
                threshold   REAL NOT NULL,
                severity    TEXT NOT NULL,
                message     TEXT NOT NULL,
                device_ts   INTEGER NOT NULL,
                created_ts  INTEGER NOT NULL
            )
            """
        )
        # Editable alert rules (managed from the portal's Rules tab).
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS rules (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                metric    TEXT NOT NULL,
                op        TEXT NOT NULL,        -- '>' or '<'
                threshold REAL NOT NULL,
                severity  TEXT NOT NULL,        -- 'critical' | 'warning'
                message   TEXT NOT NULL,
                enabled   INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        # Seed defaults on first creation only.
        (n,) = conn.execute("SELECT COUNT(*) FROM rules").fetchone()
        if n == 0:
            conn.executemany(
                "INSERT INTO rules (metric, op, threshold, severity, message) "
                "VALUES (:metric, :op, :threshold, :severity, :message)",
                DEFAULT_RULES,
            )
        # API keys the car authenticates with. The dashboard's Setup tab issues
        # and revokes them; ingestion validates against this table.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS api_keys (
                key        TEXT PRIMARY KEY,
                label      TEXT NOT NULL,
                created_ts INTEGER NOT NULL,
                revoked    INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        # Seed the default key so existing setups (and tests) keep working.
        conn.execute(
            "INSERT OR IGNORE INTO api_keys (key, label, created_ts) VALUES (?, ?, ?)",
            (API_KEY, "default", _now_ms()),
        )


def _now_ms() -> int:
    return int(time.time() * 1000)


def _valid_key(key: str | None) -> bool:
    """True if `key` exists in api_keys and is not revoked."""
    if not key:
        return False
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM api_keys WHERE key = ? AND revoked = 0", (key,)
        ).fetchone()
    return row is not None


# --- endpoints --------------------------------------------------------------

@app.post("/api/v1/telemetry")
def ingest(batch: Batch, x_api_key: str = Header(default=None)):
    """Ingest a batch: authenticate, then idempotently upsert every point."""
    if not _valid_key(x_api_key):
        raise HTTPException(status_code=401, detail="bad api key")

    received_ts = _now_ms()
    rows = [
        (p.id, batch.device_id, p.metric, p.value, p.ts, received_ts)
        for p in batch.points
    ]

    # Evaluate alert rules against the batch. Alert id = point id + rule id, so
    # re-ingesting (at-least-once delivery) never duplicates an alert.
    active_rules = [r for r in load_rules() if r["enabled"]]
    alert_rows = []
    for p in batch.points:
        for rule in active_rules:
            if p.metric == rule["metric"] and _breaches(rule["op"], p.value, rule["threshold"]):
                alert_rows.append((
                    f"{p.id}:rule{rule['id']}", batch.device_id, p.metric, p.value,
                    rule["threshold"], rule["severity"], rule["message"], p.ts, received_ts,
                ))

    with _connect() as conn:
        # ON CONFLICT(id) DO UPDATE => upsert. Resending overwrites the same row
        # instead of inserting a duplicate. received_ts refreshes; device_ts does
        # not move, so historical ordering is stable.
        conn.executemany(
            """
            INSERT INTO telemetry (id, device_id, metric, value, device_ts, received_ts)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                device_id   = excluded.device_id,
                metric      = excluded.metric,
                value       = excluded.value,
                device_ts   = excluded.device_ts,
                received_ts = excluded.received_ts
            """,
            rows,
        )
        if batch.metadata:
            conn.execute(
                """
                INSERT INTO device_meta (device_id, metadata, updated_ts)
                VALUES (?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    metadata = excluded.metadata, updated_ts = excluded.updated_ts
                """,
                (batch.device_id, json.dumps(batch.metadata), received_ts),
            )
        if alert_rows:
            conn.executemany(
                """
                INSERT OR IGNORE INTO alerts
                    (id, device_id, metric, value, threshold, severity, message, device_ts, created_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                alert_rows,
            )
    return {"accepted": len(batch.points), "alerts": len(alert_rows)}


@app.get("/api/v1/metrics")
def metrics(
    device: str | None = None,
    metric: str | None = None,
    from_: int | None = Query(default=None, alias="from"),
    to: int | None = None,
):
    """Read points for the dashboard, ordered by device time (oldest first).

    `from`/`to` are device-timestamp bounds in epoch milliseconds. The query
    param is spelled `from`; we alias it to `from_` since `from` is reserved.
    """
    clauses, params = [], []
    if device is not None:
        clauses.append("device_id = ?")
        params.append(device)
    if metric is not None:
        clauses.append("metric = ?")
        params.append(metric)
    if from_ is not None:
        clauses.append("device_ts >= ?")
        params.append(from_)
    if to is not None:
        clauses.append("device_ts <= ?")
        params.append(to)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        "SELECT id, device_id, metric, value, device_ts AS ts, received_ts "
        "FROM telemetry" + where + " ORDER BY device_ts ASC"
    )
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/v1/devices")
def devices():
    """Last-seen / health per device (plus latest metadata) for the dashboard."""
    sql = """
        SELECT t.device_id,
               COUNT(*)         AS points,
               MAX(t.device_ts) AS last_device_ts,
               MAX(t.received_ts) AS last_received_ts,
               m.metadata       AS metadata
        FROM telemetry t
        LEFT JOIN device_meta m ON m.device_id = t.device_id
        GROUP BY t.device_id
        ORDER BY last_received_ts DESC
    """
    with _connect() as conn:
        rows = conn.execute(sql).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["metadata"] = json.loads(d["metadata"]) if d.get("metadata") else {}
        out.append(d)
    return out


@app.get("/api/v1/alerts")
def alerts(device: str | None = None, limit: int = 50):
    """Recent alerts raised by the rule engine, newest first."""
    clauses, params = [], []
    if device is not None:
        clauses.append("device_id = ?")
        params.append(device)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(max(1, min(limit, 500)))
    sql = (
        "SELECT id, device_id, metric, value, threshold, severity, message, "
        "device_ts, created_ts FROM alerts" + where +
        " ORDER BY device_ts DESC LIMIT ?"
    )
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


class RuleIn(BaseModel):
    metric: str
    op: str                      # '>' or '<'
    threshold: float
    severity: str = "warning"    # 'critical' | 'warning'
    message: str = ""


@app.get("/api/v1/rules")
def get_rules():
    """List the configured alert rules."""
    return load_rules()


@app.post("/api/v1/rules", status_code=201)
def create_rule(rule: RuleIn):
    """Add an alert rule (takes effect on the next ingest, no restart)."""
    if rule.op not in (">", "<"):
        raise HTTPException(status_code=422, detail="op must be '>' or '<'")
    if rule.severity not in ("critical", "warning"):
        raise HTTPException(status_code=422, detail="severity must be 'critical' or 'warning'")
    message = rule.message or f"{rule.metric} {rule.op} {rule.threshold}"
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO rules (metric, op, threshold, severity, message) "
            "VALUES (?, ?, ?, ?, ?)",
            (rule.metric, rule.op, rule.threshold, rule.severity, message),
        )
        rule_id = cur.lastrowid
    return {"id": rule_id, **rule.model_dump(), "message": message, "enabled": 1}


@app.patch("/api/v1/rules/{rule_id}")
def toggle_rule(rule_id: int, enabled: bool):
    """Enable or disable a rule without deleting it."""
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE rules SET enabled = ? WHERE id = ?", (1 if enabled else 0, rule_id)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="no such rule")
    return {"id": rule_id, "enabled": enabled}


@app.delete("/api/v1/rules/{rule_id}")
def delete_rule(rule_id: int):
    """Remove an alert rule."""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM rules WHERE id = ?", (rule_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="no such rule")
    return {"deleted": rule_id}


# --- API keys ---------------------------------------------------------------
# Issued and revoked from the dashboard's Setup tab; the car puts its key in the
# X-API-Key header (or via auto_init). Like the rules CRUD, these endpoints are
# unauthenticated for this local-tool scope (see docs/future-work.md).

class KeyIn(BaseModel):
    label: str = "device"


@app.get("/api/v1/keys")
def get_keys():
    """List API keys (newest first)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT key, label, created_ts, revoked FROM api_keys ORDER BY created_ts DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/api/v1/keys", status_code=201)
def create_key(body: KeyIn):
    """Generate a new API key the car can authenticate with."""
    key = secrets.token_urlsafe(24)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO api_keys (key, label, created_ts) VALUES (?, ?, ?)",
            (key, body.label or "device", _now_ms()),
        )
    return {"key": key, "label": body.label or "device", "revoked": 0}


@app.delete("/api/v1/keys/{key}")
def revoke_key(key: str):
    """Revoke an API key (soft delete — kept for history)."""
    with _connect() as conn:
        cur = conn.execute("UPDATE api_keys SET revoked = 1 WHERE key = ?", (key,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="no such key")
    return {"revoked": key}


@app.delete("/api/v1/telemetry")
def clear_telemetry(device: str | None = None):
    """Delete stored telemetry and alerts (optionally for one device).

    A demo/reset convenience — wipe the chart between video takes. Live devices
    repopulate immediately. Rules and API keys are left intact. Like the other
    management endpoints this is unauthenticated (local-tool scope).
    """
    with _connect() as conn:
        if device is None:
            n = conn.execute("DELETE FROM telemetry").rowcount
            conn.execute("DELETE FROM alerts")
        else:
            n = conn.execute("DELETE FROM telemetry WHERE device_id = ?", (device,)).rowcount
            conn.execute("DELETE FROM alerts WHERE device_id = ?", (device,))
    return {"cleared": device or "all", "deleted_points": n}


# --- dashboard (served from the same origin so it's a one-URL portal) -------

@app.get("/", include_in_schema=False)
def dashboard():
    """The visual portal. Open http://127.0.0.1:8000/ in a browser."""
    return FileResponse(DASHBOARD)
