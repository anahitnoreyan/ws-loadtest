"""Scenario configuration: model, YAML loading and validation."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Thresholds:
    """Pass/fail criteria. None means 'not checked'."""

    max_p95_ms: float | None = None
    max_error_rate: float | None = None  # 0.01 = 1 %
    min_throughput: float | None = None  # successful messages per second


@dataclass
class LoadConfig:
    name: str = "default"
    uri: str = "ws://127.0.0.1:8765"
    connections: int = 10
    messages_per_connection: int = 10
    message_size: int = 64
    ramp_up_s: float = 0.0
    think_time_s: float = 0.0
    connect_timeout_s: float = 10.0
    response_timeout_s: float = 5.0
    thresholds: Thresholds = field(default_factory=Thresholds)

    @property
    def expected_messages(self) -> int:
        return self.connections * self.messages_per_connection

    def validate(self) -> None:
        if not self.uri.startswith(("ws://", "wss://")):
            raise ValueError("uri must start with ws:// or wss://")
        for name in ("connections", "messages_per_connection"):
            if getattr(self, name) < 1:
                raise ValueError(f"{name} must be >= 1")
        for name in ("message_size", "ramp_up_s", "think_time_s"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be >= 0")
        for name in ("connect_timeout_s", "response_timeout_s"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be > 0")


def load_config(path: str | Path) -> LoadConfig:
    """Load and validate a YAML scenario file. Raises ValueError if invalid."""
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {path}: {exc}") from exc

    try:
        thresholds = Thresholds(**(data.pop("thresholds", None) or {}))
        cfg = LoadConfig(**data, thresholds=thresholds)
    except TypeError as exc:  # unknown or misspelled keys
        raise ValueError(f"Invalid config {path}: {exc}") from exc

    cfg.validate()
    return cfg
