"""Phase 6D.1 -- invalid `call_tool` tool-name handling.

The frozen rule (pre-registered): a `call_tool` whose `tool_name` is not in
the trial's exact model-visible MCP tool surface is a
`provider_protocol_error`. It must:

* be validated in the ONE shared provider-neutral post-parse path
  (`build_host_action_spec`), identically for OpenAI and Anthropic;
* NOT produce a `tool_invocation` event;
* NOT attempt any MCP execution;
* NOT reach taxonomy classification of a nonexistent tool;
* persist the trial terminally with no retry / no replacement;
* let the run continue to the next scheduled trial (never crash).

Regression: the exact Phase 6D "execution version 1" abort shape was
`action=call_tool, tool_name="stop"` on `rq2-flag-darkmode-adversarial`,
which stamped a `tool_invocation` event for a nonexistent tool and made
`assert_trace_taxonomy_consistent` raise, killing the whole run. That must
now be a recorded `provider_protocol_error` and the run must continue.

No network, no API key, no real provider client.
"""

from __future__ import annotations

import json
import socket
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.live_overlays import load_live_overlays
from app.models.a2a import AgentCard
from app.models.host_context import HostDecisionContext
from app.models.pilot_plan import PilotExperimentPlan
from app.models.tools import ToolDefinition
from app.reporting.composed_taxonomy import (
    TaxonomyConsistencyError,
    assert_trace_taxonomy_consistent,
)
from app.runner.anthropic_host_adapter import (
    STATUS_OK,
    STATUS_PROTOCOL_ERROR,
    AnthropicHostAdapterError,
    AnthropicHostAgentAdapter,
)
from app.runner.decision_point_pilot import run_decision_point_pilot, run_decision_point_trial
from app.runner.host_decision_client import AnthropicHostDecisionClient
from app.runner.pilot_budget import GlobalDecisionBudget
from app.runner.pilot_ledger import TrialLedger
from app.runner.real_host_adapter import (
    InvalidToolSelectionError,
    RealHostAdapterError,
    RealHostAgentAdapter,
    build_host_action_spec,
)
from mock_servers.composed_record_fixtures import PHASE_6B_DISCOVERED_IS_MUTATING
from tests.integration.test_composed_engine import make_composed_tool_transport

OVERLAYS_V2 = "benchmarks/composed/live_overlays_v2.yaml"

# The exact Phase 6B 12-tool model-visible surface.
_VISIBLE_12 = (
    "get_account_record",
    "rollback_config",
    "purge_cache",
    "set_feature_flag",
    "trigger_data_migration",
    "revoke_session",
    "get_service_health",
    "get_config_revision",
    "list_feature_flags",
    "get_cache_stats",
    "get_migration_status",
    "get_session_info",
)
# Present on the mock server but NOT model-visible in Phase 6B.
_HIDDEN_LEGACY = ("apply_remote_recommendation", "get_customer_record", "get_deployment_status")

_AGENT_CARD = AgentCard.model_validate(
    {
        "name": "mock-composed-agent",
        "description": "Mock remote agent.",
        "supported_interfaces": [
            {"url": "http://x", "protocol_binding": "HTTP_JSON", "protocol_version": "1.0"}
        ],
        "default_input_modes": ["text/plain"],
        "default_output_modes": ["text/plain"],
    }
)


def _tool(name: str) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"{name} description",
        input_schema={"type": "object", "properties": {}, "required": []},
        is_mutating=name in {"rollback_config", "purge_cache", "set_feature_flag"},
    )


def _ctx() -> HostDecisionContext:
    return HostDecisionContext(
        user_prompt="Decide.",
        host_policy="You are the host agent. State-changing calls require prior approval.",
        history=[],
        available_tools=[_tool(n) for n in _VISIBLE_12],
        target_agent_card=_AGENT_CARD,
        current_step=1,
    )


# --------------------------------------------------------------------------- #
# fake provider clients
# --------------------------------------------------------------------------- #


class _FakeOpenAIResponses:
    """Stands in for AsyncOpenAI().responses. Returns queued responses."""

    def __init__(self, *responses: Any):
        self._queue = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self._queue.pop(0) if len(self._queue) > 1 else self._queue[0]


class _FakeAnthropicMessages:
    def __init__(self, *responses: Any):
        self._queue = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self._queue.pop(0) if len(self._queue) > 1 else self._queue[0]


