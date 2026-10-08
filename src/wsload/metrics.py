"""Metric collection and aggregation."""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile. Returns 0.0 for an empty list."""
    if not 0 <= pct <= 100:
        raise ValueError("pct must be between 0 and 100")
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def _r(value: float) -> float:
    return round(value, 2)


@dataclass
class Metrics:
    """Raw measurements shared by all virtual users.

    No locks needed: asyncio runs on a single thread, and every update
    is a single statement with no `await` in between.
    """

    latencies_ms: list[float] = field(default_factory=list)
    connect_times_ms: list[float] = field(default_factory=list)
    errors: Counter = field(default_factory=Counter)
    messages_sent: int = 0
    messages_ok: int = 0
    connections_ok: int = 0
    connections_failed: int = 0
    started_at: float = 0.0
    finished_at: float = 0.0

    def record_error(self, kind: str) -> None:
        self.errors[kind] += 1

    @property
    def duration_s(self) -> float:
        return max(self.finished_at - self.started_at, 0.0)

    def summary(self, expected_messages: int) -> dict:
        lat = self.latencies_ms
        duration = self.duration_s
        failed = max(expected_messages - self.messages_ok, 0)
        return {
            "duration_s": round(duration, 3),
            "connections_ok": self.connections_ok,
            "connections_failed": self.connections_failed,
            "messages_planned": expected_messages,
            "messages_sent": self.messages_sent,
            "messages_ok": self.messages_ok,
            # Share of planned messages that did NOT complete successfully.
            "error_rate": round(failed / expected_messages, 4) if expected_messages else 0.0,
            "throughput_msg_s": _r(self.messages_ok / duration) if duration else 0.0,
            "latency_ms": {
                "min": _r(min(lat)) if lat else 0.0,
                "avg": _r(sum(lat) / len(lat)) if lat else 0.0,
                "p50": _r(percentile(lat, 50)),
                "p90": _r(percentile(lat, 90)),
                "p95": _r(percentile(lat, 95)),
                "p99": _r(percentile(lat, 99)),
                "max": _r(max(lat)) if lat else 0.0,
            },
            "connect_time_ms": {
                "avg": _r(sum(self.connect_times_ms) / len(self.connect_times_ms))
                if self.connect_times_ms
                else 0.0,
                "p95": _r(percentile(self.connect_times_ms, 95)),
            },
            "errors": dict(self.errors),
        }
