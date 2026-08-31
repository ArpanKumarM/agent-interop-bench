"""Phase 6D.0 -- exactly THREE real OpenAI Responses API smoke calls.

Infrastructure validation, NOT study trials. One call per OpenAI panel
model (``gpt-5.6-sol``, ``gpt-5.6-terra``, ``gpt-5.6-luna``), each under the
EXACT provider interface the confirmatory study uses:

* OpenAI Responses API, ``reasoning.effort = "low"``,
  ``max_output_tokens = 512``, ``tool_choice = "required"``,
  ``parallel_tool_calls = False``, strict decision-tool schema, **0
  retries**, exactly ONE provider request per model;
* a dedicated SYNTHETIC smoke-only context -- **none** of the 40 frozen
  study overlays, no production/external MCP or A2A service, no
  state-changing action ever executed (the parsed action is inspected, not
  run);
* writes a report under ``reports/smoke/phase_6d_openai/`` -- an explicitly
  NON-study path -- recording requested/returned model, provider response
  id, stop/status reason, usage, latency, selected canonical action, the
  parsed canonical ``HostActionSpec``, the provider-config hash, and
  ``counts_toward_640_study = false``. **No chain-of-thought is recorded.**

If ANY call fails: the script writes the sanitized failure, exits non-zero,
and does **not** retry. ``OPENAI_API_KEY`` is never read or printed by this
script (the SDK reads it from the environment itself).

Run:  uv run python scripts/phase_6d_openai_smoke.py
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
from app.runner.model_panel import OPENAI_MAX_OUTPUT_TOKENS, provider_config_sha256

_REPORT_DIR = Path("reports/smoke/phase_6d_openai")
_REPORT_PATH = _REPORT_DIR / "smoke_report.json"
_CANONICAL_ACTIONS = ("relay_to_remote", "call_tool", "stop")
_SMOKE_ALLOWED_ACTIONS = ("call_tool", "stop")
_TIMEOUT_SECONDS = 20.0
_OPENAI_MODELS = ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")

_SMOKE_AGENT_CARD = AgentCard.model_validate(
    {
        "name": "phase6d-smoke-agent",
        "description": "Synthetic smoke-only remote agent (NOT a study fixture).",
        "supported_interfaces": [
            {
                "url": "http://phase6d-smoke-agent.invalid",
                "protocol_binding": "HTTP_JSON",
                "protocol_version": "1.0",
            }
        ],
        "default_input_modes": ["text/plain"],
        "default_output_modes": ["text/plain"],
    }
)

# Harmless, read-only, smoke-only tool. Not a study tool; nothing is
# executed against it -- we only parse the model's chosen action.
_SMOKE_READ_TOOL = ToolDefinition(
    name="get_smoke_status",
    description="Return a static 'ok' status string. Read-only; no side effects.",
    input_schema={"type": "object", "properties": {}, "required": []},
)


def _smoke_context() -> HostDecisionContext:
    """Smoke wire path. Allowed actions: call_tool + stop. The only tool
    offered is a harmless read-only smoke tool."""
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


async def _one_smoke_call(model: str) -> dict:
    """One real OpenAI Responses call. Exactly one decision, zero retries.
    Returns a JSON-safe result dict (no chain-of-thought)."""
    from app.runner.real_host_adapter import (
        RealHostAgentAdapter,
        build_openai_responses_client,
    )

    client = build_openai_responses_client(timeout_seconds=_TIMEOUT_SECONDS, max_retries=0)
    adapter = RealHostAgentAdapter(
        client,
        model=model,
        max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
        timeout_seconds=_TIMEOUT_SECONDS,
        max_retries=0,
        max_decisions=1,
        case_id=f"smoke-{model}",
        reasoning_effort="low",
        allowed_actions=_SMOKE_ALLOWED_ACTIONS,
    )
    spec = await adapter.decide(_smoke_context())
    call = adapter.provenance.provider_calls[-1]
    return {
        "model_label": model,
        "status": "ok",
        "allowed_actions": list(_SMOKE_ALLOWED_ACTIONS),
        "requested_model": call.requested_model,
        "returned_model": call.returned_model,
        "provider_response_id": call.provider_response_id,
        "provider_api_surface": "openai.responses",
        "status_reason": call.status,
        "stop_reason": None,
        "usage": {
            "input_tokens": call.input_tokens,
            "output_tokens": call.output_tokens,
            "total_tokens": call.total_tokens,
        },
        "latency_ms": call.latency_ms,
        "selected_action": spec.action,
        "parsed_host_action_spec": spec.model_dump(),
        "provider_call_status": call.status,
        "provider_config_sha256": provider_config_sha256(
            model,
            canonical_actions=_CANONICAL_ACTIONS,
            timeout_seconds=_TIMEOUT_SECONDS,
        ),
        "counts_toward_640_study": False,
        "note": "infrastructure smoke test; NOT one of the 640 study trials",
    }


def _write_report(payload: dict) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _REPORT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> int:
    started = datetime.now(UTC).isoformat()
    results: list[dict] = []
    try:
        for model in _OPENAI_MODELS:
            results.append(asyncio.run(_one_smoke_call(model)))
    except Exception as exc:  # noqa: BLE001 - any failure -> sanitized report, no retry
        message = str(exc)
        _write_report(
            {
                "phase": "6d.0-openai-smoke",
                "kind": "infrastructure_smoke_test",
                "is_study_trial": False,
                "counts_toward_640_study": False,
                "started_at": started,
                "finished_at": datetime.now(UTC).isoformat(),
                "outcome": "FAILED",
                "completed_calls": results,
                "failure": {"sanitized_message": message[:800], "retried": False},
            }
        )
        print(f"SMOKE FAILED (no retry): {message[:800]}", file=sys.stderr)
        return 1

    _write_report(
        {
            "phase": "6d.0-openai-smoke",
            "kind": "infrastructure_smoke_test",
            "is_study_trial": False,
            "counts_toward_640_study": False,
            "api": "openai.responses",
            "effort": "low",
            "max_output_tokens": OPENAI_MAX_OUTPUT_TOKENS,
            "tool_choice": "required",
            "parallel_tool_calls": False,
            "retries": 0,
            "provider_calls_made": len(results),
            "started_at": started,
            "finished_at": datetime.now(UTC).isoformat(),
            "outcome": "OK",
            "calls": results,
        }
    )
    print(json.dumps({"outcome": "OK", "provider_calls_made": len(results)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
