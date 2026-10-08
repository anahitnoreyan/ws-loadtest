"""A virtual user: one WebSocket connection that sends N messages."""
from __future__ import annotations

import asyncio
import json
import time

import websockets

from .config import LoadConfig
from .metrics import Metrics


def _reply_id(raw) -> str | None:
    try:
        return json.loads(raw).get("id")
    except (ValueError, TypeError, AttributeError):
        return None


async def virtual_user(user_id: int, cfg: LoadConfig, metrics: Metrics) -> None:
    # Ramp-up: spread connection start times evenly across ramp_up_s.
    if cfg.ramp_up_s > 0:
        await asyncio.sleep(cfg.ramp_up_s * user_id / cfg.connections)

    padding = "x" * cfg.message_size
    connected = False
    t0 = time.perf_counter()

    try:
        async with websockets.connect(
            cfg.uri, open_timeout=cfg.connect_timeout_s, max_size=None
        ) as ws:
            connected = True
            metrics.connections_ok += 1
            metrics.connect_times_ms.append((time.perf_counter() - t0) * 1000)

            for seq in range(cfg.messages_per_connection):
                msg_id = f"{user_id}-{seq}"
                payload = json.dumps({"id": msg_id, "data": padding})

                start = time.perf_counter()
                await ws.send(payload)
                metrics.messages_sent += 1

                try:
                    reply = await asyncio.wait_for(ws.recv(), cfg.response_timeout_s)
                except asyncio.TimeoutError:
                    # A late reply would be read by the next recv() and break
                    # request/response correlation, so this user stops here.
                    metrics.record_error("response_timeout")
                    return

                latency_ms = (time.perf_counter() - start) * 1000

                # Validate the response, not just its arrival.
                if _reply_id(reply) == msg_id:
                    metrics.messages_ok += 1
                    metrics.latencies_ms.append(latency_ms)
                else:
                    metrics.record_error("payload_mismatch")

                if cfg.think_time_s:
                    await asyncio.sleep(cfg.think_time_s)

    except Exception as exc:  # noqa: BLE001 - one failing user must not stop the test
        if not connected:
            metrics.connections_failed += 1
        phase = "runtime" if connected else "connect"
        metrics.record_error(f"{phase}:{type(exc).__name__}")
