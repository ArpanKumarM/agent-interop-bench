"""Provider-neutral host-decision seam (Phase 6B).

``HostDecisionClient`` is the one interface a ``HostAgentAdapter`` needs to
talk to *any* model provider: compile the single canonical action schema
(``call_tool`` / ``stop`` -- see
``app.runner.host_action_schema_openai.canonical_action_schema``) into that
provider's tool-use format, issue one decision request, and parse the
returned tool call back into a ``(name, arguments_dict)`` pair.

Only the OpenAI implementation exists today
(``OpenAIHostDecisionClient``), and it is a thin wrapper over the exact
logic ``RealHostAgentAdapter`` already used -- current OpenAI behaviour is
byte-for-byte preserved. A second (non-OpenAI) implementation is added
*after* the core Phase 6B implementation passes; its model id is not
frozen here.

This module never imports ``openai`` at module load; the OpenAI client is
built lazily via ``app.runner.openai_adapter.build_openai_responses_client``.
"""

from __future__ import annotations

import json
from typing import Any, Protocol


class HostDecisionRequest(Protocol):
    """The provider-agnostic shape of one decision request."""

    instructions: str
    input_payload: dict[str, Any]
    canonical_actions: tuple[str, ...]
    max_output_tokens: int
    reasoning_effort: str


class ParsedToolCall:
    """One parsed provider tool call: an action name and a decoded argument
    object. The adapter maps this to a ``HostActionSpec``."""

    __slots__ = ("name", "arguments")

    def __init__(self, name: str, arguments: dict[str, Any]) -> None:
        self.name = name
        self.arguments = arguments


class HostDecisionClient(Protocol):
    """What a ``HostAgentAdapter`` calls, regardless of provider."""

    provider: str

    def compile_action_schema(self, canonical_actions: tuple[str, ...]) -> list[dict[str, Any]]:
        """Return the provider-specific tool schema for exactly
        ``canonical_actions`` (a subset of the canonical action surface)."""
        ...

    async def decide(
        self,
        *,
        model: str,
        instructions: str,
        input_payload: dict[str, Any],
        canonical_actions: tuple[str, ...],
        max_output_tokens: int,
        reasoning_effort: str,
    ) -> Any:
        """Issue one decision request and return the raw provider response
        object (the adapter records provenance and parses it)."""
        ...

    def parse_tool_call(self, response: Any) -> ParsedToolCall: ...


class OpenAIHostDecisionClient:
    """OpenAI Responses API implementation. Wraps the same ``ResponsesClient``
    call and the same strict-schema tool list ``RealHostAgentAdapter`` used
    before Phase 6B; no behaviour change for OpenAI."""

    provider = "openai"

    def __init__(self, responses_client: Any) -> None:
        self._client = responses_client

    def compile_action_schema(self, canonical_actions: tuple[str, ...]) -> list[dict[str, Any]]:
        from app.runner.host_action_schema_openai import canonical_action_schema

        return canonical_action_schema(canonical_actions)

    async def decide(
        self,
        *,
        model: str,
        instructions: str,
        input_payload: dict[str, Any],
        canonical_actions: tuple[str, ...],
        max_output_tokens: int,
        reasoning_effort: str,
    ) -> Any:
        import json

        tools = self.compile_action_schema(canonical_actions)
        return await self._client.create(
            model=model,
            instructions=instructions,
            input=[
                {"role": "user", "content": json.dumps(input_payload, default=str, sort_keys=True)}
            ],
            tools=tools,
            tool_choice="required",
            parallel_tool_calls=False,
            max_output_tokens=max_output_tokens,
            reasoning={"effort": reasoning_effort},
        )

    def parse_tool_call(self, response: Any) -> ParsedToolCall:
        import json

        output = getattr(response, "output", []) or []
        function_calls = [item for item in output if getattr(item, "type", None) == "function_call"]
        if len(function_calls) != 1:
            raise ValueError(f"expected exactly one function call, got {len(function_calls)}")
        call = function_calls[0]
        name = getattr(call, "name", None) or ""
        raw = getattr(call, "arguments", None) or "{}"
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError(f"non-object arguments for {name!r}: {type(parsed).__name__}")
        return ParsedToolCall(name=name, arguments=parsed)


def build_openai_host_decision_client(
    *, timeout_seconds: float, max_retries: int = 0
) -> OpenAIHostDecisionClient:
    """Lazily build the OpenAI ``HostDecisionClient``. Requires the ``openai``
    extra + ``OPENAI_API_KEY``; never imported for a deterministic run."""
    from app.runner.openai_adapter import build_openai_responses_client

    client = build_openai_responses_client(timeout_seconds=timeout_seconds, max_retries=max_retries)
    return OpenAIHostDecisionClient(client)


class AnthropicRefusalError(RuntimeError):
    """The Anthropic model explicitly refused (``stop_reason == "refusal"``
    or a refusal content block). Distinct from a protocol error so the
    caller can record the pre-registered ``provider_refusal`` status."""


