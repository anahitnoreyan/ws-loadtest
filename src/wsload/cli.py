"""Command-line interface.

Exit codes: 0 = passed, 1 = thresholds failed, 2 = configuration error.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import replace

from .config import LoadConfig, load_config
from .reporter import evaluate_thresholds, print_report, save_reports
from .runner import run_load
from .server import serve

OVERRIDES = ("uri", "connections", "messages_per_connection", "message_size", "ramp_up_s")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wsload", description="Asyncio WebSocket load-testing tool")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run a load test")
    run.add_argument("--config", help="Path to a YAML scenario file")
    run.add_argument("--uri", help="Target, e.g. ws://127.0.0.1:8765")
    run.add_argument("-c", "--connections", type=int, help="Concurrent connections")
    run.add_argument("-m", "--messages", type=int, dest="messages_per_connection",
                     help="Messages per connection")
    run.add_argument("--message-size", type=int, help="Payload padding in bytes")
    run.add_argument("--ramp-up", type=float, dest="ramp_up_s", help="Ramp-up time in seconds")
    run.add_argument("--out", default="results", help="Report directory (default: results)")
    run.add_argument("--no-save", action="store_true", help="Do not write report files")

    srv = sub.add_parser("server", help="Start the local echo server")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8765)
    srv.add_argument("--delay-ms", type=float, default=0.0, help="Artificial response delay")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "server":
        try:
            asyncio.run(serve(args.host, args.port, args.delay_ms))
        except KeyboardInterrupt:
            print("\nServer stopped.")
        return 0

    try:
        cfg = load_config(args.config) if args.config else LoadConfig()
        overrides = {k: getattr(args, k) for k in OVERRIDES if getattr(args, k) is not None}
        cfg = replace(cfg, **overrides)
        cfg.validate()
    except (OSError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    print(f"Running '{cfg.name}': {cfg.connections} connections x "
          f"{cfg.messages_per_connection} messages -> {cfg.uri}")

    metrics = asyncio.run(run_load(cfg))
    summary = metrics.summary(cfg.expected_messages)
    failures = evaluate_thresholds(summary, cfg.thresholds)
    print_report(cfg, summary, failures)

    if not args.no_save:
        path = save_reports(cfg, summary, failures, args.out)
        print(f"Report saved: {path}")

    return 1 if failures else 0
