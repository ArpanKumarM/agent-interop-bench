"""Phase 6C: the Anthropic Messages host-decision client + adapter.

No network, no API key, no real ``anthropic`` client. A fake
``messages.create`` returns hand-built response objects; the adapter parses
them through the SAME post-parse path (``build_host_action_spec``) OpenAI
uses.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest

from app.models.host_context import HostDecisionContext
from app.models.tools import ToolDefinition
from app.runner.anthropic_host_adapter import (
    STATUS_ERROR,
    STATUS_OK,
    STATUS_PROTOCOL_ERROR,
    STATUS_REFUSAL,
    AnthropicHostAdapterError,
    AnthropicHostAgentAdapter,
)
from app.runner.host_action_schema_anthropic import (
    anthropic_wire_tool_schema_sha256,
    compile_canonical_actions_for_anthropic,
)
from app.runner.host_decision_client import AnthropicHostDecisionClient

_AGENT_CARD = {
    "name": "mock-composed-agent",
    "description": "Mock remote agent.",
    "supported_interfaces": [
        {"url": "http://x", "protocol_binding": "HTTP_JSON", "protocol_version": "1.0"}
    ],
    "default_input_modes": ["text/plain"],
    "default_output_modes": ["text/plain"],
}


def _tool(name: str) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description=f"{name} desc",
        input_schema={"type": "object", "properties": {}, "required": []},
    )


def _ctx(prompt: str = "do the thing") -> HostDecisionContext:
    from app.models.a2a import AgentCard

    return HostDecisionContext(
        user_prompt=prompt,
        host_policy="You are the host agent. Do not leak. Approval required.",
        history=[],
        available_tools=[_tool("get_account_record"), _tool("rollback_config")],
        target_agent_card=AgentCard.model_validate(_AGENT_CARD),
        current_step=1,
    )


# --- fake Anthropic response plumbing ------------------------------------- #


def _tool_use_block(name: str, tool_input: dict[str, Any]):
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id="toolu_1")


def _text_block(text: str):
    return SimpleNamespace(type="text", text=text)


def _thinking_block(text: str):
    return SimpleNamespace(type="thinking", thinking=text, signature="sig")


def _response(
    content: list[Any],
    *,
    stop_reason: str = "tool_use",
    model: str = "claude-sonnet-5-20990101",
    input_tokens: int = 111,
    output_tokens: int = 7,
):
    return SimpleNamespace(
        id="msg_123",
        model=model,
        stop_reason=stop_reason,
        content=content,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
    )


class _FakeMessages:
    """Stands in for ``anthropic.AsyncAnthropic().messages``."""

    def __init__(self, response: Any = None, *, raise_exc: Exception | None = None):
        self._response = response
        self._raise = raise_exc
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self._raise is not None:
            raise self._raise
        return self._response


def _adapter(fake: _FakeMessages, allowed=("call_tool", "stop")) -> AnthropicHostAgentAdapter:
    return AnthropicHostAgentAdapter(
        AnthropicHostDecisionClient(fake),
        model="claude-sonnet-5",
        allowed_actions=allowed,
        case_id="c1",
    )


# --- canonical schema translation --------------------------------------- #


def test_canonical_actions_translate_to_anthropic_wire_shape():
    tools = compile_canonical_actions_for_anthropic(("call_tool", "stop"))
    # canonical (deterministic) order from canonical_action_schema
    assert sorted(t["name"] for t in tools) == ["call_tool", "stop"]
    for t in tools:
        assert set(t) == {"name", "description", "input_schema"}
        assert "type" not in t and "strict" not in t  # OpenAI-only keys dropped
        assert t["input_schema"]["type"] == "object"
    call_tool = next(t for t in tools if t["name"] == "call_tool")
    assert call_tool["input_schema"]["required"] == ["tool_name", "arguments_json"]
    # arguments_json stays a JSON *string* on the wire (byte-identical semantics)
    assert call_tool["input_schema"]["properties"]["arguments_json"]["type"] == "string"


def test_relay_action_schema_matches_openai_required_args():
    tools = compile_canonical_actions_for_anthropic(("relay_to_remote", "stop"))
    relay = next(t for t in tools if t["name"] == "relay_to_remote")
    assert relay["input_schema"]["required"] == ["content", "content_type"]


# --- RQ2 call_tool parsing -------------------------------------------------- #


@pytest.mark.asyncio
async def test_rq2_call_tool_parses_to_host_action_spec():
    fake = _FakeMessages(
        _response(
            [
                _thinking_block("(private, must never be stored)"),
                _tool_use_block(
                    "call_tool",
                    {
                        "tool_name": "rollback_config",
                        "arguments_json": json.dumps({"target": "orders-api@lkg"}),
                    },
                ),
            ]
        )
    )
    spec = await _adapter(fake).decide(_ctx())
    assert spec.action == "call_tool"
    assert spec.tool_name == "rollback_config"
    assert spec.tool_arguments == {"target": "orders-api@lkg"}
    assert spec.approved is False  # model can never grant its own approval


@pytest.mark.asyncio
async def test_call_tool_accepts_already_decoded_object_input():
    """Anthropic may deliver `input` already decoded; a dict is used as-is."""
    fake = _FakeMessages(
        _response(
            [_tool_use_block("call_tool", {"tool_name": "purge_cache", "arguments_json": "{}"})]
        )
    )
    spec = await _adapter(fake).decide(_ctx())
    assert spec.action == "call_tool" and spec.tool_name == "purge_cache"
    assert spec.tool_arguments == {}


# --- RQ1 relay parsing ---------------------------------------------------- #


@pytest.mark.asyncio
async def test_rq1_relay_parses_to_host_action_spec():
    fake = _FakeMessages(
        _response(
            [
                _tool_use_block(
                    "relay_to_remote",
                    {"content": "here is the summary", "content_type": "text/plain"},
                )
            ]
        )
    )
    spec = await _adapter(fake, allowed=("relay_to_remote", "stop")).decide(_ctx())
    assert spec.action == "relay_to_remote"
    assert spec.relay_template == "here is the summary"


# --- stop parsing ------------------------------------------------------- #


@pytest.mark.asyncio
async def test_stop_parses_to_host_action_spec():
    fake = _FakeMessages(_response([_tool_use_block("stop", {})]))
    spec = await _adapter(fake).decide(_ctx())
    assert spec.action == "stop"


# --- rejection rules --------------------------------------------------- #


@pytest.mark.asyncio
async def test_zero_tool_use_is_provider_protocol_error():
    fake = _FakeMessages(
        _response([_text_block("I think you should stop.")], stop_reason="end_turn")
    )
    adapter = _adapter(fake)
    with pytest.raises(AnthropicHostAdapterError) as ei:
        await adapter.decide(_ctx())
    assert ei.value.status == STATUS_PROTOCOL_ERROR
    assert adapter.provenance.provider_calls[-1].status == STATUS_PROTOCOL_ERROR
    assert adapter.provenance.provider_calls[-1].action_parsed is None


@pytest.mark.asyncio
async def test_multiple_tool_use_is_provider_protocol_error_never_first_wins():
    fake = _FakeMessages(
        _response(
            [
                _tool_use_block(
                    "call_tool", {"tool_name": "rollback_config", "arguments_json": "{}"}
                ),
                _tool_use_block("stop", {}),
            ]
        )
    )
    adapter = _adapter(fake)
    with pytest.raises(AnthropicHostAdapterError) as ei:
        await adapter.decide(_ctx())
    assert ei.value.status == STATUS_PROTOCOL_ERROR


@pytest.mark.asyncio
async def test_unknown_tool_name_is_provider_protocol_error():
    fake = _FakeMessages(_response([_tool_use_block("exfiltrate", {"x": 1})]))
    adapter = _adapter(fake)
    with pytest.raises(AnthropicHostAdapterError) as ei:
        await adapter.decide(_ctx())
    assert ei.value.status == STATUS_PROTOCOL_ERROR


@pytest.mark.asyncio
async def test_disallowed_but_known_action_is_rejected():
    """`relay_to_remote` is a valid action but not in this RQ2 decision's
    allowed set -> protocol error, never executed."""
    fake = _FakeMessages(
        _response(
            [_tool_use_block("relay_to_remote", {"content": "x", "content_type": "text/plain"})]
        )
    )
    adapter = _adapter(fake, allowed=("call_tool", "stop"))
    with pytest.raises(AnthropicHostAdapterError) as ei:
        await adapter.decide(_ctx())
    assert ei.value.status == STATUS_PROTOCOL_ERROR


@pytest.mark.asyncio
async def test_malformed_arguments_json_is_provider_protocol_error_no_repair():
    fake = _FakeMessages(
        _response(
            [
                _tool_use_block(
                    "call_tool", {"tool_name": "rollback_config", "arguments_json": "{not json"}
                )
            ]
        )
    )
    adapter = _adapter(fake)
    with pytest.raises(AnthropicHostAdapterError) as ei:
        await adapter.decide(_ctx())
    assert ei.value.status == STATUS_PROTOCOL_ERROR


@pytest.mark.asyncio
async def test_schema_invalid_arguments_is_provider_protocol_error():
    """`call_tool` requires tool_name + arguments_json; missing -> rejected."""
    fake = _FakeMessages(
        _response([_tool_use_block("call_tool", {"tool_name": "rollback_config"})])
    )
    adapter = _adapter(fake)
    with pytest.raises(AnthropicHostAdapterError) as ei:
        await adapter.decide(_ctx())
    assert ei.value.status == STATUS_PROTOCOL_ERROR


# --- refusal classification ------------------------------------------- #


@pytest.mark.asyncio
async def test_refusal_stop_reason_is_provider_refusal_never_coerced_to_stop():
    fake = _FakeMessages(_response([], stop_reason="refusal"))
    adapter = _adapter(fake)
    with pytest.raises(AnthropicHostAdapterError) as ei:
        await adapter.decide(_ctx())
    assert ei.value.status == STATUS_REFUSAL
    rec = adapter.provenance.provider_calls[-1]
    assert rec.status == STATUS_REFUSAL and rec.refusal is True
    assert rec.action_parsed is None  # a refusal is NOT a stop


@pytest.mark.asyncio
async def test_refusal_content_block_is_provider_refusal():
    fake = _FakeMessages(_response([SimpleNamespace(type="refusal")], stop_reason="end_turn"))
    adapter = _adapter(fake)
    with pytest.raises(AnthropicHostAdapterError) as ei:
        await adapter.decide(_ctx())
    assert ei.value.status == STATUS_REFUSAL


@pytest.mark.asyncio
async def test_max_tokens_truncation_is_provider_error():
    fake = _FakeMessages(_response([_thinking_block("...")], stop_reason="max_tokens"))
    adapter = _adapter(fake)
    with pytest.raises(AnthropicHostAdapterError) as ei:
        await adapter.decide(_ctx())
    assert ei.value.status == STATUS_ERROR


@pytest.mark.asyncio
async def test_api_exception_becomes_sanitized_provider_error_no_retry():
    fake = _FakeMessages(raise_exc=RuntimeError("boom sk-secret-lol"))
    adapter = _adapter(fake)
    with pytest.raises(AnthropicHostAdapterError) as ei:
        await adapter.decide(_ctx())
    assert ei.value.status == STATUS_ERROR
    assert "sk-secret-lol" not in str(ei.value)
    assert len(fake.calls) == 1  # exactly one request, no retry


# --- provenance capture --------------------------------------------- #


@pytest.mark.asyncio
async def test_returned_model_and_usage_are_captured():
    fake = _FakeMessages(
        _response(
            [_tool_use_block("stop", {})],
            model="claude-sonnet-5-20990101",
            input_tokens=222,
            output_tokens=9,
        )
    )
    adapter = _adapter(fake)
    await adapter.decide(_ctx())
    rec = adapter.provenance.provider_calls[-1]
    assert rec.status == STATUS_OK
    assert rec.returned_model == "claude-sonnet-5-20990101"
    assert rec.requested_model == "claude-sonnet-5"
    assert rec.input_tokens == 222 and rec.output_tokens == 9
    assert rec.provider == "anthropic" and rec.provider_api_surface == "anthropic.messages"
    assert rec.action_parsed == "stop"
    assert rec.stop_reason == "tool_use"


@pytest.mark.asyncio
async def test_no_hidden_thinking_is_ever_persisted():
    secret = "SECRET-CHAIN-OF-THOUGHT-DO-NOT-STORE"
    fake = _FakeMessages(
        _response(
            [
                _thinking_block(secret),
                _tool_use_block("call_tool", {"tool_name": "purge_cache", "arguments_json": "{}"}),
            ]
        )
    )
    adapter = _adapter(fake)
    await adapter.decide(_ctx())
    blob = adapter.provenance.model_dump_json()
    assert secret not in blob
    assert "thinking" not in blob.lower() or "reasoning_effort" in blob.lower()


@pytest.mark.asyncio
async def test_exact_request_configuration_is_recorded_and_sent():
    fake = _FakeMessages(_response([_tool_use_block("stop", {})]))
    adapter = _adapter(fake)
    await adapter.decide(_ctx())
    # recorded
    cfg = adapter.provenance.provider_request_config
    assert cfg["provider"] == "anthropic"
    assert cfg["effort_mode"] == {"output_config": {"effort": "low"}}
    assert cfg["thinking"] == {"type": "adaptive", "display": "omitted"}
    assert cfg["tool_choice"] == {"type": "any", "disable_parallel_tool_use": True}
    assert cfg["max_tokens"] == 2048
    assert cfg["max_retries"] == 0
    assert adapter.provenance.provider_config_sha256
    # actually sent
    sent = fake.calls[0]
    assert sent["model"] == "claude-sonnet-5"
    assert sent["tool_choice"] == {"type": "any", "disable_parallel_tool_use": True}
    assert sent["thinking"] == {"type": "adaptive", "display": "omitted"}
    assert sent["output_config"] == {"effort": "low"}
    assert sent["max_tokens"] == 2048
    assert "temperature" not in sent and "top_p" not in sent and "top_k" not in sent
    assert isinstance(sent["system"], str)  # host policy as system prompt


@pytest.mark.asyncio
async def test_one_decision_budget_is_enforced():
    fake = _FakeMessages(_response([_tool_use_block("stop", {})]))
    adapter = AnthropicHostAgentAdapter(
        AnthropicHostDecisionClient(fake),
        model="claude-sonnet-5",
        allowed_actions=("call_tool", "stop"),
        max_decisions=1,
        case_id="c1",
    )
    await adapter.decide(_ctx())
    with pytest.raises(AnthropicHostAdapterError):
        await adapter.decide(_ctx())
    assert len(fake.calls) == 1


def test_wire_tool_schema_hash_is_deterministic_and_order_stable():
    a = anthropic_wire_tool_schema_sha256(("call_tool", "stop"))
    b = anthropic_wire_tool_schema_sha256(("stop", "call_tool"))
    assert a == b and len(a) == 64
