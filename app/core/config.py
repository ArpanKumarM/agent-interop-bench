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
    # Real-model (Phase 2C) cost-safety controls. Disabled by default: a
    # deterministic run never inspects any of these, never constructs a
    # provider client, and never requires OPENAI_API_KEY. See
    # app/runner/openai_adapter.py and docs/scoring.md.
    enable_real_model_runs: bool
    real_model_max_cases: int
    real_model_timeout_seconds: float
    real_model_max_output_tokens: int
    # Real-model COMPOSED (Phase 4A.2) cost-safety controls -- deliberately a
    # SEPARATE flag/budget from the MCP ones above: enabling
    # ENABLE_REAL_MODEL_RUNS must never also enable composed live runs, and
    # vice versa. real_model_composed_max_decisions bounds the number of
    # provider *decisions* (one per host-agent turn, not one per case/trial —
    # a single trial can span several decisions), independent of any case's
    # own max_interaction_steps. See app/runner/real_host_adapter.py.
    enable_real_model_composed_runs: bool = False
    real_model_composed_max_decisions: int = 20

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
        if self.real_model_max_cases < 1:
            raise ValueError(f"REAL_MODEL_MAX_CASES must be >= 1, got {self.real_model_max_cases}")
        if self.real_model_timeout_seconds <= 0:
            raise ValueError(
                f"REAL_MODEL_TIMEOUT_SECONDS must be > 0, got {self.real_model_timeout_seconds}"
            )
        if self.real_model_max_output_tokens < 1:
            raise ValueError(
                "REAL_MODEL_MAX_OUTPUT_TOKENS must be >= 1, "
                f"got {self.real_model_max_output_tokens}"
            )
        if self.real_model_composed_max_decisions < 1:
            raise ValueError(
                "REAL_MODEL_COMPOSED_MAX_DECISIONS must be >= 1, "
                f"got {self.real_model_composed_max_decisions}"
            )

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
            enable_real_model_runs=os.environ.get("ENABLE_REAL_MODEL_RUNS", "false").lower()
            in ("1", "true", "yes"),
            real_model_max_cases=int(os.environ.get("REAL_MODEL_MAX_CASES", "3")),
            real_model_timeout_seconds=float(os.environ.get("REAL_MODEL_TIMEOUT_SECONDS", "30.0")),
            real_model_max_output_tokens=int(os.environ.get("REAL_MODEL_MAX_OUTPUT_TOKENS", "256")),
            enable_real_model_composed_runs=os.environ.get(
                "ENABLE_REAL_MODEL_COMPOSED_RUNS", "false"
            ).lower()
            in ("1", "true", "yes"),
            real_model_composed_max_decisions=int(
                os.environ.get("REAL_MODEL_COMPOSED_MAX_DECISIONS", "20")
            ),
        )


def real_model_api_key_configured() -> bool:
    """Whether OPENAI_API_KEY is present in the environment.

    Deliberately returns only a bool — the value is never read, logged, or
    stored anywhere else in this module or in Settings, so a key can never
    end up serialized into a report, a log line, or an API response.
    """
    return bool(os.environ.get("OPENAI_API_KEY"))


settings = Settings.from_env()
