"""Edge SDK public API and background sync pipeline.

What a developer using the SDK calls:

    init(server_url, api_key, device_id)
    track(metric, value, ts=None)      -- returns immediately, never blocks
    force_flush()                      -- drain everything now (e.g. on shutdown)

What happens after track():

    1. The point is written to a durable SQLite queue (sdk/queue.py).
    2. A background batcher pulls unsent points oldest-first and groups them.
    3. The sender POSTs the batch to the REST server.
    4. Points are marked sent only after the server acknowledges. Failed sends
       retry with backoff, so a dropped connection just grows the backlog, which
       then drains in chronological order once the network returns.

The pipeline is deliberately data-agnostic: it only ever sees metric/value/ts.
"""

import threading
import time

import httpx

from . import sync_policy
from .queue import Queue


class Client:
    def __init__(
        self,
        server_url: str,
        api_key: str,
        device_id: str,
        *,
        db_path: str = "sdk_outbox.db",
        metadata: dict | None = None,
        batch_size: int = 50,
        flush_interval: float = 2.0,
        max_backoff: float = 30.0,
        network: str | None = None,
        battery: float | None = None,
        sender=None,
    ):
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.device_id = device_id
        self.metadata = metadata or {}
        self.max_backoff = max_backoff

        # Link conditions drive the network-aware sync policy. When `network` is
        # set, batch_size / flush_interval are derived from it dynamically;
        # otherwise the fixed values passed in are used.
        self.network = network
        self.battery = battery
        self._base_batch_size = batch_size
        self._base_flush_interval = flush_interval
        self.batch_size = batch_size          # current effective values
        self.flush_interval = flush_interval
        self._apply_policy()

        self.queue = Queue(db_path)

        # The sender is injectable so tests can simulate a flaky/offline network.
        # It takes a batch dict and must raise on failure, return on success.
        self._sender = sender or self._http_send
        self._http = httpx.Client(timeout=10.0) if sender is None else None

        self._seq = 0
        self._seq_lock = threading.Lock()

        self._stop = threading.Event()
        self._wake = threading.Event()   # nudges the batcher to flush now
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    # --- public API ---------------------------------------------------------

    def track(self, metric: str, value: float, ts: int | None = None) -> str:
        """Inject one data point. Persists it durably and returns immediately."""
        if ts is None:
            ts = int(time.time() * 1000)
        point_id = self._next_id(ts)
        self.queue.enqueue(point_id, metric, float(value), ts)
        # If we've hit a full batch, nudge the worker instead of waiting.
        if self.queue.unsent_count() >= self.batch_size:
            self._wake.set()
        return point_id

    def force_flush(self, timeout: float = 15.0) -> bool:
        """Block until the queue is fully drained or `timeout` elapses.

        Returns True if everything was acknowledged, False on timeout.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.queue.unsent_count() == 0:
                return True
            self._wake.set()
            time.sleep(0.05)
        return self.queue.unsent_count() == 0

    def close(self) -> None:
        """Stop the background worker and release resources."""
        self._stop.set()
        self._wake.set()
        self._worker.join(timeout=5.0)
        if self._http is not None:
            self._http.close()
        self.queue.close()

    # --- network-aware sync policy ------------------------------------------

    def set_link(self, network: str | None = None, battery: float | None = None) -> None:
        """Update the device's link conditions; the batcher adapts immediately."""
        if network is not None:
            self.network = network
        if battery is not None:
            self.battery = battery
        self._apply_policy()
        self._wake.set()   # re-evaluate the loop now

    def _apply_policy(self) -> None:
        """Recompute effective batch size / flush interval from link state."""
        if self.network is None:
            self.batch_size = self._base_batch_size
            self.flush_interval = self._base_flush_interval
            self._allow_send = True
        else:
            self.batch_size, self.flush_interval, self._allow_send = sync_policy.plan(
                self.network, self.battery
            )

    def _send_metadata(self) -> dict:
        """Static metadata plus current link state, sent once per batch."""
        meta = dict(self.metadata)
        if self.network is not None:
            meta["network"] = self.network
        if self.battery is not None:
            meta["battery"] = self.battery
        return meta

    # --- id assignment ------------------------------------------------------

    def _next_id(self, ts: int) -> str:
        # device + sequence + timestamp -> globally unique, client-assigned.
        # This is what makes server ingestion idempotent.
        with self._seq_lock:
            self._seq += 1
            seq = self._seq
        return f"{self.device_id}-{seq:06d}-{ts}"

    # --- background batcher + sender ----------------------------------------

    def _run(self) -> None:
        backoff = 1.0
        while not self._stop.is_set():
            # Flush on a timer or when nudged (full batch / force_flush / close).
            self._wake.wait(timeout=self.flush_interval)
            self._wake.clear()

            # Network-aware policy: when the device knows it's offline, don't
            # attempt to send -- just keep buffering durably (saves the radio).
            if not self._allow_send:
                continue

            sent_any = True
            while sent_any and not self._stop.is_set():
                points = self.queue.fetch_unsent(self.batch_size)
                if not points:
                    sent_any = False
                    backoff = 1.0
                    break
                try:
                    self._send_batch(points)
                    self.queue.mark_sent([p["id"] for p in points])
                    backoff = 1.0
                except Exception:
                    # Network/server failure: leave points unsent and back off.
                    # They stay safely in the queue and are retried next loop.
                    self._sleep_backoff(backoff)
                    backoff = min(backoff * 2, self.max_backoff)
                    sent_any = False

        # On close, make a best-effort final drain of whatever is queued.
        self._drain_remaining()

    def _send_batch(self, points: list[dict]) -> None:
        batch = {
            "device_id": self.device_id,
            "metadata": self._send_metadata(),
            "points": points,
        }
        self._sender(batch)

    def _http_send(self, batch: dict) -> None:
        resp = self._http.post(
            f"{self.server_url}/api/v1/telemetry",
            json=batch,
            headers={"X-API-Key": self.api_key},
        )
        resp.raise_for_status()

    def _sleep_backoff(self, seconds: float) -> None:
        # Interruptible sleep so close()/force_flush() stay responsive.
        self._wake.wait(timeout=seconds)
        self._wake.clear()

    def _drain_remaining(self) -> None:
        try:
            points = self.queue.fetch_unsent(self.batch_size)
            while points:
                self._send_batch(points)
                self.queue.mark_sent([p["id"] for p in points])
                points = self.queue.fetch_unsent(self.batch_size)
        except Exception:
            pass  # best effort; unsent data remains durably on disk


