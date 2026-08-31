"""Phase 6C: the frozen four-model panel and the per-provider inference
interface each model runs under.

The panel is `blocked_schedule.PHASE_6B_MODEL_PANEL` (single source of
truth): the three OpenAI models `gpt-5.6-{sol,terra,luna}` followed by the
external-family robustness model `claude-sonnet-5`. Claude's schedule is
the deterministic continuation of the SAME `random.Random(
PHASE_6B_SCHEDULE_SEED)` stream after `luna`, so the three existing
per-model schedules are byte-identical.

This module holds NO Anthropic- or OpenAI-specific decision logic -- only
the request-configuration facts each provider's client is built with, and
their canonical hash (folded into execution fingerprint v2). Nothing here
constructs a client or makes a call.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.runner.blocked_schedule import PHASE_6B_MODEL_PANEL
from app.runner.host_action_schema_anthropic import anthropic_wire_tool_schema_sha256
from app.runner.host_action_schema_openai import canonical_action_schema_sha256

__all__ = [
    "PHASE_6C_MODEL_PANEL",
    "ANTHROPIC_ROBUSTNESS_MODEL",
    "OPENAI_MODELS",
    "ANTHROPIC_MAX_OUTPUT_TOKENS",
    "OPENAI_MAX_OUTPUT_TOKENS",
    "LOW_EFFORT",
    "provider_for_model",
    "provider_api_surface_for_model",
    "provider_request_config",
    "provider_config_sha256",
]

PHASE_6C_MODEL_PANEL: tuple[str, ...] = PHASE_6B_MODEL_PANEL
ANTHROPIC_ROBUSTNESS_MODEL = "claude-sonnet-5"
OPENAI_MODELS: tuple[str, ...] = tuple(
    m for m in PHASE_6C_MODEL_PANEL if m != ANTHROPIC_ROBUSTNESS_MODEL
)

# Frozen (Phase 4A.3c / 6C): both providers run in their OWN low-effort
# mode. These are NOT claimed to be numerically equivalent -- only that
# each is that provider's supported low-effort configuration.
LOW_EFFORT = "low"

# OpenAI Responses `max_output_tokens` -- unchanged from Phase 4B/6B.
OPENAI_MAX_OUTPUT_TOKENS = 512

# Anthropic Messages `max_tokens`. The OpenAI 512 cap does NOT map cleanly:
# on Anthropic `max_tokens` bounds thinking tokens + visible output
# together, and adaptive thinking may spend some budget before the single
# `tool_use` block. One low-effort decision here is tiny -- a `call_tool`
# with a <=2-key argument object, a `relay_to_remote` with a short string,
# or a zero-argument `stop`. 2048 is the smallest round cap that cannot
# reasonably truncate that decision even with a low-effort adaptive-thinking
# preamble, while staying far below anything that would let a run wander.
# This value is part of the provider-config hash (change it -> fingerprint
# changes).
ANTHROPIC_MAX_OUTPUT_TOKENS = 2048

# Anthropic thinking configuration. `adaptive` = the model chooses how much
# to think (no fixed budget) and is the low-effort-friendly mode in the
# installed SDK (anthropic>=1.2.0, which also exposes
# `output_config.effort`). `display: "omitted"` -> the API returns NO
# thinking text, only an opaque signature; we never read, store, or replay
# any thinking content regardless.
ANTHROPIC_THINKING = {"type": "adaptive", "display": "omitted"}
# The model MUST emit exactly one tool call, and it may only be one of the
# decision tools we pass (`call_tool`+`stop` for RQ2, `relay_to_remote`+
# `stop` for RQ1). `stop` is itself one of those tools.
ANTHROPIC_TOOL_CHOICE = {"type": "any", "disable_parallel_tool_use": True}

_OPENAI_API_SURFACE = "openai.responses"
_ANTHROPIC_API_SURFACE = "anthropic.messages"


def provider_for_model(model: str) -> str:
    """``anthropic`` for the robustness model (or any ``claude-*`` id),
    ``openai`` for the three core models (or any ``gpt-*`` id). Raises for
    anything else."""
    if model == ANTHROPIC_ROBUSTNESS_MODEL or model.startswith("claude-"):
        return "anthropic"
    if model in OPENAI_MODELS or model.startswith("gpt-"):
        return "openai"
    raise ValueError(
        f"model {model!r} maps to no known provider (Phase 6C panel: {list(PHASE_6C_MODEL_PANEL)})"
    )


def provider_api_surface_for_model(model: str) -> str:
    return (
        _ANTHROPIC_API_SURFACE if provider_for_model(model) == "anthropic" else _OPENAI_API_SURFACE
    )


def provider_request_config(model: str, *, timeout_seconds: float) -> dict[str, Any]:
    """The exact, credential-free provider request configuration sent on
    EVERY decision call for ``model`` (recorded in provenance and hashed).
    One decision per trial, zero retries, no temperature/top_p/top_k."""
    provider = provider_for_model(model)
    if provider == "anthropic":
        return {
            "provider": "anthropic",
            "api_surface": _ANTHROPIC_API_SURFACE,
            "model": model,
            "effort_mode": {"output_config": {"effort": LOW_EFFORT}},
            "thinking": dict(ANTHROPIC_THINKING),
            "tool_choice": dict(ANTHROPIC_TOOL_CHOICE),
            "max_tokens": ANTHROPIC_MAX_OUTPUT_TOKENS,
            "timeout_seconds": timeout_seconds,
            "max_retries": 0,
            "decisions_per_trial": 1,
            "sampling_overrides": "none (no temperature/top_p/top_k set)",
        }
    return {
        "provider": "openai",
        "api_surface": _OPENAI_API_SURFACE,
        "model": model,
        "effort_mode": {"reasoning": {"effort": LOW_EFFORT}},
        "tool_choice": "required",
        "parallel_tool_calls": False,
        "max_output_tokens": OPENAI_MAX_OUTPUT_TOKENS,
        "timeout_seconds": timeout_seconds,
        "max_retries": 0,
        "decisions_per_trial": 1,
        "sampling_overrides": "none (no temperature/top_p/top_k set)",
    }


def _wire_tool_schema_sha256(model: str, canonical_actions: tuple[str, ...]) -> str:
    if provider_for_model(model) == "anthropic":
        return anthropic_wire_tool_schema_sha256(canonical_actions)
    return canonical_action_schema_sha256(canonical_actions)


def provider_config_sha256(
    model: str,
    *,
    canonical_actions: tuple[str, ...],
    timeout_seconds: float,
) -> str:
    """SHA-256 over the exact provider inference interface: provider id,
    model id, API mode, canonical request parameters, and the PROVIDER wire
    tool-schema hash. Folded into execution fingerprint v2 (Phase 6C).

    Changing the Anthropic effort mode, model id, max_tokens, tool_choice
    mode, or the compiled wire schema all change this hash."""
    payload = {
        "request_config": provider_request_config(model, timeout_seconds=timeout_seconds),
        "wire_tool_schema_sha256": _wire_tool_schema_sha256(model, canonical_actions),
        "canonical_actions": list(canonical_actions),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