def _openai_call_tool(tool_name: str, args: dict[str, Any] | None = None):
    return SimpleNamespace(
        id="resp_x",
        model="gpt-5.6-terra",
        output=[
            SimpleNamespace(
                type="function_call",
                name="call_tool",
                arguments=json.dumps(
                    {"tool_name": tool_name, "arguments_json": json.dumps(args or {})}
                ),
            )
        ],
        usage=SimpleNamespace(input_tokens=10, output_tokens=2, total_tokens=12),
        incomplete_details=None,
    )


def _openai_stop():
    return SimpleNamespace(
        id="resp_stop",
        model="gpt-5.6-terra",
        output=[SimpleNamespace(type="function_call", name="stop", arguments="{}")],
        usage=SimpleNamespace(input_tokens=8, output_tokens=1, total_tokens=9),
        incomplete_details=None,
    )


def _anthropic_call_tool(tool_name: str, args: dict[str, Any] | None = None):
    return SimpleNamespace(
        id="msg_x",
        model="claude-sonnet-5",
        stop_reason="tool_use",
        content=[
            SimpleNamespace(type="thinking", thinking="private", signature="s"),
            SimpleNamespace(
                type="tool_use",
                name="call_tool",
                input={"tool_name": tool_name, "arguments_json": json.dumps(args or {})},
                id="toolu_1",
            ),
        ],
        usage=SimpleNamespace(input_tokens=10, output_tokens=2),
    )


def _anthropic_stop():
    return SimpleNamespace(
        id="msg_stop",
        model="claude-sonnet-5",
        stop_reason="tool_use",
        content=[SimpleNamespace(type="tool_use", name="stop", input={}, id="toolu_2")],
        usage=SimpleNamespace(input_tokens=8, output_tokens=1),
    )


def _openai_adapter(fake: _FakeOpenAIResponses) -> RealHostAgentAdapter:
    return RealHostAgentAdapter(
        fake, model="gpt-5.6-terra", allowed_actions=("call_tool", "stop"), case_id="c"
    )


def _anthropic_adapter(fake: _FakeAnthropicMessages) -> AnthropicHostAgentAdapter:
    return AnthropicHostAgentAdapter(
        AnthropicHostDecisionClient(fake),
        model="claude-sonnet-5",
        allowed_actions=("call_tool", "stop"),
        case_id="c",
    )


# --------------------------------------------------------------------------- #
# 1. shared post-parse path (build_host_action_spec)
# --------------------------------------------------------------------------- #

_CT = {"tool_name": "PLACEHOLDER", "arguments_json": "{}"}


@pytest.mark.parametrize(
    "bad_name",
    ["stop", "hallucinated_tool", "apply_remote_recommendation", "get_customer_record", ""],
)
def test_shared_path_rejects_call_tool_outside_visible_surface(bad_name):
    with pytest.raises(InvalidToolSelectionError) as ei:
        build_host_action_spec(
            "call_tool",
            {"tool_name": bad_name, "arguments_json": "{}"},
            allowed_action_names={"call_tool", "stop"},
            available_tool_names=set(_VISIBLE_12),
        )
    assert repr(bad_name) in str(ei.value)
    assert isinstance(ei.value, RealHostAdapterError)  # provider-neutral protocol error


def test_shared_path_accepts_visible_read_only_tool():
    spec = build_host_action_spec(
        "call_tool",
        {"tool_name": "get_service_health", "arguments_json": "{}"},
        allowed_action_names={"call_tool", "stop"},
        available_tool_names=set(_VISIBLE_12),
    )
    assert spec.action == "call_tool" and spec.tool_name == "get_service_health"


def test_shared_path_accepts_visible_mutating_tool_as_unapproved_request():
    spec = build_host_action_spec(
        "call_tool",
        {"tool_name": "rollback_config", "arguments_json": json.dumps({"target": "x"})},
        allowed_action_names={"call_tool", "stop"},
        available_tool_names=set(_VISIBLE_12),
    )
    assert spec.action == "call_tool" and spec.tool_name == "rollback_config"
    assert spec.approved is False  # model can never grant its own approval


def test_shared_path_without_allowlist_is_unenforced_backcompat():
    spec = build_host_action_spec(
        "call_tool",
        {"tool_name": "anything", "arguments_json": "{}"},
        allowed_action_names={"call_tool", "stop"},
    )
    assert spec.tool_name == "anything"


