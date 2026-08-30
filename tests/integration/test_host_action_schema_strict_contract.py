"""Phase 4A.3c offline contract test: the EXACT host-action function schemas
this project sends to the OpenAI Responses API must satisfy strict-mode
object invariants at every nesting depth, and each of the four tools must
round-trip through the real ``openai`` SDK.

Pattern mirrors ``test_real_host_adapter_sdk_offline_contract.py``: a REAL
``openai.AsyncOpenAI`` client backed by ``httpx.MockTransport`` (in-process
request handler) -- the SDK's real serialization runs, zero sockets open,
zero requests reach any host. The mock transport inspects the OUTGOING
request body's ``tools`` array and records a failure if ANY nested object
lacks ``additionalProperties: false`` or has properties not fully listed in
``required``. Skipped (not failed) when the optional ``openai`` extra is
absent.
"""

from __future__ import annotations

import json
import socket

import pytest

openai = pytest.importorskip("openai")
httpx = pytest.importorskip("httpx")

from app.models.a2a import AgentCard, AgentInterface  # noqa: E402
from app.models.host_context import HostDecisionContext  # noqa: E402
from app.models.tools import ToolDefinition  # noqa: E402
from app.runner.host_action_schema_openai import strict_schema_violations  # noqa: E402
from app.runner.real_host_adapter import RealHostAgentAdapter  # noqa: E402

AGENT_CARD = AgentCard(
    name="test-agent",
    supported_interfaces=[
        AgentInterface(url="http://test", protocol_binding="HTTP_JSON", protocol_version="1.0")
    ],
)
LOCAL_TOOL = ToolDefinition(
    name="get_deployment_status",
    description="Fetch deployment status.",
    input_schema={"type": "object", "properties": {"case_id": {"type": "string"}}},
    required_arguments=["case_id"],
    is_mutating=False,
)


def _response_json(function_name: str, arguments: dict) -> dict:
    return {
        "id": f"resp_{function_name}",
        "object": "response",
        "created_at": 1234567890,
        "status": "completed",
        "model": "gpt-5.6-terra-returned",
        "output": [
            {
                "type": "function_call",
                "id": "fc_1",
                "call_id": "call_1",
                "name": function_name,
                "arguments": json.dumps(arguments),
                "status": "completed",
            }
        ],
        "parallel_tool_calls": False,
        "tool_choice": "required",
        "tools": [],
        "incomplete_details": None,
        "usage": {
            "input_tokens": 5,
            "output_tokens": 3,
            "total_tokens": 8,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0},
        },
    }


class _SchemaInspectingHandler:
    """Captures every outgoing request body and records strict-mode
    violations found anywhere in its ``tools`` array."""

    def __init__(self, response_json: dict):
        self._response_json = response_json
        self.captured_requests: list[dict] = []
        self.schema_violations: list[str] = []

    def __call__(self, request) -> httpx.Response:
        body = json.loads(request.content)
        self.captured_requests.append(body)
        for tool in body.get("tools", []):
            name = tool.get("name", "<unnamed>")
            params = tool.get("parameters", {})
            # (a) generic recursive invariant check
            self.schema_violations.extend(
                strict_schema_violations(params, f"outgoing[{name}].parameters")
            )
            # (b) explicit per-nested-object assertions demanded by the spec
            for obj_path, obj in _walk_objects(params, f"outgoing[{name}].parameters"):
                if obj.get("additionalProperties", None) is not False:
                    self.schema_violations.append(
                        f"{obj_path}: nested object lacks additionalProperties:false"
                    )
                props = set(obj.get("properties", {}))
                if props - set(obj.get("required", [])):
                    self.schema_violations.append(
                        f"{obj_path}: properties {sorted(props)} not fully in required "
                        f"{sorted(obj.get('required', []))}"
                    )
        return httpx.Response(200, json=self._response_json)


