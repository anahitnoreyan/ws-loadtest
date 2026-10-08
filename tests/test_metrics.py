import pytest

from wsload.metrics import Metrics, percentile


def test_percentile_nearest_rank():
    values = list(range(1, 101))
    assert percentile(values, 50) == 50
    assert percentile(values, 95) == 95
    assert percentile(values, 100) == 100


def test_percentile_empty_list():
    assert percentile([], 95) == 0.0


def test_percentile_invalid_pct():
    with pytest.raises(ValueError):
        percentile([1.0], 101)


def test_summary_error_rate_and_throughput():
    m = Metrics(latencies_ms=[10, 20, 30], messages_ok=3, started_at=0.0, finished_at=1.5)
    m.record_error("response_timeout")
    s = m.summary(expected_messages=4)
    assert s["error_rate"] == 0.25
    assert s["throughput_msg_s"] == 2.0
    assert s["latency_ms"]["avg"] == 20.0
    assert s["errors"] == {"response_timeout": 1}
