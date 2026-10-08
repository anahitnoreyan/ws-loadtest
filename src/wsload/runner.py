"""Runs all virtual users concurrently on one event loop."""
from __future__ import annotations

import asyncio
import time

from .client import virtual_user
from .config import LoadConfig
from .metrics import Metrics


async def run_load(cfg: LoadConfig) -> Metrics:
    metrics = Metrics()
    metrics.started_at = time.perf_counter()
    await asyncio.gather(
        *(virtual_user(i, cfg, metrics) for i in range(cfg.connections))
    )
    metrics.finished_at = time.perf_counter()
    return metrics