def _walk_objects(node, path="$"):
    if not isinstance(node, dict):
        return
    if node.get("type") == "object" or "properties" in node:
        yield path, node
        for pname, pschema in node.get("properties", {}).items():
            yield from _walk_objects(pschema, f"{path}.{pname}")
    for key in ("items", "not", "additionalProperties"):
        if isinstance(node.get(key), dict):
            yield from _walk_objects(node[key], f"{path}.{key}")
    for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
        for i, sub in enumerate(node.get(key, []) or []):
            yield from _walk_objects(sub, f"{path}.{key}[{i}]")


def _build_offline_client(handler: _SchemaInspectingHandler):
    http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return openai.AsyncOpenAI(
        api_key="test-key-not-real-never-sent-anywhere",
        http_client=http_client,
        timeout=5.0,
        max_retries=0,
    )


def _context() -> HostDecisionContext:
    return HostDecisionContext(
        user_prompt="do the task",
        host_policy="You may call tools, relay, attempt mutations, or stop.",
        history=[],
        available_tools=[LOCAL_TOOL],
        target_agent_card=AGENT_CARD,
        current_step=0,
    )


ALL_FOUR_CASES = [
    (
        "call_local_tool",
        {
            "tool_name": "get_deployment_status",
            "tool_arguments_json": json.dumps({"case_id": "c1"}),
        },
    ),
    (
        "relay_to_remote",
        {"content": "hello remote", "content_type": "text/plain"},
    ),
    (
        "attempt_mutating_tool",
        {"tool_name": "apply_remote_recommendation", "tool_arguments_json": json.dumps({"a": 1})},
    ),
    ("stop", {}),
]


@pytest.mark.parametrize("function_name, arguments", ALL_FOUR_CASES)
async def test_each_host_action_tool_schema_is_strict_on_the_wire_and_round_trips(
    function_name, arguments
):
    handler = _SchemaInspectingHandler(_response_json(function_name, arguments))
    client = _build_offline_client(handler)
    adapter = RealHostAgentAdapter(client.responses, model="gpt-5.6-terra", max_output_tokens=512)

    action = await adapter.decide(_context())

    # The outgoing request carried all four tool schemas, strict, with zero
    # nested-object violations.
    assert len(handler.captured_requests) == 1
    sent_tool_names = {t["name"] for t in handler.captured_requests[0]["tools"]}
    assert sent_tool_names == {
        "call_local_tool",
        "relay_to_remote",
        "attempt_mutating_tool",
        "stop",
    }
    for tool in handler.captured_requests[0]["tools"]:
        assert tool["strict"] is True
    assert handler.schema_violations == [], handler.schema_violations

    # And the SDK accepted + parsed the response for this tool.
    assert action.action == function_name
    if function_name == "call_local_tool":
        assert action.tool_name == "get_deployment_status"
        assert action.tool_arguments == {"case_id": "c1"}
    elif function_name == "attempt_mutating_tool":
        assert action.tool_arguments == {"a": 1}
        assert action.approved is False
    elif function_name == "relay_to_remote":
        assert action.relay_template == "hello remote"


async def test_bad_tool_arguments_json_becomes_a_controlled_adapter_error():
    from app.runner.real_host_adapter import RealHostAdapterError

    handler = _SchemaInspectingHandler(
        _response_json("call_local_tool", {"tool_name": "x", "tool_arguments_json": "not json"})
    )
    client = _build_offline_client(handler)
    adapter = RealHostAgentAdapter(client.responses, model="gpt-5.6-terra")
    with pytest.raises(RealHostAdapterError, match="invalid action|tool_arguments_json"):
        await adapter.decide(_context())
    assert handler.schema_violations == []


def test_contract_test_opened_zero_sockets():
    import asyncio

    def exploding_connect(self, address):
        raise AssertionError(f"strict-schema contract test attempted a socket to {address}")

    original = socket.socket.connect
    socket.socket.connect = exploding_connect
    try:
        handler = _SchemaInspectingHandler(_response_json("stop", {}))
        client = _build_offline_client(handler)
        adapter = RealHostAgentAdapter(client.responses, model="gpt-5.6-terra")
        asyncio.run(adapter.decide(_context()))
        assert handler.schema_violations == []
        assert len(handler.captured_requests) == 1
    finally:
        socket.socket.connect = original
