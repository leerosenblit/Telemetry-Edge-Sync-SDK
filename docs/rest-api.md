# REST API

Base URL (local): `http://127.0.0.1:8000`. Interactive reference (Swagger UI): `/docs`.

Telemetry ingestion requires an `X-API-Key` header (see [user init](user-init.md)). Read
and management endpoints are unauthenticated in this build (local-tool scope).

---

## `POST /api/v1/telemetry`

Ingest a batch. Auth: `X-API-Key`. Body:

```json
{
  "device_id": "solar-car-01",
  "metadata": { "fw": "RaceOS-2.0", "type": "solar-car", "network": "lte" },
  "points": [
    { "id": "solar-car-01-000001-1718900000100", "metric": "bms_voltage_V", "value": 108.4, "ts": 1718900000100 }
  ]
}
```

Each point is idempotently upserted on `id`; metadata is stored as the device's latest;
alert rules are evaluated. Response: `{ "accepted": <int>, "alerts": <int> }`.
Bad/missing/revoked key → `401`.

## `GET /api/v1/metrics`

Read points, ordered by device time (oldest first).

Query params: `device`, `metric`, `from` (epoch ms), `to` (epoch ms) — all optional.
Response: array of `{ id, device_id, metric, value, ts, received_ts }`.

```
GET /api/v1/metrics?device=solar-car-01&metric=battery_temp_C
```

## `GET /api/v1/devices`

Per-device health. Response: array of
`{ device_id, points, last_device_ts, last_received_ts, metadata }`.

## `GET /api/v1/alerts`

Recent alerts, newest first. Query params: `device` (optional), `limit` (default 50).
Response: array of `{ id, device_id, metric, value, threshold, severity, message,
device_ts, created_ts }`.

## Alert rules

| Method & path | Body / params | Response |
|---|---|---|
| `GET /api/v1/rules` | — | array of `{ id, metric, op, threshold, severity, message, enabled }` |
| `POST /api/v1/rules` | `{ metric, op (">"/"<"), threshold, severity ("critical"/"warning"), message }` | the created rule |
| `PATCH /api/v1/rules/{id}?enabled=<bool>` | — | `{ id, enabled }` |
| `DELETE /api/v1/rules/{id}` | — | `{ deleted: id }` |

Changes take effect on the next ingested batch.

## API keys

| Method & path | Body | Response |
|---|---|---|
| `GET /api/v1/keys` | — | array of `{ key, label, created_ts, revoked }` |
| `POST /api/v1/keys` | `{ label }` | `{ key, label, revoked }` (the generated key) |
| `DELETE /api/v1/keys/{key}` | — | `{ revoked: key }` (soft delete) |

## `GET /`

Serves the pit-wall portal (`dashboard/index.html`).
