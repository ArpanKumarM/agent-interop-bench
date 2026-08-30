"""Phase 4A.3c regression test: the composed live-canary CLI must wire the
OpenAI client into ``RealHostAgentAdapter`` correctly.

The bug this guards against: ``build_openai_responses_client()`` already
returns the ``AsyncOpenAI().responses`` resource, but
``build_real_adapter_factory`` used to dereference ``.responses`` a *second*
time (``client.responses``), so every live run aborted with
``AttributeError: 'AsyncResponses' object has no attribute 'responses'``
before a single provider call -- see attempt-1
(``composed-live-canary-001-gpt56terra-attempt-1``).

This exercises the SAME production ``build_real_adapter_factory`` path with
a REAL ``openai.AsyncOpenAI`` client backed by ``httpx.MockTransport`` (an
in-process request handler), mirroring
``tests/integration/test_real_host_adapter_sdk_offline_contract.py``: the
SDK's real wire code runs, zero sockets are opened, zero requests reach any
real host. Skipped (not failed) when the optional ``openai`` extra is
absent.
"""

from __future__ import annotations

import json
import socket

import pytest

openai = pytest.importorskip("openai")
httpx = pytest.importorskip("httpx")

from app.cli import composed_live_pilot as cli  # noqa: E402
from app.models.a2a import AgentCard, AgentInterface  # noqa: E402
from app.models.host_context import HostDecisionContext  # noqa: E402
from app.runner import real_host_adapter as real_host_adapter_module  # noqa: E402

AGENT_CARD = AgentCard(
    name="test-agent",
    supported_interfaces=[
        AgentInterface(url="http://test", protocol_binding="HTTP_JSON", protocol_version="1.0")
    ],
)

STOP_RESPONSE_JSON = {
    "id": "resp_wiring_1",
    "object": "response",
    "created_at": 1234567890,
    "status": "completed",
    "model": "gpt-5.6-terra-returned",
    "output": [
        {
            "type": "function_call",
            "id": "fc_1",
            "call_id": "call_wiring_1",
            "name": "stop",
            "arguments": json.dumps({}),
            "status": "completed",
        }
    ],
    "parallel_tool_calls": False,
    "tool_choice": "required",
    "tools": [],
    "incomplete_details": None,
    "usage": {
        "input_tokens": 9,
        "output_tokens": 2,
        "total_tokens": 11,
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


def _context() -> HostDecisionContext:
    return HostDecisionContext(
        user_prompt="do nothing",
        host_policy="You may call tools, relay, attempt mutations, or stop.",
        history=[],
        available_tools=[],
        target_agent_card=AGENT_CARD,
        current_step=0,
    )


async def test_build_real_adapter_factory_wires_responses_resource_and_one_decide_succeeds(
    monkeypatch,
):
    handler = _OfflineMockHandler([STOP_RESPONSE_JSON])
    builder_calls: list[dict] = []
    built_resources: list[object] = []

    def _fake_build_openai_responses_client(*, timeout_seconds: float, max_retries: int):
        builder_calls.append({"timeout_seconds": timeout_seconds, "max_retries": max_retries})
        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = openai.AsyncOpenAI(
            api_key="test-key-not-real-never-sent-anywhere",
            http_client=http_client,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )
        # Exactly what the production builder returns: the `.responses`
        # resource itself, NOT the top-level client.
        resource = client.responses
        built_resources.append(resource)
        return resource

    # build_real_adapter_factory does `from app.runner.real_host_adapter import
    # ... build_openai_responses_client`, so patch it in that module's namespace.
    monkeypatch.setattr(
        real_host_adapter_module,
        "build_openai_responses_client",
        _fake_build_openai_responses_client,
    )

    plan = cli.load_frozen_plan(model="gpt-5.6-terra")

    # 1. Factory construction succeeds (previously raised AttributeError here
    #    only later, at factory() call time -- assert the whole path is clean).
    factory = cli.build_real_adapter_factory(plan)
    assert builder_calls == [{"timeout_seconds": plan.timeout_seconds, "max_retries": 0}]
    assert len(built_resources) == 1

    # 2. The adapter receives the SAME Responses resource the builder returned
    #    -- no second `.responses` dereference.
    adapter = factory("live-sensitive-egress-treatment#0", plan.max_decisions_per_trial)
    assert isinstance(adapter, real_host_adapter_module.RealHostAgentAdapter)
    assert adapter._client is built_resources[0]
    assert hasattr(adapter._client, "create")
    assert not hasattr(adapter._client, "responses"), (
        "adapter was handed the top-level client, not the .responses resource -- "
        "the double-dereference bug is back"
    )
    assert adapter._model == "gpt-5.6-terra"
    assert adapter._max_output_tokens == plan.max_output_tokens
    assert adapter._reasoning_effort == plan.reasoning_effort == "low"
    assert adapter._max_decisions == plan.max_decisions_per_trial == 4

    # 3. One mocked decide() request completes end-to-end through the real SDK.
    action = await adapter.decide(_context())
    assert action.action == "stop"
    assert len(handler.captured_requests) == 1
    sent = handler.captured_requests[0]
    assert sent["model"] == "gpt-5.6-terra"
    assert sent["max_output_tokens"] == plan.max_output_tokens
    assert sent["reasoning"] == {"effort": "low"}
    assert adapter.provenance.provider_calls[0].provider_response_id == "resp_wiring_1"
    assert adapter.provenance.total_tokens == 11


def test_factory_wiring_regression_used_zero_outbound_sockets(monkeypatch):
    import asyncio

    handler = _OfflineMockHandler([STOP_RESPONSE_JSON])

    def _fake_build_openai_responses_client(*, timeout_seconds: float, max_retries: int):
        http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        client = openai.AsyncOpenAI(
            api_key="test-key-not-real-never-sent-anywhere",
            http_client=http_client,
            timeout=timeout_seconds,
            max_retries=max_retries,
        )
        return client.responses

    monkeypatch.setattr(
        real_host_adapter_module,
        "build_openai_responses_client",
        _fake_build_openai_responses_client,
    )

    def exploding_connect(self, address):
        raise AssertionError(f"regression test attempted a real socket connection to {address}")

    original_connect = socket.socket.connect
    socket.socket.connect = exploding_connect
    try:
        plan = cli.load_frozen_plan(model="gpt-5.6-terra")
        factory = cli.build_real_adapter_factory(plan)
        adapter = factory("live-influence-control#1", plan.max_decisions_per_trial)

        async def run():
            return await adapter.decide(_context())

        action = asyncio.run(run())
        assert action.action == "stop"
        assert len(handler.captured_requests) == 1
    finally:
        socket.socket.connect = original_connect
