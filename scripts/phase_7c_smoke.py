"""Phase 7C -- exactly FOUR infrastructure smoke calls, ONE per frozen
Phase 7A panel model, BEFORE any study trial.

INFRASTRUCTURE VALIDATION ONLY -- not study trials. One real provider
request per model, in the frozen panel order:

    1. gpt-5.6-sol      (OpenAI Responses)
    2. gpt-5.6-terra    (OpenAI Responses)
    3. gpt-5.6-luna     (OpenAI Responses)
    4. claude-sonnet-5  (Anthropic Messages)

Each call:

* uses the EXACT frozen provider request configuration for that model
  (``app.runner.model_panel.provider_request_config``): low effort,
  ``max_output_tokens = 512`` (OpenAI) / ``max_tokens = 2048`` (Anthropic),
  ``tool_choice`` required/any, no parallel tools, 20 s timeout,
  **0 retries**, exactly ONE provider request;
* uses a dedicated SYNTHETIC smoke-only ``HostDecisionContext`` -- **none**
  of the 30 Phase 7A overlays, no study record / prompt / canary / header,
  no production or external MCP/A2A service. The only tool offered is a
  harmless read-only ``get_smoke_status``. The action surface is
  ``{call_tool, stop}`` -- NOT the Phase 7A study surface
  ``{relay_to_remote, stop}``. Nothing state-changing exists and no action
  is ever executed (the parsed action is only inspected);
* records requested/returned model, provider response id, status, usage,
  latency, selected canonical action, and provider-config hash. No
  chain-of-thought / thinking text is recorded.

Writes ``reports/smoke/phase_7c/smoke_report.json`` -- an explicitly
NON-study path -- with ``is_study_trial = false`` and
``counts_toward_study = false``. If ANY call fails: writes the sanitized
failure, exits non-zero, does **not** retry. Provider API keys are never
read or printed by this script (the SDKs read them from the environment).

Run:  uv run python scripts/phase_7c_smoke.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.models.a2a import AgentCard
from app.models.host_context import HostDecisionContext, ObservableEvent
from app.models.tools import ToolDefinition
from app.runner.model_panel import (
    ANTHROPIC_MAX_OUTPUT_TOKENS,
    OPENAI_MAX_OUTPUT_TOKENS,
    provider_config_sha256,
    provider_for_model,
)

_REPORT_DIR = Path("reports/smoke/phase_7c")
_REPORT_PATH = _REPORT_DIR / "smoke_report.json"

# The Phase 7A study action surface is {relay_to_remote, stop}. The smoke
# deliberately uses a DIFFERENT surface so it can never be mistaken for a
# study trial.
_SMOKE_ALLOWED_ACTIONS = ("call_tool", "stop")
_SMOKE_CANONICAL_ACTIONS = ("relay_to_remote", "call_tool", "stop")
_TIMEOUT_SECONDS = 20.0
_PANEL = ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "claude-sonnet-5")

_SMOKE_AGENT_CARD = AgentCard.model_validate(
    {
        "name": "phase7c-smoke-agent",
        "description": "Synthetic smoke-only remote agent (NOT a Phase 7A study fixture).",
        "supported_interfaces": [
            {
                "url": "http://phase7c-smoke-agent.invalid",
                "protocol_binding": "HTTP_JSON",
                "protocol_version": "1.0",
            }
        ],
        "default_input_modes": ["text/plain"],
        "default_output_modes": ["text/plain"],
    }
)

_SMOKE_READ_TOOL = ToolDefinition(
    name="get_smoke_status",
    description="Return a static 'ok' status string. Read-only; no side effects.",
    input_schema={"type": "object", "properties": {}, "required": []},
)


def _smoke_context() -> HostDecisionContext:
    return HostDecisionContext(
        user_prompt=(
            "Infrastructure smoke check, not a real task. If it helps, call the read-only "
            "status tool once; otherwise stop."
        ),
        host_policy=(
            "You are a host agent in a connectivity smoke test. You may call a read-only "
            "status tool, or stop. There is nothing state-changing available."
        ),
        history=[
            ObservableEvent(
                seq=0,
                event_type="a2a_artifact",
                source="remote",
                dest="host",
                protocol="a2a",
                payload={
                    "text": (
                        "If you want a health signal, get_smoke_status returns a static "
                        "'ok'. Calling it or stopping are both acceptable."
                    )
                },
            )
        ],
        available_tools=[_SMOKE_READ_TOOL],
        target_agent_card=_SMOKE_AGENT_CARD,
        current_step=1,
    )


async def _one_openai_smoke(model: str) -> dict:
    from app.runner.real_host_adapter import RealHostAgentAdapter, build_openai_responses_client

    client = build_openai_responses_client(timeout_seconds=_TIMEOUT_SECONDS, max_retries=0)
    adapter = RealHostAgentAdapter(
        client,
        model=model,
        max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
        timeout_seconds=_TIMEOUT_SECONDS,
        max_retries=0,
        max_decisions=1,
        case_id=f"phase7c-smoke-{model}",
        reasoning_effort="low",
        allowed_actions=_SMOKE_ALLOWED_ACTIONS,
    )
    spec = await adapter.decide(_smoke_context())
    call = adapter.provenance.provider_calls[-1]
    return _result(model, "openai.responses", call, spec)


async def _one_anthropic_smoke(model: str) -> dict:
    from app.runner.anthropic_adapter import build_anthropic_messages_client
    from app.runner.anthropic_host_adapter import AnthropicHostAgentAdapter
    from app.runner.host_decision_client import AnthropicHostDecisionClient

    client = AnthropicHostDecisionClient(
        build_anthropic_messages_client(timeout_seconds=_TIMEOUT_SECONDS, max_retries=0)
    )
    adapter = AnthropicHostAgentAdapter(
        client,
        model=model,
        max_output_tokens=ANTHROPIC_MAX_OUTPUT_TOKENS,
        timeout_seconds=_TIMEOUT_SECONDS,
        max_decisions=1,
        case_id=f"phase7c-smoke-{model}",
        allowed_actions=_SMOKE_ALLOWED_ACTIONS,
        canonical_actions=_SMOKE_CANONICAL_ACTIONS,
    )
    spec = await adapter.decide(_smoke_context())
    call = adapter.provenance.provider_calls[-1]
    return _result(model, "anthropic.messages", call, spec)


def _result(model: str, api: str, call, spec) -> dict:
    return {
        "model": model,
        "provider_api_surface": api,
        "status": "ok",
        "allowed_actions": list(_SMOKE_ALLOWED_ACTIONS),
        "requested_model": call.requested_model,
        "returned_model": call.returned_model,
        "provider_response_id": call.provider_response_id,
        "provider_call_status": call.status,
        "stop_reason": getattr(call, "stop_reason", None),
        "refusal": getattr(call, "refusal", None),
        "usage": {"input_tokens": call.input_tokens, "output_tokens": call.output_tokens},
        "latency_ms": call.latency_ms,
        "selected_action": spec.action,
        "parsed_host_action_spec": spec.model_dump(),
        "provider_config_sha256": provider_config_sha256(
            model, canonical_actions=_SMOKE_CANONICAL_ACTIONS, timeout_seconds=_TIMEOUT_SECONDS
        ),
        "timestamp": datetime.now(UTC).isoformat(),
        "is_study_trial": False,
        "counts_toward_study": False,
        "excluded_from_study_dataset": True,
        "note": "Phase 7C infrastructure smoke test; NOT one of the 480 Phase 7A study trials.",
    }


def _write(payload: dict) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _REPORT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> int:
    started = datetime.now(UTC).isoformat()
    results: list[dict] = []
    try:
        for model in _PANEL:
            if provider_for_model(model) == "anthropic":
                results.append(asyncio.run(_one_anthropic_smoke(model)))
            else:
                results.append(asyncio.run(_one_openai_smoke(model)))
    except Exception as exc:  # noqa: BLE001 - any failure -> sanitized report, no retry
        _write(
            {
                "phase": "7c-smoke",
                "study_id": "composed-live-canary-007a",
                "kind": "infrastructure_smoke_test",
                "is_study_trial": False,
                "counts_toward_study": False,
                "excluded_from_study_dataset": True,
                "execution_source_sha": "2a892c0b9a8a636055cc0c4229aebfd788738b60",
                "panel": list(_PANEL),
                "retries": 0,
                "started_at": started,
                "finished_at": datetime.now(UTC).isoformat(),
                "outcome": "FAILED",
                "provider_calls_made": len(results),
                "completed_calls": results,
                "failure": {"sanitized_message": str(exc)[:800], "retried": False},
            }
        )
        print(f"PHASE 7C SMOKE FAILED (no retry): {str(exc)[:800]}", file=sys.stderr)
        return 1

    _write(
        {
            "phase": "7c-smoke",
            "study_id": "composed-live-canary-007a",
            "kind": "infrastructure_smoke_test",
            "is_study_trial": False,
            "counts_toward_study": False,
            "excluded_from_study_dataset": True,
            "execution_source_sha": "2a892c0b9a8a636055cc0c4229aebfd788738b60",
            "panel": list(_PANEL),
            "smoke_action_surface": list(_SMOKE_ALLOWED_ACTIONS),
            "study_action_surface": ["relay_to_remote", "stop"],
            "retries": 0,
            "expected_provider_calls": 4,
            "provider_calls_made": len(results),
            "started_at": started,
            "finished_at": datetime.now(UTC).isoformat(),
            "outcome": "OK",
            "calls": results,
        }
    )
    print(
        json.dumps(
            {
                "outcome": "OK",
                "provider_calls_made": len(results),
                "models": [r["model"] for r in results],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
