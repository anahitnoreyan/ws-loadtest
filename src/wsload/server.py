"""Local echo server used as a safe test target."""
from __future__ import annotations

import asyncio
import contextlib

import websockets
from websockets.exceptions import ConnectionClosed


def make_handler(delay_ms: float = 0.0):
    async def echo(ws):
        try:
            async for message in ws:
                if delay_ms:
                    await asyncio.sleep(delay_ms / 1000)  # simulate a slow backend
                await ws.send(message)
        except ConnectionClosed:
            pass

    return echo


@contextlib.asynccontextmanager
async def echo_server(host: str = "127.0.0.1", port: int = 0, delay_ms: float = 0.0):
    """Start an echo server and yield its URI. port=0 picks a free port."""
    async with websockets.serve(make_handler(delay_ms), host, port, max_size=None) as server:
        actual_port = server.sockets[0].getsockname()[1]
        yield f"ws://{host}:{actual_port}"


async def serve(host: str, port: int, delay_ms: float) -> None:
    async with echo_server(host, port, delay_ms) as uri:
        print(f"Echo server listening on {uri} (delay {delay_ms} ms). Press Ctrl+C to stop.")
        await asyncio.Future()  # run forever