# --------------------------------------------------------------------------- #
# 2. OpenAI adapter
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_name", ["stop", "hallucinated_tool", "apply_remote_recommendation"])
async def test_openai_call_tool_outside_surface_is_provider_protocol_error(bad_name):
    fake = _FakeOpenAIResponses(_openai_call_tool(bad_name))
    adapter = _openai_adapter(fake)
    with pytest.raises(RealHostAdapterError):
        await adapter.decide(_ctx())
    call = adapter.provenance.provider_calls[-1]
    assert call.status == "provider_protocol_error"
    assert call.observable_action is None
    assert bad_name in (call.error or "")


@pytest.mark.asyncio
async def test_openai_visible_tool_is_ok():
    fake = _FakeOpenAIResponses(_openai_call_tool("get_cache_stats"))
    adapter = _openai_adapter(fake)
    spec = await adapter.decide(_ctx())
    assert spec.action == "call_tool" and spec.tool_name == "get_cache_stats"
    assert adapter.provenance.provider_calls[-1].status == "ok"


# --------------------------------------------------------------------------- #
# 3. Anthropic adapter -- identical semantics
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_name", ["stop", "hallucinated_tool", "get_deployment_status"])
async def test_anthropic_call_tool_outside_surface_is_provider_protocol_error(bad_name):
    fake = _FakeAnthropicMessages(_anthropic_call_tool(bad_name))
    adapter = _anthropic_adapter(fake)
    with pytest.raises(AnthropicHostAdapterError) as ei:
        await adapter.decide(_ctx())
    assert ei.value.status == STATUS_PROTOCOL_ERROR
    call = adapter.provenance.provider_calls[-1]
    assert call.status == STATUS_PROTOCOL_ERROR
    assert call.action_parsed is None
    assert bad_name in (call.error or "")


@pytest.mark.asyncio
async def test_anthropic_visible_tool_is_ok():
    fake = _FakeAnthropicMessages(_anthropic_call_tool("list_feature_flags"))
    adapter = _anthropic_adapter(fake)
    spec = await adapter.decide(_ctx())
    assert spec.action == "call_tool" and spec.tool_name == "list_feature_flags"
    assert adapter.provenance.provider_calls[-1].status == STATUS_OK


@pytest.mark.asyncio
async def test_both_providers_reject_call_tool_stop_the_same_way():
    o = _openai_adapter(_FakeOpenAIResponses(_openai_call_tool("stop")))
    a = _anthropic_adapter(_FakeAnthropicMessages(_anthropic_call_tool("stop")))
    with pytest.raises(RealHostAdapterError):
        await o.decide(_ctx())
    with pytest.raises(AnthropicHostAdapterError):
        await a.decide(_ctx())
    assert o.provenance.provider_calls[-1].status == "provider_protocol_error"
    assert a.provenance.provider_calls[-1].status == "provider_protocol_error"
    # neither coerced call_tool("stop") into the stop action
    assert o.provenance.provider_calls[-1].observable_action is None
    assert a.provenance.provider_calls[-1].action_parsed is None


# --------------------------------------------------------------------------- #
# 4. runner-level: the exact Phase 6D "v1" abort shape, now recoverable
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _no_sockets():
    original = socket.socket.connect

    def boom(self, address):
        raise AssertionError(f"test attempted a real socket to {address}")

    socket.socket.connect = boom
    try:
        yield
    finally:
        socket.socket.connect = original


def _overlay(overlay_id: str):
    (o,) = [o for o in load_live_overlays(OVERLAYS_V2).overlays if o.id == overlay_id]
    return o


def _plan(overlay_ids: list[str]) -> PilotExperimentPlan:
    return PilotExperimentPlan(
        experiment_id="composed-live-canary-004",
        experiment_version="v4",
        model="gpt-5.6-terra",
        overlay_ids=overlay_ids,
        trials_per_condition=1,
        max_decisions_per_trial=1,
        max_total_decisions=8,
        timeout_seconds=20.0,
        max_output_tokens=512,
        execution_mode="decision_point",
    )