# --- module-level convenience API ------------------------------------------
# Mirrors the architecture's public surface: init / track / force_flush.

_default: Client | None = None


def init(server_url: str, api_key: str, device_id: str, **kwargs) -> Client:
    global _default
    _default = Client(server_url, api_key, device_id, **kwargs)
    return _default


def auto_init(config_path: str | None = None) -> Client:
    """Initialize the SDK without hand-coding init() — read config from, in order:

      1. an explicit JSON file at `config_path`,
      2. a `telemetry.json` file in the current directory (if present),
      3. environment variables: TELEMETRY_SERVER_URL, TELEMETRY_API_KEY,
         TELEMETRY_DEVICE_ID, and optional TELEMETRY_NETWORK.

    A config file may set: server_url, api_key, device_id, network, and any other
    Client option (batch_size, flush_interval, db_path, metadata, …). Handy on a
    device that's provisioned once with a key from the dashboard's Setup tab.
    """
    import json
    import os

    cfg: dict = {}
    path = config_path or ("telemetry.json" if os.path.exists("telemetry.json") else None)
    if path:
        with open(path, "r", encoding="utf-8") as f:
            cfg = json.load(f)

    server_url = cfg.get("server_url") or os.environ.get("TELEMETRY_SERVER_URL")
    api_key = cfg.get("api_key") or os.environ.get("TELEMETRY_API_KEY")
    device_id = cfg.get("device_id") or os.environ.get("TELEMETRY_DEVICE_ID")
    network = cfg.get("network") or os.environ.get("TELEMETRY_NETWORK")

    missing = [n for n, v in
               (("server_url", server_url), ("api_key", api_key), ("device_id", device_id))
               if not v]
    if missing:
        raise RuntimeError(
            "auto_init() is missing: " + ", ".join(missing) +
            ". Provide them in a config file or TELEMETRY_* environment variables."
        )

    # Pass through any extra Client options from the config file.
    opts = {k: v for k, v in cfg.items()
            if k not in ("server_url", "api_key", "device_id")}
    if network and "network" not in opts:
        opts["network"] = network
    return init(server_url, api_key, device_id, **opts)


def track(metric: str, value: float, ts: int | None = None) -> str:
    if _default is None:
        raise RuntimeError("SDK not initialized; call init() first")
    return _default.track(metric, value, ts)


def force_flush(timeout: float = 15.0) -> bool:
    if _default is None:
        raise RuntimeError("SDK not initialized; call init() first")
    return _default.force_flush(timeout)
