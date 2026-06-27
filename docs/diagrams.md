# Diagrams

All diagrams are [Mermaid](https://mermaid.js.org/) — they render automatically on
GitHub and in most Markdown viewers (VS Code: "Markdown Preview Mermaid Support").

## System architecture

How telemetry flows from the car to the pit wall.

```mermaid
flowchart LR
    subgraph CAR["Solar car — Raspberry Pi"]
        CAN["CAN bus<br/>BMS · MMS · battery-temp"] --> OS["SolarRace-OS<br/>decodes → vehicle_state"]
        OS --> BRIDGE["track_vehicle_state()"]
        subgraph SDK["Edge-Sync SDK"]
            BRIDGE --> Q[("SQLite outbox<br/>durable queue")]
            Q --> BATCH["Batcher<br/>(count / time)"]
            BATCH --> SEND["Sender<br/>retry + backoff"]
        end
    end

    SEND -- "HTTPS POST /api/v1/telemetry<br/>(batch, X-API-Key)" --> API

    subgraph SERVER["REST API server (FastAPI)"]
        API["Ingest<br/>auth · upsert · rules"] --> DB[("SQLite<br/>telemetry · alerts · …")]
    end

    DB --> READ["GET /api/v1/metrics · /alerts · /devices"]
    READ -- "poll every 1.5s" --> PORTAL["Pit-wall portal<br/>charts · devices · alerts · rules · setup"]

    style SDK fill:#0e1b1a,stroke:#2dd4bf
    style SERVER fill:#0e1422,stroke:#5b8cff
```

## Entity-relationship diagram (ERD)

The server's SQLite store (plus the SDK's on-device outbox). The car-assigned
point `id` is the idempotency key; alert ids are derived from it.

```mermaid
erDiagram
    OUTBOX ||..|| TELEMETRY : "syncs to (by point id)"
    TELEMETRY ||--o{ ALERTS : "breach raises"
    RULES ||--o{ ALERTS : "evaluated into"
    DEVICE_META ||--o{ TELEMETRY : "describes (device_id)"
    API_KEYS ||..o{ TELEMETRY : "authenticates ingest"

    OUTBOX {
        TEXT id PK "device-seq-ts"
        TEXT metric
        REAL value
        INTEGER ts "device time (ms)"
        INTEGER sent "0/1"
        INTEGER seq "insert order"
    }
    TELEMETRY {
        TEXT id PK "client-assigned"
        TEXT device_id
        TEXT metric
        REAL value
        INTEGER device_ts "order + late-arrival"
        INTEGER received_ts "diagnostics"
    }
    DEVICE_META {
        TEXT device_id PK
        TEXT metadata "JSON: fw, type, network…"
        INTEGER updated_ts
    }
    ALERTS {
        TEXT id PK "pointid:ruleN"
        TEXT device_id
        TEXT metric
        REAL value
        REAL threshold
        TEXT severity
        TEXT message
        INTEGER device_ts
        INTEGER created_ts
    }
    RULES {
        INTEGER id PK
        TEXT metric
        TEXT op "> or <"
        REAL threshold
        TEXT severity
        TEXT message
        INTEGER enabled "0/1"
    }
    API_KEYS {
        TEXT key PK
        TEXT label
        INTEGER created_ts
        INTEGER revoked "0/1"
    }
```

## Sequence — track to chart (with offline recovery)

```mermaid
sequenceDiagram
    autonumber
    participant Pi as Car (SolarRace-OS)
    participant SDK as Edge-Sync SDK
    participant Q as SQLite outbox
    participant API as REST server
    participant UI as Pit portal

    Pi->>SDK: track_vehicle_state(vehicle_state, ts)
    SDK->>Q: enqueue point(s) (durable)
    Note over SDK,Q: returns immediately — never blocks the car

    loop batcher (every flush_interval, or when full)
        SDK->>Q: fetch_unsent(oldest-first)
        alt network up
            SDK->>API: POST /api/v1/telemetry (batch, X-API-Key)
            API->>API: validate key · upsert by id · evaluate rules
            API-->>SDK: 200 {accepted, alerts}
            SDK->>Q: mark_sent(ids)
        else network down
            SDK--xAPI: POST fails
            Note over SDK: keep points unsent · backoff 1s→2s→4s…
            Note over Q: backlog grows safely on disk
        end
    end

    UI->>API: GET /api/v1/metrics (poll every 1.5s)
    API-->>UI: points (ordered by device_ts) + alerts
    Note over UI: gap backfills in order once the link returns
```

## State — the batcher

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Draining: timer fires / queue full / force_flush
    Draining --> Sending: unsent points exist
    Draining --> Idle: queue empty
    Sending --> Idle: 200 OK (mark_sent)
    Sending --> Backoff: send failed
    Backoff --> Sending: wait (1s→2s→4s… capped)
    Idle --> BufferOnly: network = "offline"
    BufferOnly --> Idle: link restored
    note right of BufferOnly
        track() still persists to disk;
        sends are skipped to save the radio
    end note
```
