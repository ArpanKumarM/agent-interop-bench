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
        )


settings = Settings.from_env()
