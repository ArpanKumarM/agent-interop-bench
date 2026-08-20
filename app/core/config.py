"""Minimal environment-driven settings. No config framework needed for Phase 1."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    log_level: str
    api_host: str
    api_port: int
    benchmarks_path: str
    mock_server_command: str
    mock_server_args: list[str]
    # Bounded background execution for POST /runs (Phase 2B). Conservative
    # defaults for a local, single-process benchmark service: at most 2 runs
    # execute concurrently (each spawns its own mock-server subprocess), and
    # at most 10 more can be queued behind them before submissions are
    # rejected with 429 rather than accepted unboundedly.
    run_worker_count: int
    run_queue_maxsize: int

    def __post_init__(self) -> None:
        # asyncio.Queue(maxsize=0) means UNBOUNDED, not zero — so a value < 1
        # here would silently defeat the bounded-execution guarantee rather
        # than raise, if it went unchecked. Fail fast instead, at settings
        # load time, using the dataclass's own validation hook rather than a
        # separate config framework.
        if self.run_worker_count < 1:
            raise ValueError(f"RUN_WORKER_COUNT must be >= 1, got {self.run_worker_count}")
        if self.run_queue_maxsize < 1:
            raise ValueError(f"RUN_QUEUE_MAXSIZE must be >= 1, got {self.run_queue_maxsize}")

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            api_host=os.environ.get("API_HOST", "0.0.0.0"),
            api_port=int(os.environ.get("API_PORT", "8000")),
            benchmarks_path=os.environ.get("BENCHMARKS_PATH", "benchmarks/"),
            mock_server_command=os.environ.get("MOCK_SERVER_COMMAND", sys.executable),
            mock_server_args=os.environ.get(
                "MOCK_SERVER_ARGS", "-m mock_servers.github_mock"
            ).split(),
            run_worker_count=int(os.environ.get("RUN_WORKER_COUNT", "2")),
            run_queue_maxsize=int(os.environ.get("RUN_QUEUE_MAXSIZE", "10")),
        )


settings = Settings.from_env()
