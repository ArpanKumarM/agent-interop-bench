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


__all__ = [
    "HostDecisionClient",
    "OpenAIHostDecisionClient",
    "ParsedToolCall",
    "build_openai_host_decision_client",
]
