"""Threshold evaluation and report output (console, JSON, CSV history)."""
from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .config import LoadConfig, Thresholds


def evaluate_thresholds(summary: dict, t: Thresholds) -> list[str]:
    """Return a list of human-readable failures. Empty list = passed."""
    failures: list[str] = []

    if summary["messages_ok"] == 0:
        failures.append("No message completed successfully")

    p95 = summary["latency_ms"]["p95"]
    if t.max_p95_ms is not None and p95 > t.max_p95_ms:
        failures.append(f"p95 latency {p95} ms > {t.max_p95_ms} ms")

    rate = summary["error_rate"]
    if t.max_error_rate is not None and rate > t.max_error_rate:
        failures.append(f"error rate {rate:.2%} > {t.max_error_rate:.2%}")

    tput = summary["throughput_msg_s"]
    if t.min_throughput is not None and tput < t.min_throughput:
        failures.append(f"throughput {tput} msg/s < {t.min_throughput} msg/s")

    return failures


def print_report(cfg: LoadConfig, summary: dict, failures: list[str]) -> None:
    lat, ct = summary["latency_ms"], summary["connect_time_ms"]
    errors = ", ".join(f"{k}={v}" for k, v in summary["errors"].items()) or "none"

    print(f"\n=== wsload report: {cfg.name} ===")
    print(f"Target            : {cfg.uri}")
    print(f"Connections       : {summary['connections_ok']} ok / "
          f"{summary['connections_failed']} failed")
    print(f"Messages          : {summary['messages_ok']} ok / "
          f"{summary['messages_planned']} planned")
    print(f"Duration          : {summary['duration_s']} s")
    print(f"Throughput        : {summary['throughput_msg_s']} msg/s")
    print(f"Error rate        : {summary['error_rate']:.2%}")
    print(f"Latency (ms)      : min {lat['min']} | avg {lat['avg']} | p50 {lat['p50']} | "
          f"p90 {lat['p90']} | p95 {lat['p95']} | p99 {lat['p99']} | max {lat['max']}")
    print(f"Connect time (ms) : avg {ct['avg']} | p95 {ct['p95']}")
    print(f"Errors            : {errors}")

    if failures:
        print("Result            : FAILED")
        for failure in failures:
            print(f"  - {failure}")
    else:
        print("Result            : PASSED")


def save_reports(cfg: LoadConfig, summary: dict, failures: list[str],
                 out_dir: str | Path = "results") -> Path:
    """Write a detailed JSON report and append one row to history.csv."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    report = {
        "scenario": cfg.name,
        "timestamp": stamp,
        "config": asdict(cfg),
        "summary": summary,
        "passed": not failures,
        "threshold_failures": failures,
    }
    json_path = out / f"{cfg.name}-{stamp}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    row = {
        "timestamp": stamp,
        "scenario": cfg.name,
        "connections": cfg.connections,
        "messages_per_connection": cfg.messages_per_connection,
        "duration_s": summary["duration_s"],
        "messages_ok": summary["messages_ok"],
        "error_rate": summary["error_rate"],
        "throughput_msg_s": summary["throughput_msg_s"],
        "p50_ms": summary["latency_ms"]["p50"],
        "p95_ms": summary["latency_ms"]["p95"],
        "p99_ms": summary["latency_ms"]["p99"],
        "passed": not failures,
    }
    history = out / "history.csv"
    is_new = not history.exists()
    with history.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        if is_new:
            writer.writeheader()
        writer.writerow(row)

    return json_path
