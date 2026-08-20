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
