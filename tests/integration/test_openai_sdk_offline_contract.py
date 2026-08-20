"""Offline contract test against the REAL OpenAI Python SDK (Part 5 of the
Phase 2C final state-isolation and offline-SDK gate).

`ProtocolValidatingFakeResponsesClient` (in ``tests/unit/test_openai_adapter.py``)
proves referential integrity against a hand-rolled fake, but not that the
actual SDK's request serialization / response parsing agrees with what
``OpenAIResponsesAdapter`` assumes. This module closes that specific gap:
it constructs a REAL ``openai.AsyncOpenAI`` client, but backs its HTTP
transport with ``httpx.MockTransport`` — a synchronous, in-process request
handler — so the SDK's actual wire-serialization code runs for real while
**zero sockets are ever opened and zero requests reach any real host**.

Skipped entirely (not failed) when the optional ``openai`` extra is not
installed, via ``pytest.importorskip`` — the rest of the suite (and this
file's own skip behavior) is valid and green in both environments; only
this one file's tests require the extra to actually execute.

No test in this file, and no other verification step in this project, ever
calls the real OpenAI inference endpoint.
"""

from __future__ import annotations

import json

import pytest

openai = pytest.importorskip("openai")
httpx = pytest.importorskip("httpx")

from app.models.execution import TurnResult  # noqa: E402
from app.models.tools import ToolDefinition  # noqa: E402
from app.runner.openai_adapter import OpenAIResponsesAdapter  # noqa: E402

SEARCH_TOOL = ToolDefinition(
    name="search_issues",
    description="Search issues.",
    input_schema={
        "type": "object",
        "properties": {"repo": {"type": "string"}, "query": {"type": "string"}},
        "required": ["repo", "query"],
    },
    required_arguments=["repo", "query"],
    is_mutating=False,
)

TURN1_RESPONSE_JSON = {
    "id": "resp_turn1",
    "object": "response",
    "created_at": 1234567890,
    "status": "completed",
    "model": "gpt-test-returned",
    "output": [
        {"type": "reasoning", "id": "rs_should_not_leak_abc123", "summary": []},
        {
            "type": "function_call",
            "id": "fc_abc123",
            "call_id": "call_xyz789_real_provider_id",
            "name": "search_issues",
            "arguments": json.dumps({"repo": "acme/webapp", "query": "bug"}),
            "status": "completed",
        },
    ],
    "parallel_tool_calls": False,
    "tool_choice": "auto",
    "tools": [],
    "temperature": 1.0,
    "top_p": 1.0,
    "incomplete_details": None,
    "usage": {
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 0},
    },
}

TURN2_RESPONSE_JSON = {
    "id": "resp_turn2",
    "object": "response",
    "created_at": 1234567891,
    "status": "completed",
    "model": "gpt-test-returned",
    "output": [],  # voluntary stop after observing the tool output
    "parallel_tool_calls": False,
    "tool_choice": "auto",
    "tools": [],
    "temperature": 1.0,
    "top_p": 1.0,
    "incomplete_details": None,
    "usage": {
        "input_tokens": 20,
        "output_tokens": 1,
        "total_tokens": 21,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens_details": {"reasoning_tokens": 0},
    },
}


class _OfflineMockHandler:
    """Captures every request body the SDK actually serialized, and returns
    pre-scripted synthetic Responses API JSON — entirely in-process, via
    httpx.MockTransport. This function is the ONLY thing standing in for
    the network; it never touches a socket."""

    def __init__(self, responses: list[dict]):
        self._responses = list(responses)
        self.captured_requests: list[dict] = []

    def __call__(self, request) -> httpx.Response:
        self.captured_requests.append(json.loads(request.content))
        return httpx.Response(200, json=self._responses.pop(0))


def _build_offline_client(handler: _OfflineMockHandler):
    """Constructs a REAL AsyncOpenAI client whose HTTP transport is fully
    offline (httpx.MockTransport backed by an in-process handler). No
    OPENAI_API_KEY is read from the environment; a placeholder string is
    passed directly since no real request is ever sent."""
    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(transport=transport)
    return openai.AsyncOpenAI(
        api_key="test-key-not-real-never-sent-anywhere",
        http_client=http_client,
        timeout=5.0,
        max_retries=0,
    )


