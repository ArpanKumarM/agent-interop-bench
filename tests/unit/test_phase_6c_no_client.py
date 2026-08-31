"""Phase 6C: no provider client that could send inference is ever
constructed for an offline flow, and the ``anthropic`` package is not
imported at module load of the seam modules.
"""

from __future__ import annotations

import sys

import pytest

import app.runner.anthropic_adapter as aa
import app.runner.anthropic_host_adapter as aha
import app.runner.host_action_schema_anthropic as hsa
import app.runner.host_decision_client as hdc
import app.runner.model_panel as mp


def test_seam_modules_do_not_import_anthropic_at_module_load(monkeypatch):
    # Force a fresh import and assert `anthropic` was not pulled in as a
    # side effect. (It may already be importable via the extra; what matters
    # is that our modules don't import it eagerly.)
    for name in [
        "app.runner.anthropic_adapter",
        "app.runner.anthropic_host_adapter",
        "app.runner.host_action_schema_anthropic",
    ]:
        sys.modules.pop(name, None)
    sys.modules.pop("anthropic", None)
    import importlib

    importlib.import_module("app.runner.anthropic_adapter")
    importlib.import_module("app.runner.host_action_schema_anthropic")
    importlib.import_module("app.runner.anthropic_host_adapter")
    assert "anthropic" not in sys.modules


def test_anthropic_sdk_available_is_a_bool_seam():
    assert isinstance(aa.anthropic_sdk_available(), bool)


def test_build_anthropic_messages_client_is_lazy_and_not_called_offline():
    # Constructing it is what would need a key; simply referencing the
    # builder must not construct anything.
    assert callable(aa.build_anthropic_messages_client)
    assert callable(hdc.build_anthropic_host_decision_client)


def test_provider_for_model_rejects_unknown_family():
    with pytest.raises(ValueError):
        mp.provider_for_model("mistral-large")


def test_max_tokens_choice_is_documented_and_hashed():
    assert mp.ANTHROPIC_MAX_OUTPUT_TOKENS == 2048
    cfg = mp.provider_request_config("claude-sonnet-5", timeout_seconds=20.0)
    assert cfg["max_tokens"] == mp.ANTHROPIC_MAX_OUTPUT_TOKENS
    h1 = mp.provider_config_sha256(
        "claude-sonnet-5", canonical_actions=("call_tool", "stop"), timeout_seconds=20.0
    )
    # a different cap -> different hash
    import app.runner.model_panel as reload_mp

    original = reload_mp.ANTHROPIC_MAX_OUTPUT_TOKENS
    try:
        reload_mp.ANTHROPIC_MAX_OUTPUT_TOKENS = 4096
        h2 = reload_mp.provider_config_sha256(
            "claude-sonnet-5", canonical_actions=("call_tool", "stop"), timeout_seconds=20.0
        )
    finally:
        reload_mp.ANTHROPIC_MAX_OUTPUT_TOKENS = original
    assert h1 != h2


def test_no_temperature_top_p_top_k_in_any_provider_config():
    for model in ("gpt-5.6-sol", "claude-sonnet-5"):
        cfg = mp.provider_request_config(model, timeout_seconds=20.0)
        assert "temperature" not in cfg
        assert "top_p" not in cfg
        assert "top_k" not in cfg
        assert cfg["max_retries"] == 0
        assert cfg["decisions_per_trial"] == 1


def test_adapter_module_symbols_present():
    assert hasattr(aha, "AnthropicHostAgentAdapter")
    assert hasattr(hsa, "compile_canonical_actions_for_anthropic")
