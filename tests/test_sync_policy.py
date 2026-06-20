"""Network-aware sync policy: faster links sync smaller batches more often;
slower links sync larger batches less often; low battery backs off further;
offline buffers without sending."""

from sdk import sync_policy


def test_faster_link_syncs_more_often_than_slower():
    wifi_batch, wifi_interval, _ = sync_policy.plan("wifi")
    edge_batch, edge_interval, _ = sync_policy.plan("edge")
    assert wifi_interval < edge_interval        # wifi sends more often
    assert wifi_batch < edge_batch              # ...in smaller batches


def test_offline_buffers_without_sending():
    _, _, allow_send = sync_policy.plan("offline")
    assert allow_send is False
    assert sync_policy.plan("lte")[2] is True


def test_low_battery_backs_off():
    base_batch, base_interval, _ = sync_policy.plan("lte", battery=90)
    low_batch, low_interval, _ = sync_policy.plan("lte", battery=10)
    assert low_interval > base_interval         # sync less often on low battery
    assert low_batch >= base_batch              # ...in larger bursts
