from wsload.config import Thresholds
from wsload.reporter import evaluate_thresholds


def _summary(p95=10.0, error_rate=0.0, throughput=100.0, ok=10):
    return {
        "messages_ok": ok,
        "error_rate": error_rate,
        "throughput_msg_s": throughput,
        "latency_ms": {"p95": p95},
    }


def test_all_thresholds_pass():
    t = Thresholds(max_p95_ms=50, max_error_rate=0.01, min_throughput=50)
    assert evaluate_thresholds(_summary(), t) == []


def test_each_threshold_can_fail():
    t = Thresholds(max_p95_ms=5, max_error_rate=0.0, min_throughput=500)
    failures = evaluate_thresholds(_summary(error_rate=0.1), t)
    assert len(failures) == 3


def test_zero_successful_messages_always_fails():
    assert evaluate_thresholds(_summary(ok=0), Thresholds())
