"""Offline contract test against the REAL OpenAI Python SDK for
RealHostAgentAdapter (Phase 4A.2), mirroring
``tests/integration/test_openai_sdk_offline_contract.py``'s proven pattern:
a REAL ``openai.AsyncOpenAI`` client, backed by ``httpx.MockTransport`` — a
synchronous, in-process request handler — so the SDK's actual wire
serialization/parsing code runs for real while zero sockets are ever
opened and zero requests reach any real host.

Skipped entirely (not failed) when the optional ``openai`` extra is not
installed. No test in this file ever calls the real OpenAI inference
endpoint.
"""

from __future__ import annotations

import json

import pytest

openai = pytest.importorskip("openai")
httpx = pytest.importorskip("httpx")

from app.models.a2a import AgentCard, AgentInterface  # noqa: E402
from app.models.host_context import HostDecisionContext  # noqa: E402
from app.models.tools import ToolDefinition  # noqa: E402
from app.runner.real_host_adapter import RealHostAgentAdapter  # noqa: E402

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

RESPONSE_JSON = {
    "id": "resp_host_1",
    "object": "response",
    "created_at": 1234567890,
    "status": "completed",
    "model": "gpt-test-returned",
    "output": [
        {"type": "reasoning", "id": "rs_should_not_leak_host", "summary": []},
        {
            "type": "function_call",
            "id": "fc_1",
            "call_id": "call_host_1",
            "name": "relay_to_remote",
            "arguments": json.dumps({"content": "hello remote", "content_type": "text/plain"}),
            "status": "completed",
        },
    ],
    "parallel_tool_calls": False,
    "tool_choice": "required",
    "tools": [],
    "incomplete_details": None,
    "usage": {
        "input_tokens": 12,
        "output_tokens": 6,
        "total_tokens": 18,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 0},
    },
}


class _OfflineMockHandler:
    def __init__(self, responses: list[dict]):
        self._responses = list(responses)
        self.captured_requests: list[dict] = []

    def __call__(self, request) -> httpx.Response:
        self.captured_requests.append(json.loads(request.content))
        return httpx.Response(200, json=self._responses.pop(0))


def _build_offline_client(handler: _OfflineMockHandler):
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return openai.AsyncOpenAI(
        api_key="test-key-not-real-never-sent-anywhere",
        http_client=http_client,
        timeout=5.0,
        max_retries=0,
    )


async def test_real_sdk_offline_host_decision_contract():
    handler = _OfflineMockHandler([RESPONSE_JSON])
    client = _build_offline_client(handler)
    adapter = RealHostAgentAdapter(client.responses, model="gpt-test", max_output_tokens=256)

    context = HostDecisionContext(
        user_prompt="ask the remote agent for a recommendation",
        host_policy="You may call tools, relay, attempt mutations, or stop.",
        history=[],
        available_tools=[DEPLOYMENT_TOOL],
        target_agent_card=AGENT_CARD,
        current_step=0,
    )
    action = await adapter.decide(context)

    assert action.action == "relay_to_remote"
    assert action.relay_template == "hello remote"

    request = handler.captured_requests[0]
    assert request["model"] == "gpt-test"
    assert request["parallel_tool_calls"] is False
    assert request["tool_choice"] == "required"
    assert request["max_output_tokens"] == 256
    assert request["instructions"] == "You may call tools, relay, attempt mutations, or stop."
    tool_names = {tool["name"] for tool in request["tools"]}
    assert tool_names == {"call_local_tool", "relay_to_remote", "attempt_mutating_tool", "stop"}

    sent_content = json.loads(request["input"][0]["content"])
    assert sent_content["user_prompt"] == "ask the remote agent for a recommendation"
    assert sent_content["available_mcp_tools"][0]["name"] == "get_deployment_status"

    provenance_json = adapter.provenance.model_dump_json()
    assert "rs_should_not_leak_host" not in provenance_json
    assert adapter.provenance.total_tokens == 18
    assert adapter.provenance.provider_calls[0].provider_response_id == "resp_host_1"


def test_offline_contract_test_used_zero_outbound_sockets():
    import asyncio
    import socket

    def exploding_connect(self, address):
        raise AssertionError(
            f"offline contract test attempted a real socket connection to {address}"
        )

    original_connect = socket.socket.connect
    socket.socket.connect = exploding_connect
    try:
        handler = _OfflineMockHandler([RESPONSE_JSON])
        client = _build_offline_client(handler)
        adapter = RealHostAgentAdapter(client.responses, model="gpt-test")

        context = HostDecisionContext(
            user_prompt="ask",
            host_policy="policy",
            history=[],
            available_tools=[],
            target_agent_card=AGENT_CARD,
            current_step=0,
        )

        async def run():
            await adapter.decide(context)

        asyncio.run(run())
        assert len(handler.captured_requests) == 1
    finally:
        socket.socket.connect = original_connect
