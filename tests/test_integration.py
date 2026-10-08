"""End-to-end tests against a real local echo server (random free port)."""
import asyncio

from wsload.config import LoadConfig, Thresholds
from wsload.reporter import evaluate_thresholds
from wsload.runner import run_load
from wsload.server import echo_server


def _run_against_server(delay_ms=0.0, **cfg_kwargs):
    async def scenario():
        async with echo_server(delay_ms=delay_ms) as uri:
            cfg = LoadConfig(uri=uri, **cfg_kwargs)
            metrics = await run_load(cfg)
            return cfg, metrics.summary(cfg.expected_messages)

    return asyncio.run(scenario())


def test_all_messages_round_trip():
    cfg, s = _run_against_server(connections=20, messages_per_connection=5)
    assert s["connections_ok"] == 20
    assert s["messages_ok"] == 100
    assert s["error_rate"] == 0
    assert s["latency_ms"]["p95"] > 0


def test_slow_server_breaches_latency_threshold():
    cfg, s = _run_against_server(
        delay_ms=50, connections=5, messages_per_connection=3,
        thresholds=Thresholds(max_p95_ms=20),
    )
    failures = evaluate_thresholds(s, cfg.thresholds)
    assert any("p95" in f for f in failures)


def test_response_timeout_is_recorded():
    cfg, s = _run_against_server(
        delay_ms=300, connections=3, messages_per_connection=2, response_timeout_s=0.1,
    )
    assert s["errors"].get("response_timeout") == 3
    assert s["error_rate"] == 1.0


def test_unreachable_server_is_reported_not_raised():
    cfg = LoadConfig(uri="ws://127.0.0.1:1", connections=3,
                     messages_per_connection=2, connect_timeout_s=2)
    s = asyncio.run(run_load(cfg)).summary(cfg.expected_messages)
    assert s["connections_failed"] == 3
    assert s["error_rate"] == 1.0
