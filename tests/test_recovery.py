"""Reboot / crash-recovery: data written before a process dies is recovered
intact by a fresh SDK instance on the same on-disk queue.

This is the durability half of the "no data loss" promise (the deck's
"Pre-Crash Rescue"): because every point is persisted to SQLite at track()
time, a crash or reboot loses nothing -- a new process drains the backlog.
"""

from conftest import DEVICE, read_metrics

from sdk.client import Client
from sdk.queue import Queue


def test_data_survives_process_restart(server, flaky_network, tmp_path):
    db = str(tmp_path / "outbox.db")

    # --- process 1: buffer data while "offline", then die without sending ---
    net_down = flaky_network(server)
    net_down.up = False
    sdk_a = Client(
        "http://unused", "dev-key", DEVICE,
        db_path=db, batch_size=10, flush_interval=0.1, sender=net_down,
    )
    N = 150
    for i in range(N):
        sdk_a.track("speed", float(i), ts=5_000_000 + i)
    sdk_a.close()                                    # simulate the process ending

    assert read_metrics(server) == []                # nothing was ever sent

    # The "reboot": a brand-new queue handle on the same file still has it all.
    q = Queue(db)
    assert q.unsent_count() == N                     # durable across restart
    q.close()

    # --- process 2: fresh SDK, network up, drains the recovered backlog ---
    net_up = flaky_network(server)
    sdk_b = Client(
        "http://unused", "dev-key", DEVICE,
        db_path=db, batch_size=10, flush_interval=0.1, sender=net_up,
    )
    assert sdk_b.force_flush(timeout=10) is True

    rows = read_metrics(server)
    assert len(rows) == N                            # everything recovered
    ts = [r["ts"] for r in rows]
    assert ts == sorted(ts)                          # still in device-time order
    assert [r["value"] for r in rows] == [float(i) for i in range(N)]
    sdk_b.close()