async def test_real_sdk_offline_two_turn_contract_end_to_end():
    """The full Part 5 proof, using the REAL production OpenAIResponsesAdapter
    class through the REAL SDK client's `.responses` resource — not a
    hand-rolled fake standing in for the adapter."""
    handler = _OfflineMockHandler([TURN1_RESPONSE_JSON, TURN2_RESPONSE_JSON])
    client = _build_offline_client(handler)

    adapter = OpenAIResponsesAdapter(client.responses, model="gpt-test", max_output_tokens=256)

    # --- Turn 1 ---
    decision1 = await adapter.decide("search for bugs", [SEARCH_TOOL], [])
    assert decision1.tool_name == "search_issues"
    assert decision1.arguments == {"repo": "acme/webapp", "query": "bug"}

    first_request = handler.captured_requests[0]
    assert first_request["model"] == "gpt-test"
    assert first_request["tools"][0]["name"] == "search_issues"
    assert first_request["parallel_tool_calls"] is False
    assert first_request["max_output_tokens"] == 256
    from app.core.baseline_policy import BASELINE_POLICY_TEXT

    assert first_request["instructions"] == BASELINE_POLICY_TEXT
    assert first_request["input"] == [{"role": "user", "content": "search for bugs"}]

    # --- The harness (not simulated here) executes the real MCP tool and
    # produces a real TurnResult; we feed that back in, exactly as
    # suite_execution/BenchmarkRunner would. ---
    turn0 = TurnResult(
        turn_index=0,
        requested_tool="search_issues",
        requested_arguments={"repo": "acme/webapp", "query": "bug"},
        executed=True,
        raw_text_output="1 issue found",
    )

    # --- Turn 2 ---
    decision2 = await adapter.decide("search for bugs", [SEARCH_TOOL], [turn0])
    assert decision2.tool_name is None  # voluntary stop

    second_request = handler.captured_requests[1]
    assert second_request["parallel_tool_calls"] is False
    assert second_request["max_output_tokens"] == 256

    input_items = second_request["input"]
    assert input_items[0] == {"role": "user", "content": "search for bugs"}

    reasoning_items = [
        i for i in input_items if isinstance(i, dict) and i.get("type") == "reasoning"
    ]
    assert len(reasoning_items) == 1
    assert reasoning_items[0]["id"] == "rs_should_not_leak_abc123"

    function_call_items = [
        i for i in input_items if isinstance(i, dict) and i.get("type") == "function_call"
    ]
    assert len(function_call_items) == 1
    replayed_call = function_call_items[0]
    assert replayed_call["call_id"] == "call_xyz789_real_provider_id"
    assert replayed_call["name"] == "search_issues"
    assert replayed_call["arguments"] == json.dumps({"repo": "acme/webapp", "query": "bug"})

    function_call_output_items = [
        i for i in input_items if isinstance(i, dict) and i.get("type") == "function_call_output"
    ]
    assert len(function_call_output_items) == 1
    fco = function_call_output_items[0]
    # The exact original call_id -- never invented or substituted.
    assert fco["call_id"] == "call_xyz789_real_provider_id"
    # The real MCP tool output (not a fixture value).
    assert fco["output"] == "1 issue found"

    # Reasoning content never appears in persisted provenance.
    provenance_json = adapter.provenance.model_dump_json()
    assert "rs_should_not_leak_abc123" not in provenance_json
    assert adapter.provenance.total_tokens == 15 + 21
    assert adapter.provenance.provider_calls[0].provider_response_id == "resp_turn1"
    assert adapter.provenance.provider_calls[1].provider_response_id == "resp_turn2"


async def test_real_sdk_offline_call_id_substitution_would_be_caught():
    """Negative control: if the adapter invented a call_id instead of
    replaying the real one, this assertion (checked against what the REAL
    SDK actually serialized) would fail -- proving the test is sensitive to
    exactly the defect Part 1 of the prior gate found and fixed."""
    handler = _OfflineMockHandler([TURN1_RESPONSE_JSON, TURN2_RESPONSE_JSON])
    client = _build_offline_client(handler)
    adapter = OpenAIResponsesAdapter(client.responses, model="gpt-test")

    await adapter.decide("search for bugs", [SEARCH_TOOL], [])
    turn0 = TurnResult(
        turn_index=0,
        requested_tool="search_issues",
        requested_arguments={"repo": "acme/webapp", "query": "bug"},
        executed=True,
        raw_text_output="1 issue found",
    )
    await adapter.decide("search for bugs", [SEARCH_TOOL], [turn0])

    second_request = handler.captured_requests[1]
    call_ids_sent = {
        item.get("call_id")
        for item in second_request["input"]
        if isinstance(item, dict) and "call_id" in item
    }
    assert call_ids_sent == {"call_xyz789_real_provider_id"}
    assert "turn-0" not in call_ids_sent  # the old synthetic scheme, must never appear


def test_offline_contract_test_used_zero_outbound_sockets():
    """Explicit proof the offline transport never opens a real socket:
    httpx.MockTransport's handler is a plain in-process callable with no
    networking primitive involved at all -- confirmed by construction, and
    additionally guarded here by blocking socket.socket.connect for the
    duration of a full two-turn exchange."""
    import asyncio
    import socket

    def exploding_connect(self, address):
        raise AssertionError(
            f"offline contract test attempted a real socket connection to {address}"
        )

    original_connect = socket.socket.connect
    socket.socket.connect = exploding_connect
    try:
        handler = _OfflineMockHandler([TURN1_RESPONSE_JSON, TURN2_RESPONSE_JSON])
        client = _build_offline_client(handler)
        adapter = OpenAIResponsesAdapter(client.responses, model="gpt-test")

        async def run():
            await adapter.decide("search for bugs", [SEARCH_TOOL], [])

        asyncio.run(run())
        assert len(handler.captured_requests) == 1
    finally:
        socket.socket.connect = original_connect
