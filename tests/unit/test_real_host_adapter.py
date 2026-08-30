"""Unit tests for RealHostAgentAdapter.

Uses fake ResponsesClient implementations throughout — plain objects
satisfying the ``ResponsesClient`` Protocol — so these tests never import
the real ``openai`` package, make no network call, and never touch a live
model, even though they're testing the module that would.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.models.a2a import AgentCard, AgentInterface
from app.models.host_context import HostDecisionContext
from app.models.tools import ToolDefinition
from app.runner.real_host_adapter import RealHostAdapterError, RealHostAgentAdapter

AGENT_CARD = AgentCard(
    name="test-agent",
    supported_interfaces=[
        AgentInterface(url="http://test", protocol_binding="HTTP_JSON", protocol_version="1.0")
    ],
)

DEPLOYMENT_TOOL = ToolDefinition(
    name="get_deployment_status",
    description="Fetch deployment status.",
    input_schema={"type": "object", "properties": {"case_id": {"type": "string"}}},
    required_arguments=["case_id"],
    is_mutating=False,
)

MUTATING_TOOL = ToolDefinition(
    name="apply_remote_recommendation",
    description="Apply a recommendation. Mutating.",
    input_schema={"type": "object", "properties": {"action": {"type": "string"}}},
    required_arguments=["action"],
    is_mutating=True,
)


def _context(step: int = 0, history=None, tools=None) -> HostDecisionContext:
    return HostDecisionContext(
        user_prompt="do the task",
        host_policy="policy text",
        history=history or [],
        available_tools=tools or [DEPLOYMENT_TOOL, MUTATING_TOOL],
        target_agent_card=AGENT_CARD,
        current_step=step,
    )


class FakeResponsesClient:
    def __init__(self, responses=None, exception: Exception | None = None):
        self._responses = list(responses or [])
        self._exception = exception
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._exception is not None:
            raise self._exception
        return self._responses.pop(0)


def _function_call(name, arguments, call_id="call_1"):
    return SimpleNamespace(
        type="function_call", name=name, arguments=json.dumps(arguments), call_id=call_id
    )


def _response(output=None, usage=None, response_id="resp_1", model="gpt-test", incomplete=None):
    return SimpleNamespace(
        id=response_id,
        model=model,
        output=output or [],
        usage=usage,
        incomplete_details=incomplete,
    )


async def test_valid_call_local_tool():
    client = FakeResponsesClient(
        [
            _response(
                output=[
                    _function_call(
                        "call_local_tool", {"tool_name": "x", "tool_arguments": {"a": 1}}
                    )
                ]
            )
        ]
    )
    adapter = RealHostAgentAdapter(client, model="gpt-test")
    action = await adapter.decide(_context())
    assert action.action == "call_local_tool"
    assert action.tool_name == "x"
    assert action.tool_arguments == {"a": 1}


async def test_valid_relay_to_remote():
    client = FakeResponsesClient(
        [
            _response(
                output=[
                    _function_call(
                        "relay_to_remote", {"content": "hello", "content_type": "text/plain"}
                    )
                ]
            )
        ]
    )
    adapter = RealHostAgentAdapter(client, model="gpt-test")
    action = await adapter.decide(_context())
    assert action.action == "relay_to_remote"
    assert action.relay_template == "hello"
    assert action.content_type == "text/plain"


async def test_valid_attempt_mutating_tool_forces_approved_false():
    client = FakeResponsesClient(
        [
            _response(
                output=[
                    _function_call(
                        "attempt_mutating_tool",
                        {
                            "tool_name": "apply_remote_recommendation",
                            "tool_arguments": {"action": "x"},
                        },
                    )
                ]
            )
        ]
    )
    adapter = RealHostAgentAdapter(client, model="gpt-test")
    action = await adapter.decide(_context())
    assert action.action == "attempt_mutating_tool"
    assert action.tool_name == "apply_remote_recommendation"
    # The model can never grant its own approval.
    assert action.approved is False
    assert action.trigger_name is None


async def test_valid_stop():
    client = FakeResponsesClient([_response(output=[_function_call("stop", {})])])
    adapter = RealHostAgentAdapter(client, model="gpt-test")
    action = await adapter.decide(_context())
    assert action.action == "stop"


async def test_malformed_json_arguments_raises():
    bad_call = SimpleNamespace(
        type="function_call", name="stop", arguments="{not json", call_id="c1"
    )
    client = FakeResponsesClient([_response(output=[bad_call])])
    adapter = RealHostAgentAdapter(client, model="gpt-test")
    with pytest.raises(RealHostAdapterError, match="unparseable"):
        await adapter.decide(_context())


async def test_non_object_arguments_raises():
    bad_call = SimpleNamespace(type="function_call", name="stop", arguments="[1,2,3]", call_id="c1")
    client = FakeResponsesClient([_response(output=[bad_call])])
    adapter = RealHostAgentAdapter(client, model="gpt-test")
    with pytest.raises(RealHostAdapterError, match="non-object"):
        await adapter.decide(_context())


async def test_missing_required_field_raises():
    client = FakeResponsesClient(
        [_response(output=[_function_call("relay_to_remote", {"content_type": "text/plain"})])]
    )
    adapter = RealHostAgentAdapter(client, model="gpt-test")
    with pytest.raises(RealHostAdapterError, match="invalid action"):
        await adapter.decide(_context())


async def test_unknown_action_name_raises():
    client = FakeResponsesClient([_response(output=[_function_call("delete_everything", {})])])
    adapter = RealHostAgentAdapter(client, model="gpt-test")
    with pytest.raises(RealHostAdapterError, match="Unknown action"):
        await adapter.decide(_context())


async def test_zero_function_calls_raises():
    client = FakeResponsesClient([_response(output=[])])
    adapter = RealHostAgentAdapter(client, model="gpt-test")
    with pytest.raises(RealHostAdapterError, match="expected exactly one"):
        await adapter.decide(_context())


async def test_multiple_function_calls_raises():
    client = FakeResponsesClient(
        [_response(output=[_function_call("stop", {}), _function_call("stop", {})])]
    )
    adapter = RealHostAgentAdapter(client, model="gpt-test")
    with pytest.raises(RealHostAdapterError, match="expected exactly one"):
        await adapter.decide(_context())


async def test_incomplete_response_raises():
    client = FakeResponsesClient(
        [_response(incomplete=SimpleNamespace(reason="max_output_tokens"))]
    )
    adapter = RealHostAgentAdapter(client, model="gpt-test")
    with pytest.raises(RealHostAdapterError, match="incomplete"):
        await adapter.decide(_context())


async def test_provider_error_is_sanitized_and_raised():
    client = FakeResponsesClient(exception=RuntimeError("Authorization: Bearer sk-secret123456"))
    adapter = RealHostAgentAdapter(client, model="gpt-test")
    with pytest.raises(RealHostAdapterError) as exc_info:
        await adapter.decide(_context())
    assert "sk-secret123456" not in str(exc_info.value)
    assert "REDACTED" in str(exc_info.value)


async def test_decision_budget_exhaustion_raises_without_calling_provider():
    client = FakeResponsesClient([_response(output=[_function_call("stop", {})])])
    adapter = RealHostAgentAdapter(client, model="gpt-test", max_decisions=1)
    await adapter.decide(_context(step=0))  # uses the one allowed decision
    with pytest.raises(RealHostAdapterError, match="budget exhausted"):
        await adapter.decide(_context(step=1))
    assert len(client.calls) == 1  # the second call never reached the provider


async def test_provenance_recorded_without_raw_response_or_reasoning():
    reasoning_item = SimpleNamespace(type="reasoning", id="rs_should_not_leak", summary=[])
    usage = SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15)
    client = FakeResponsesClient(
        [
            _response(
                output=[reasoning_item, _function_call("stop", {})],
                usage=usage,
                response_id="resp_abc",
                model="gpt-test-returned",
            )
        ]
    )
    adapter = RealHostAgentAdapter(client, model="gpt-test", case_id="case-1")
    await adapter.decide(_context())

    assert adapter.provenance.total_provider_calls == 1
    call = adapter.provenance.provider_calls[0]
    assert call.case_id == "case-1"
    assert call.decision_index == 0
    assert call.provider_response_id == "resp_abc"
    assert call.returned_model == "gpt-test-returned"
    assert call.total_tokens == 15
    assert call.status == "ok"
    assert call.observable_action == {
        "action": "stop",
        "tool_name": None,
        "tool_arguments": {},
        "relay_template": None,
        "content_type": "text/plain",
        "approved": False,
        "trigger_name": None,
    }
    provenance_json = adapter.provenance.model_dump_json()
    assert "rs_should_not_leak" not in provenance_json
    assert adapter.provenance.tool_schema_sha256
    assert adapter.provenance.host_policy_sha256
