"""OpenAIResponsesAdapter: an AgentAdapter backed by a real OpenAI model via
the Responses API. Optional — requires the ``openai`` extra to be installed
and ``OPENAI_API_KEY`` to be set. Never constructed for a deterministic run.

Architecture: this adapter is a pure translator between the project's
provider-neutral ``AgentAdapter`` contract and OpenAI's Responses API. It
never touches MCP transport, never executes a tool itself, and never
changes what ``BenchmarkRunner`` does with the ``ToolCallDecision`` it
returns — the same mutation safety gate, argument validation, and
evaluators apply exactly as they do for ``DeterministicFakeAdapter``. A
model can *propose* a dangerous mutation; only ``BenchmarkRunner``'s
existing, model-independent safety gate decides whether it executes.

Protocol fidelity — provider conversation state: the Responses API
correlates a ``function_call_output`` with its ``function_call`` via an
opaque, provider-issued ``call_id`` (and, for reasoning models, further
opaque reasoning items must be replayed verbatim between turns — see
OpenAI's function-calling guide's ``input_list += response.output``
pattern). This adapter therefore is NOT fully stateless across a case's
turns: it caches each turn's raw ``response.output`` items internally
(``_provider_output_by_turn``, reset by ``bind_case`` at each case
boundary) and replays them verbatim on the next request, rather than
reconstructing a synthetic function-call item with an invented call_id.
This state is opaque, provider-internal, and never exposed as scientific
tool behavior: it never touches ``TurnResult``, never gets logged, and is
discarded at the next case boundary. The *content* an adapter reasons
about (the tool's actual output, including any prompt-injection payload)
still comes only from the real ``TurnResult`` the runner produced — never
from a deterministic fixture, which ``TurnResult`` has no field for anyway.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import re
from typing import Any, Protocol

from app.core.baseline_policy import (
    BASELINE_POLICY_SHA256,
    BASELINE_POLICY_TEXT,
    BASELINE_POLICY_VERSION,
)
from app.models.execution import ToolCallDecision, TurnResult
from app.models.provenance import ModelRunProvenance, ProviderCallRecord
from app.models.tools import ToolDefinition
from app.runner.adapters import AgentAdapter
from app.runner.tool_schema_openai import translate_tools_for_openai

logger = logging.getLogger("agent_interop_bench.openai_adapter")

DEFAULT_MAX_OUTPUT_TOKENS = 256
DEFAULT_TIMEOUT_SECONDS = 30.0
# The OpenAI Python SDK defaults to internally retrying failed requests
# (timeouts, 5xx, 429) up to 2 times before an error ever reaches this
# adapter. Phase 2C wants one benchmark turn == one intentional, observable
# provider request: predictable call counts, predictable spend, no hidden
# extra paid attempts. See build_openai_responses_client.
DEFAULT_MAX_RETRIES = 0

# Redacts anything shaped like a credential from a provider exception's
# message before it is ever stored, logged, or returned. This is
# belt-and-suspenders on top of `from None` exception-chain suppression
# below — the actual security boundary does not rely on a third-party SDK's
# current exception-string behavior; see _sanitize_provider_error.
_SENSITIVE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{10,}"),
    re.compile(r"Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"Authorization\s*:\s*\S+(?:\s+\S+)?", re.IGNORECASE),
)


def openai_sdk_available() -> bool:
    """Whether the optional ``openai`` package is importable.

    A directly monkeypatchable seam — API-layer precondition tests inject
    this rather than depending on whether the optional extra happens to be
    installed in the environment the test suite runs in, so the suite is
    valid regardless of that installation state (see Part 5 of the Phase 2C
    hardening audit).
    """
    return importlib.util.find_spec("openai") is not None


class OpenAIAdapterError(RuntimeError):
    """A controlled adapter-level failure: provider error, an unexpected
    multiple-tool-call response, an incomplete response (e.g. truncated by
    ``max_output_tokens``), or unparseable tool-call arguments.

    Message text is always sanitized (see ``_sanitize_provider_error``) —
    never contains an API key, an Authorization header, or raw SDK debug
    data. Raised with exception chaining suppressed (``from None``): the
    original provider exception is deliberately not attached as ``__cause__``,
    so nothing downstream (including ``RunManager``'s ``logger.exception``,
    which would otherwise walk the chain and print the original exception's
    own, unsanitized message/traceback) can leak whatever a third-party SDK
    happened to put in its own exception text. This propagates out of
    ``decide()`` uncaught by design: the existing execution chain
    (``BenchmarkRunner`` -> ``execute_suite`` -> ``RunManager._execute``'s
    existing exception handling) already converts any adapter exception into
    a cleanly recorded ``FAILED`` run with a sanitized error message — the
    same path a buggy deterministic fixture would already hit today. No
    runner change was needed for this.
    """


class ResponsesClient(Protocol):
    """The minimal surface of ``openai.AsyncOpenAI().responses`` this
    adapter needs, expressed as a ``Protocol`` so tests can inject a fake
    without ever importing or depending on the real ``openai`` package."""

    async def create(self, **kwargs: Any) -> Any: ...


_MESSAGE_EXCERPT_LIMIT = 200


def _sanitize_provider_error(exc: Exception) -> str:
    """A traceback-free, bounded error string safe to store, log, or return
    over the API.

    Built from an allow-list of known-safe fields, not by treating the raw
    ``str(exc)`` as a security boundary: a third-party SDK's exception text
    is not something this project controls, and a future SDK version could
    in principle include more than a human-readable message (e.g. request
    metadata) in it. The result always leads with the exception's type name;
    ``status_code``/``request_id`` attributes are included only if the
    exception actually exposes them (the SDK's ``APIStatusError`` family
    does); the free-text message is included only as a *bounded, redacted
    excerpt* (``_MESSAGE_EXCERPT_LIMIT`` chars), never open-ended — this
    project does not claim the redaction patterns below are an exhaustive,
    mathematically complete secret scanner, so boundedness is the actual
    safety property being relied on, not pattern-matching alone.
    """
    parts = [type(exc).__name__]

    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        parts.append(f"status={status_code}")

    request_id = getattr(exc, "request_id", None)
    if isinstance(request_id, str) and request_id:
        parts.append(f"request_id={request_id}")

    message = str(exc)
    for pattern in _SENSITIVE_PATTERNS:
        message = pattern.sub("[REDACTED]", message)
    message = message.strip()
    if message:
        parts.append(message[:_MESSAGE_EXCERPT_LIMIT])

    return " ".join(parts)


class OpenAIResponsesAdapter(AgentAdapter):
    """Real-model ``AgentAdapter`` using OpenAI's Responses API."""

    def __init__(
        self,
        client: ResponsesClient,
        model: str,
        *,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        tool_schema_sha256: str = "",
    ) -> None:
        self._client = client
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._current_case_id: str | None = None
        # Provider-issued output items (function_call, and any opaque
        # reasoning items) keyed by the turn index that produced them —
        # replayed verbatim on the following request so the provider's own
        # call_id correlation (and, for reasoning models, continuity) is
        # preserved exactly. Reset per case by bind_case(). Never inspected
        # for content, never logged, never exposed outside this adapter.
        self._provider_output_by_turn: dict[int, list[Any]] = {}
        self.provenance = ModelRunProvenance(
            adapter_type="openai_responses",
            provider="openai",
            requested_model=model,
            baseline_policy_version=BASELINE_POLICY_VERSION,
            baseline_policy_sha256=BASELINE_POLICY_SHA256,
            tool_schema_sha256=tool_schema_sha256,
            configured_timeout_seconds=timeout_seconds,
            configured_max_retries=max_retries,
            configured_max_output_tokens=max_output_tokens,
        )

    def bind_case(self, case_id: str) -> None:
        """Tells the adapter which case's provider calls to attribute in
        provenance, and resets the per-case provider-conversation-state
        cache. Called by suite_execution before each case; never affects
        prompt/tool/policy content sent to the provider."""
        self._current_case_id = case_id
        self._provider_output_by_turn = {}

    async def decide(
        self,
        prompt: str,
        available_tools: list[ToolDefinition],
        history: list[TurnResult],
    ) -> ToolCallDecision:
        input_list = self._build_input_list(prompt, history)
        tools = translate_tools_for_openai(available_tools)
        turn_index = len(history)

        try:
            response = await self._client.create(
                model=self._model,
                instructions=BASELINE_POLICY_TEXT,
                input=input_list,
                tools=tools,
                tool_choice="auto",
                parallel_tool_calls=False,
                max_output_tokens=self._max_output_tokens,
            )
        except Exception as exc:  # noqa: BLE001 - deliberately broad: ANY provider
            # failure (timeout, rate limit, API error, connection error) must
            # become one controlled, sanitized adapter error, never an
            # unhandled raw SDK exception.
            sanitized = _sanitize_provider_error(exc)
            self._record_call(status="error", error=sanitized)
            raise OpenAIAdapterError(f"OpenAI request failed: {sanitized}") from None

        return self._handle_response(response, turn_index)

    def _build_input_list(self, prompt: str, history: list[TurnResult]) -> list[Any]:
        """Reconstructs the OpenAI Responses ``input`` list.

        The first item is always the benchmark prompt. Every prior turn is
        represented by replaying that turn's *actual* cached provider output
        items verbatim (see ``_provider_output_by_turn`` — this preserves
        the real ``call_id`` and any reasoning items exactly as OpenAI's own
        function-calling guide's ``input_list += response.output`` pattern
        does), followed by a ``function_call_output`` whose ``call_id``
        matches that real function_call item and whose ``output`` is the
        turn's *actual observed* tool output (``raw_text_output``, falling
        back to ``error``) — including any prompt-injection payload text a
        tool returned — never a scripted fixture value, and never a
        synthetic/invented call_id.

        Every prior turn in ``history`` is, by construction, a turn that
        actually executed a tool call and produced exactly one function
        call: ``BenchmarkRunner.run_case``'s loop always terminates
        immediately after a voluntary stop or a blocked mutation (see
        ``app/runner/engine.py``), so ``decide()`` is never called again
        afterward, and a turn only reaches ``history`` if this adapter's own
        prior ``_handle_response`` call cached its provider output.
        """
        input_list: list[Any] = [{"role": "user", "content": prompt}]
        for turn in history:
            provider_output = self._provider_output_by_turn.get(turn.turn_index)
            if provider_output is None:
                # Should never happen for a turn this adapter itself
                # produced — defensive, not a normal code path.
                raise OpenAIAdapterError(
                    f"No cached provider output for turn {turn.turn_index}; cannot "
                    "faithfully continue the Responses API conversation without "
                    "inventing a call_id the provider never issued."
                )
            input_list.extend(provider_output)
            call_id = _extract_function_call_id(provider_output)
            observation = (
                turn.raw_text_output if turn.raw_text_output is not None else (turn.error or "")
            )
            input_list.append(
                {"type": "function_call_output", "call_id": call_id, "output": observation}
            )
        return input_list

    def _handle_response(self, response: Any, turn_index: int) -> ToolCallDecision:
        incomplete_details = getattr(response, "incomplete_details", None)
        incomplete_reason = (
            getattr(incomplete_details, "reason", None) if incomplete_details else None
        )
        if incomplete_reason is not None:
            self._record_call(
                status="error",
                response_id=getattr(response, "id", None),
                returned_model=getattr(response, "model", None),
                usage=getattr(response, "usage", None),
                error=f"Incomplete response (reason={incomplete_reason})",
            )
            raise OpenAIAdapterError(
                f"Provider response was incomplete (reason={incomplete_reason}); "
                "refusing to interpret a partial response as a valid decision."
            )

        output = getattr(response, "output", []) or []
        function_calls = [item for item in output if getattr(item, "type", None) == "function_call"]

        usage = getattr(response, "usage", None)
        self._record_call(
            status="ok",
            response_id=getattr(response, "id", None),
            returned_model=getattr(response, "model", None),
            usage=usage,
        )

        if len(function_calls) > 1:
            raise OpenAIAdapterError(
                f"Provider returned {len(function_calls)} function calls in one turn "
                "despite parallel_tool_calls=False; expected at most one. Refusing "
                "to silently pick one — see Phase 2C's documented policy."
            )

        if not function_calls:
            return ToolCallDecision(tool_name=None)

        # Cache the FULL output list (not just the function_call item) so
        # any opaque reasoning items are also replayed verbatim next turn —
        # this adapter never inspects or persists their content.
        self._provider_output_by_turn[turn_index] = list(output)

        call = function_calls[0]
        raw_arguments = getattr(call, "arguments", None) or "{}"
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise OpenAIAdapterError(
                f"Provider returned unparseable tool-call arguments for "
                f"'{getattr(call, 'name', '?')}': {exc}"
            ) from None

        if not isinstance(arguments, dict):
            raise OpenAIAdapterError(
                f"Provider returned non-object tool-call arguments for "
                f"'{getattr(call, 'name', '?')}': {type(arguments).__name__}"
            )

        # Pass the tool name and arguments through exactly as the model gave
        # them — including a hallucinated/unknown tool name, or arguments
        # that fail the tool's schema. The existing runner/evaluators (tool
        # lookup, schema validation, argument-correctness scoring) retain
        # full authority over judging this; this adapter never repairs,
        # validates, or conceals a model's mistake.
        return ToolCallDecision(tool_name=call.name, arguments=arguments)

    def _record_call(
        self,
        *,
        status: str,
        response_id: str | None = None,
        returned_model: str | None = None,
        usage: Any | None = None,
        error: str | None = None,
    ) -> None:
        self.provenance.provider_calls.append(
            ProviderCallRecord(
                case_id=self._current_case_id or "",
                turn_index=sum(
                    1
                    for call in self.provenance.provider_calls
                    if call.case_id == (self._current_case_id or "")
                ),
                provider_response_id=response_id,
                requested_model=self._model,
                returned_model=returned_model,
                input_tokens=getattr(usage, "input_tokens", None) if usage is not None else None,
                output_tokens=getattr(usage, "output_tokens", None) if usage is not None else None,
                total_tokens=getattr(usage, "total_tokens", None) if usage is not None else None,
                status=status,
                error=error,
            )
        )


def _extract_function_call_id(provider_output: list[Any]) -> str:
    for item in provider_output:
        if getattr(item, "type", None) == "function_call":
            return item.call_id
    raise OpenAIAdapterError(
        "Cached provider output for a continued turn has no function_call item; "
        "cannot correlate a function_call_output to it."
    )


def build_openai_responses_client(
    *, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS, max_retries: int = DEFAULT_MAX_RETRIES
) -> ResponsesClient:
    """Constructs a real ``AsyncOpenAI`` client's ``.responses`` resource.

    Reads ``OPENAI_API_KEY`` from the environment via the SDK's own standard
    behavior only — never accepts a key from a request body, query
    parameter, suite YAML, or benchmark fixture (see Part H of the Phase 2C
    design). Raises a clear, actionable ``OpenAIAdapterError`` if the
    optional ``openai`` package is not installed, rather than an opaque
    ``ImportError`` surfacing from deep inside adapter construction.
    """
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise OpenAIAdapterError(
            "The 'openai' package is not installed. Install the optional "
            "real-model extra to use adapter=openai: `uv sync --extra openai`."
        ) from None

    client = AsyncOpenAI(timeout=timeout_seconds, max_retries=max_retries)
    return client.responses
