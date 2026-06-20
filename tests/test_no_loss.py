"""The test that proves the one guarantee: no data is lost when the network
drops, and what arrives is in correct time order with no duplicates.

We drive the *real* server ingestion logic through FastAPI's TestClient, and
inject a toggleable "network" into the SDK so we can pull the plug mid-stream
and plug it back in. Shared fixtures (`server`, `flaky_network`) live in
conftest.py.
"""

import time

from conftest import DEVICE, read_metrics

from sdk.client import Client


def test_no_loss_across_network_drop(server, flaky_network, tmp_path):
    net = flaky_network(server)
    net.up = False                                   # start with no network
    sdk = Client(
        "http://unused", "dev-key", DEVICE,
        db_path=str(tmp_path / "outbox.db"),
        batch_size=10, flush_interval=0.1, sender=net,
    )

    N = 200
    for i in range(N):
        sdk.track("speed", float(i), ts=1_000_000 + i)

    time.sleep(0.5)                                  # let the batcher try & fail
    assert read_metrics(server) == []                # nothing got through
    assert sdk.queue.unsent_count() == N             # all safe on disk

    net.up = True                                    # network restored
    assert sdk.force_flush(timeout=10) is True       # backlog drains

    rows = read_metrics(server)
    assert len(rows) == N                            # nothing lost
    ts = [r["ts"] for r in rows]
    assert ts == sorted(ts)                          # correct time order
    assert [r["value"] for r in rows] == [float(i) for i in range(N)]
    sdk.close()


def test_idempotent_on_lost_acknowledgement(server, flaky_network, tmp_path):
    net = flaky_network(server)
    net.drop_ack = True                              # server stores, ack "lost"
    sdk = Client(
        "http://unused", "dev-key", DEVICE,
        db_path=str(tmp_path / "outbox.db"),
        batch_size=5, flush_interval=0.05, sender=net,
    )

    N = 20
    for i in range(N):
        sdk.track("speed", float(i), ts=2_000_000 + i)

    time.sleep(0.4)                                  # some batches reach server,
                                                     # but every ack is "lost"
    net.drop_ack = False                             # acks flow again
    assert sdk.force_flush(timeout=10) is True       # never-acked points resend

    rows = read_metrics(server)
    assert len(rows) == N                            # upsert deduped the resends
    # Every point was delivered at least once with a lost ack and then resent,
    # so total deliveries exceed the N/5 distinct batches: proof of resend.
    assert net.delivered > N / 5
    sdk.close()
