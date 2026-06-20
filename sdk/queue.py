"""Durable local queue for the edge SDK.

Every tracked point is written to SQLite *before* anything tries to send it.
That is the whole durability story: if the network is down or the device
reboots mid-flight, the data is still on disk and gets drained later.

The queue is the only shared state between the caller's thread (which calls
`enqueue` via `track()`) and the background batcher thread (which calls
`fetch_unsent` / `mark_sent`), so every operation is guarded by a lock and uses
a single connection opened with check_same_thread=False.
"""

import sqlite3
import threading


class Queue:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS outbox (
                id     TEXT PRIMARY KEY,   -- client-assigned point id
                metric TEXT NOT NULL,
                value  REAL NOT NULL,
                ts     INTEGER NOT NULL,   -- device timestamp (epoch ms)
                sent   INTEGER NOT NULL DEFAULT 0,
                seq    INTEGER             -- monotonic insert order, for stable tiebreak
            )
            """
        )
        self._conn.commit()

    def enqueue(self, id: str, metric: str, value: float, ts: int) -> None:
        """Persist one point. INSERT OR IGNORE so a duplicate id is a no-op."""
        with self._lock:
            self._conn.execute(
                "INSERT OR IGNORE INTO outbox (id, metric, value, ts, sent, seq) "
                "VALUES (?, ?, ?, ?, 0, (SELECT COALESCE(MAX(seq), 0) + 1 FROM outbox))",
                (id, metric, value, ts),
            )
            self._conn.commit()

    def fetch_unsent(self, limit: int) -> list[dict]:
        """Oldest-first batch of points not yet acknowledged by the server.

        Ordered by device timestamp (then insert order) so the backlog drains in
        chronological order the moment the network returns.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, metric, value, ts FROM outbox "
                "WHERE sent = 0 ORDER BY ts ASC, seq ASC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_sent(self, ids: list[str]) -> None:
        """Mark points sent -- only ever called after the server acknowledges."""
        if not ids:
            return
        with self._lock:
            self._conn.executemany(
                "UPDATE outbox SET sent = 1 WHERE id = ?", [(i,) for i in ids]
            )
            self._conn.commit()

    def unsent_count(self) -> int:
        with self._lock:
            (n,) = self._conn.execute(
                "SELECT COUNT(*) FROM outbox WHERE sent = 0"
            ).fetchone()
        return n

    def close(self) -> None:
        with self._lock:
            self._conn.close()
