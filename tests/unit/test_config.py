"""Settings validation: RUN_WORKER_COUNT/RUN_QUEUE_MAXSIZE must never be able
to undermine the bounded-execution guarantee. In particular,
asyncio.Queue(maxsize=0) means UNBOUNDED, not zero, so 0 (and negative
values) must be rejected, not silently accepted.
"""

from __future__ import annotations

import pytest

from app.core.config import Settings


def _settings(**overrides) -> Settings:
    defaults = dict(
        log_level="INFO",
        api_host="0.0.0.0",
        api_port=8000,
        benchmarks_path="benchmarks/",
        mock_server_command="python",
        mock_server_args=[],
        run_worker_count=2,
        run_queue_maxsize=10,
        enable_real_model_runs=False,
        real_model_max_cases=3,
        real_model_timeout_seconds=30.0,
        real_model_max_output_tokens=256,
    )
    defaults.update(overrides)
    return Settings(**defaults)


def test_valid_settings_construct_fine():
    settings = _settings()
    assert settings.run_worker_count == 2
    assert settings.run_queue_maxsize == 10


@pytest.mark.parametrize("value", [0, -1])
def test_zero_or_negative_worker_count_rejected(value):
    with pytest.raises(ValueError, match="RUN_WORKER_COUNT"):
        _settings(run_worker_count=value)


@pytest.mark.parametrize("value", [0, -1])
def test_zero_or_negative_queue_maxsize_rejected(value):
    with pytest.raises(ValueError, match="RUN_QUEUE_MAXSIZE"):
        _settings(run_queue_maxsize=value)


def test_enable_real_model_runs_defaults_false_and_is_a_plain_bool():
    settings = _settings()
    assert settings.enable_real_model_runs is False


@pytest.mark.parametrize("value", [0, -1])
def test_zero_or_negative_real_model_max_cases_rejected(value):
    with pytest.raises(ValueError, match="REAL_MODEL_MAX_CASES"):
        _settings(real_model_max_cases=value)


@pytest.mark.parametrize("value", [0, -1.0])
def test_non_positive_real_model_timeout_rejected(value):
    with pytest.raises(ValueError, match="REAL_MODEL_TIMEOUT_SECONDS"):
        _settings(real_model_timeout_seconds=value)


@pytest.mark.parametrize("value", [0, -1])
def test_zero_or_negative_real_model_max_output_tokens_rejected(value):
    with pytest.raises(ValueError, match="REAL_MODEL_MAX_OUTPUT_TOKENS"):
        _settings(real_model_max_output_tokens=value)


def test_from_env_defaults_disable_real_model_runs(monkeypatch):
    for key in (
        "ENABLE_REAL_MODEL_RUNS",
        "REAL_MODEL_MAX_CASES",
        "REAL_MODEL_TIMEOUT_SECONDS",
        "REAL_MODEL_MAX_OUTPUT_TOKENS",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)

    settings = Settings.from_env()
    assert settings.enable_real_model_runs is False
    assert settings.real_model_max_cases == 3


def test_enable_real_model_composed_runs_defaults_false():
    settings = _settings()
    assert settings.enable_real_model_composed_runs is False
    assert settings.real_model_composed_max_decisions == 20


@pytest.mark.parametrize("value", [0, -1])
def test_zero_or_negative_real_model_composed_max_decisions_rejected(value):
    with pytest.raises(ValueError, match="REAL_MODEL_COMPOSED_MAX_DECISIONS"):
        _settings(real_model_composed_max_decisions=value)


def test_enabling_mcp_real_model_runs_does_not_enable_composed_runs(monkeypatch):
    """A separate flag, per Phase 4A.2: ENABLE_REAL_MODEL_RUNS must never
    also enable composed live runs."""
    monkeypatch.setenv("ENABLE_REAL_MODEL_RUNS", "true")
    monkeypatch.delenv("ENABLE_REAL_MODEL_COMPOSED_RUNS", raising=False)

    settings = Settings.from_env()
    assert settings.enable_real_model_runs is True
    assert settings.enable_real_model_composed_runs is False


def test_from_env_defaults_disable_real_model_composed_runs(monkeypatch):
    for key in ("ENABLE_REAL_MODEL_COMPOSED_RUNS", "REAL_MODEL_COMPOSED_MAX_DECISIONS"):
        monkeypatch.delenv(key, raising=False)

    settings = Settings.from_env()
    assert settings.enable_real_model_composed_runs is False
    assert settings.real_model_composed_max_decisions == 20