class AnthropicProtocolError(RuntimeError):
    """The Anthropic response did not contain exactly one usable tool call
    (zero tool_use blocks, more than one, an unknown tool, or malformed
    arguments) -- the pre-registered ``provider_protocol_error`` status."""


class AnthropicHostDecisionClient:
    """Anthropic Messages API implementation of ``HostDecisionClient``.

    Compiles the SAME canonical action schema
    (``call_tool``/``relay_to_remote``/``stop``) to Anthropic's tool format,
    issues exactly one Messages request in the provider's low-effort mode
    (``output_config.effort = "low"`` + adaptive thinking), forces one tool
    call (``tool_choice = {"type": "any", "disable_parallel_tool_use":
    true}``), and parses exactly one ``tool_use`` block back into a
    ``ParsedToolCall``. The adapter maps that through the shared
    ``build_host_action_spec`` -- so the resulting ``HostDecision`` is
    byte-identical to OpenAI's for the same decision.

    No chain-of-thought is ever read: only ``tool_use`` blocks are
    inspected; ``thinking`` / ``redacted_thinking`` blocks are ignored and
    never stored.
    """

    provider = "anthropic"

    def __init__(self, messages_client: Any) -> None:
        self._client = messages_client

    def compile_action_schema(self, canonical_actions: tuple[str, ...]) -> list[dict[str, Any]]:
        from app.runner.host_action_schema_anthropic import compile_canonical_actions_for_anthropic

        return compile_canonical_actions_for_anthropic(canonical_actions)

    async def decide(
        self,
        *,
        model: str,
        instructions: str,
        input_payload: dict[str, Any],
        canonical_actions: tuple[str, ...],
        max_output_tokens: int,
        reasoning_effort: str,
    ) -> Any:
        import json

        from app.runner.model_panel import (
            ANTHROPIC_THINKING,
            ANTHROPIC_TOOL_CHOICE,
        )

        tools = self.compile_action_schema(canonical_actions)
        return await self._client.create(
            model=model,
            system=instructions,
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(input_payload, default=str, sort_keys=True),
                }
            ],
            tools=tools,
            tool_choice=dict(ANTHROPIC_TOOL_CHOICE),
            thinking=dict(ANTHROPIC_THINKING),
            output_config={"effort": reasoning_effort},
            max_tokens=max_output_tokens,
        )

    @staticmethod
    def response_stop_reason(response: Any) -> str | None:
        return getattr(response, "stop_reason", None)

    @staticmethod
    def is_refusal(response: Any) -> bool:
        if getattr(response, "stop_reason", None) == "refusal":
            return True
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", None) == "refusal":
                return True
        return False

    def parse_tool_call(self, response: Any) -> ParsedToolCall:
        content = getattr(response, "content", []) or []
        tool_uses = [b for b in content if getattr(b, "type", None) == "tool_use"]
        if len(tool_uses) != 1:
            raise AnthropicProtocolError(
                f"expected exactly one tool_use block, got {len(tool_uses)}"
            )
        block = tool_uses[0]
        name = getattr(block, "name", None) or ""
        raw_input = getattr(block, "input", None)
        # Anthropic delivers tool input as an already-decoded object. The
        # canonical schema still declares arguments_json as a JSON *string*
        # (byte-identical semantics with OpenAI), so accept either: a dict
        # is used as-is; a str must decode to a dict.
        if isinstance(raw_input, dict):
            parsed: Any = raw_input
        elif isinstance(raw_input, str):
            try:
                parsed = json.loads(raw_input)
            except json.JSONDecodeError as exc:
                raise AnthropicProtocolError(
                    f"tool_use input for {name!r} is not valid JSON: {exc}"
                ) from None
        else:
            raise AnthropicProtocolError(
                f"tool_use input for {name!r} is {type(raw_input).__name__}, expected object"
            )
        if not isinstance(parsed, dict):
            raise AnthropicProtocolError(
                f"non-object tool_use input for {name!r}: {type(parsed).__name__}"
            )
        return ParsedToolCall(name=name, arguments=parsed)


def build_anthropic_host_decision_client(
    *, timeout_seconds: float, max_retries: int = 0
) -> AnthropicHostDecisionClient:
    """Lazily build the Anthropic ``HostDecisionClient``. Requires the
    ``anthropic`` extra + ``ANTHROPIC_API_KEY``; never imported for a
    deterministic run, a preflight, or a test."""
    from app.runner.anthropic_adapter import build_anthropic_messages_client

    client = build_anthropic_messages_client(
        timeout_seconds=timeout_seconds, max_retries=max_retries
    )
    return AnthropicHostDecisionClient(client)


__all__ = [
    "AnthropicHostDecisionClient",
    "AnthropicProtocolError",
    "AnthropicRefusalError",
    "HostDecisionClient",
    "OpenAIHostDecisionClient",
    "ParsedToolCall",
    "build_anthropic_host_decision_client",
    "build_openai_host_decision_client",
]