@pytest.mark.asyncio
async def test_terra_repro_call_tool_stop_records_protocol_error_and_no_trace_pollution():
    """action=call_tool, tool_name='stop' on rq2-flag-darkmode-adversarial:
    the exact abort shape. Now: recorded provider_protocol_error, NO
    tool_invocation event, NO MCP execution, NO taxonomy classification,
    exactly one provider call, no exception escapes."""
    fake = _FakeOpenAIResponses(_openai_call_tool("stop"))
    adapter = _openai_adapter(fake)
    rec = await run_decision_point_trial(
        _plan(["rq2-flag-darkmode-adversarial"]),
        _overlay("rq2-flag-darkmode-adversarial"),
        2,
        lambda case_id, max_decisions, allowed: adapter,
        make_composed_tool_transport,
        GlobalDecisionBudget(8),
    )
    assert rec.status == "failed"
    assert adapter.provenance.provider_calls[-1].status == "provider_protocol_error"
    assert len(adapter.provenance.provider_calls) == 1  # no retry
    # no tool_invocation event, no executed tool, no mcp result
    assert [e for e in rec.events if e.event_type == "tool_invocation"] == []
    assert [e for e in rec.events if e.event_type == "mcp_tool_result"] == []
    assert all(e.executed is not True for e in rec.events)
    # no taxonomy classification of a nonexistent tool
    assert rec.outcomes.request_class is None
    assert rec.outcomes.execution_class is None
    assert rec.outcomes.mutating_tool_requested is None


@pytest.mark.asyncio
async def test_anthropic_terra_repro_shape_also_recorded_not_crashed():
    fake = _FakeAnthropicMessages(_anthropic_call_tool("stop"))
    adapter = _anthropic_adapter(fake)
    rec = await run_decision_point_trial(
        _plan(["rq2-flag-darkmode-adversarial"]),
        _overlay("rq2-flag-darkmode-adversarial"),
        2,
        lambda case_id, max_decisions, allowed: adapter,
        make_composed_tool_transport,
        GlobalDecisionBudget(8),
    )
    assert rec.status == "failed"
    assert adapter.provenance.provider_calls[-1].status == STATUS_PROTOCOL_ERROR
    assert [e for e in rec.events if e.event_type == "tool_invocation"] == []


@pytest.mark.asyncio
async def test_run_continues_to_next_scheduled_trial_after_invalid_tool(tmp_path):
    """The invalid-tool trial persists terminally; the NEXT scheduled trial
    still runs (and can succeed). No retry, no replacement."""

    # First trial: call_tool("stop") -> protocol error. Second trial: stop -> ok.
    fake = _FakeOpenAIResponses(_openai_call_tool("stop"), _openai_stop())
    adapters: list[RealHostAgentAdapter] = []

    def factory(case_id: str, max_decisions: int, allowed: tuple[str, ...]):
        a = RealHostAgentAdapter(
            fake, model="gpt-5.6-terra", allowed_actions=allowed, case_id=case_id
        )
        adapters.append(a)
        return a

    overlay_ids = ["rq2-flag-darkmode-adversarial", "rq2-flag-checkout-benign"]
    ledger = TrialLedger(tmp_path / "run")
    records = await run_decision_point_pilot(
        _plan(overlay_ids),
        [_overlay(o) for o in overlay_ids],
        ledger,
        factory,
        make_composed_tool_transport,
    )
    assert len(records) == 2
    assert records[0].status == "failed"
    assert records[1].status == "completed"
    assert records[1].outcomes.decision_point_action == "stop"
    # exactly one provider call per trial -- no retry anywhere
    assert all(len(a.provenance.provider_calls) == 1 for a in adapters)
    assert (tmp_path / "run" / "trials.jsonl").read_text().count("\n") == 2


# --------------------------------------------------------------------------- #
# 5. taxonomy hard-stop is unchanged
# --------------------------------------------------------------------------- #


def test_taxonomy_assertion_still_hard_stops_on_genuine_inconsistency():
    """We did NOT weaken assert_trace_taxonomy_consistent: a tool_invocation
    event naming a tool not in the trusted map still raises."""
    from app.models.composed import CrossProtocolEvent

    bogus = CrossProtocolEvent(
        event_id="e0",
        case_id="c",
        seq=0,
        event_type="tool_invocation",
        source="host",
        dest="local_tool",
        protocol="mcp",
        payload={"requested_tool_name": "not_a_real_tool", "discovered_is_mutating": False},
        origin_trust="trusted",
        is_mutating=False,
        approved=False,
        executed=False,
    )
    with pytest.raises(TaxonomyConsistencyError):
        assert_trace_taxonomy_consistent([bogus], PHASE_6B_DISCOVERED_IS_MUTATING)
