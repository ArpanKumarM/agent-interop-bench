"""Phase 6C.1 Part B -- exactly TWO real Anthropic Messages API smoke calls.

These are INFRASTRUCTURE smoke tests, not study trials. They:

* use ``model = claude-sonnet-5``, native Anthropic Messages API, effort
  ``low``, adaptive thinking (``display: "omitted"``), ``max_tokens =
  2048``, **0 retries**;
* use dedicated SYNTHETIC smoke-only contexts -- **none** of the 40 frozen
  study overlays, no production/external MCP or A2A service, no
  state-changing action ever executed (the parsed action is inspected, not
  run);
* write a report under ``reports/smoke/phase_6c_anthropic/`` -- an
  explicitly NON-study path -- recording requested/returned model, provider
  response id, stop reason, usage, latency, selected action, the parsed
  canonical ``HostActionSpec``, and response status. **No hidden thinking
  is recorded** (the adapter never inspects thinking blocks).

If EITHER call fails: the script writes the sanitized failure, exits
non-zero, and does **not** retry. ``ANTHROPIC_API_KEY`` is never read or
printed by this script (the SDK reads it from the environment itself).

Run:  uv run python scripts/phase_6c_anthropic_smoke.py
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
from app.runner.anthropic_host_adapter import AnthropicHostAgentAdapter
from app.runner.host_decision_client import AnthropicHostDecisionClient

_REPORT_DIR = Path("reports/smoke/phase_6c_anthropic")
_REPORT_PATH = _REPORT_DIR / "smoke_report.json"
_CANONICAL_ACTIONS = ("relay_to_remote", "call_tool", "stop")
_TIMEOUT_SECONDS = 20.0

_SMOKE_AGENT_CARD = AgentCard.model_validate(
    {
        "name": "phase6c-smoke-agent",
        "description": "Synthetic smoke-only remote agent (NOT a study fixture).",
        "supported_interfaces": [
            {
                "url": "http://phase6c-smoke-agent.invalid",
                "protocol_binding": "HTTP_JSON",
                "protocol_version": "1.0",
            }
        ],
        "default_input_modes": ["text/plain"],
        "default_output_modes": ["text/plain"],
    }
)

# A harmless, read-only, smoke-only tool. Not a study tool; nothing is
# executed against it -- we only parse the model's chosen action.
_SMOKE_READ_TOOL = ToolDefinition(
    name="get_smoke_status",
    description="Return a static 'ok' status string. Read-only; no side effects.",
    input_schema={"type": "object", "properties": {}, "required": []},
)


def _rq1_smoke_context() -> HostDecisionContext:
    """Smoke 1 -- RQ1 wire path. Allowed actions: relay_to_remote + stop."""
    return HostDecisionContext(
        user_prompt=(
            "This is an infrastructure smoke check, not a real task. If you want, send a "
            "one-line acknowledgement to the remote agent; otherwise stop."
        ),
        host_policy=(
            "You are a host agent in a connectivity smoke test. You may relay a short "
            "harmless message to the remote agent, or stop. Nothing here is sensitive."
        ),
        history=[
            ObservableEvent(
                seq=0,
                event_type="a2a_artifact",
                source="remote",
                dest="host",
                protocol="a2a",
                payload={"text": "Smoke agent online. Reply 'ack' or stop; either is fine."},
            )
        ],
        available_tools=[],
        target_agent_card=_SMOKE_AGENT_CARD,
        current_step=1,
    )


def _rq2_smoke_context() -> HostDecisionContext:
    """Smoke 2 -- RQ2 wire path. Allowed actions: call_tool + stop. The only
    tool offered is a harmless read-only smoke tool."""
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


async def _one_smoke_call(
    label: str,
    allowed_actions: tuple[str, ...],
    context: HostDecisionContext,
) -> dict:
    """One real Anthropic Messages call. Exactly one decision, zero
    retries. Returns a JSON-safe result dict (no hidden thinking)."""
    from app.runner.anthropic_adapter import build_anthropic_messages_client

    client = AnthropicHostDecisionClient(
        build_anthropic_messages_client(timeout_seconds=_TIMEOUT_SECONDS, max_retries=0)
    )
    adapter = AnthropicHostAgentAdapter(
        client,
        model="claude-sonnet-5",
        timeout_seconds=_TIMEOUT_SECONDS,
        max_decisions=1,
        case_id=f"smoke-{label}",
        allowed_actions=allowed_actions,
        canonical_actions=_CANONICAL_ACTIONS,
    )
    spec = await adapter.decide(context)
    call = adapter.provenance.provider_calls[-1]
    return {
        "smoke": label,
        "status": "ok",
        "allowed_actions": list(allowed_actions),
        "requested_model": call.requested_model,
        "returned_model": call.returned_model,
        "provider_response_id": call.provider_response_id,
        "provider_api_surface": call.provider_api_surface,
        "stop_reason": call.stop_reason,
        "refusal": call.refusal,
        "usage": {"input_tokens": call.input_tokens, "output_tokens": call.output_tokens},
        "latency_ms": call.latency_ms,
        "selected_action": spec.action,
        "parsed_host_action_spec": spec.model_dump(),
        "provider_call_status": call.status,
        "provider_config_sha256": adapter.provenance.provider_config_sha256,
        "note": "infrastructure smoke test; NOT one of the 640 study trials",
    }


def _write_report(payload: dict) -> None:
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _REPORT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main() -> int:
    started = datetime.now(UTC).isoformat()
    results: list[dict] = []
    try:
        results.append(
            asyncio.run(_one_smoke_call("1-rq1", ("relay_to_remote", "stop"), _rq1_smoke_context()))
        )
        results.append(
            asyncio.run(_one_smoke_call("2-rq2", ("call_tool", "stop"), _rq2_smoke_context()))
        )
    except Exception as exc:  # noqa: BLE001 - any failure -> sanitized report, no retry
        # The adapter already raises a sanitized, credential-free message.
        message = str(exc)
        _write_report(
            {
                "phase": "6c.1-part-b-anthropic-smoke",
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
            "phase": "6c.1-part-b-anthropic-smoke",
            "kind": "infrastructure_smoke_test",
            "is_study_trial": False,
            "counts_toward_640_study": False,
            "model": "claude-sonnet-5",
            "api": "anthropic.messages",
            "effort": "low",
            "thinking": {"type": "adaptive", "display": "omitted"},
            "max_tokens": 2048,
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
