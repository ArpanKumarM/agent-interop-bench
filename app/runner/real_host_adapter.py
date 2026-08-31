"""RealHostAgentAdapter: a HostAgentAdapter backed by a real OpenAI model
via the Responses API (Phase 4A.2). Optional — requires the ``openai``
extra and ``OPENAI_API_KEY``. Never constructed for a deterministic run,
and never called against a live model anywhere in this repository's own
tests or CI.

Architecture: consumes ONLY ``HostDecisionContext`` (see
``app.models.host_context``) and returns a validated ``HostActionSpec`` —
never a ``ComposedBenchmarkCase``, never a raw ``CrossProtocolEvent``. It
never touches MCP transport or the A2A mock itself, and never changes what
``ComposedBenchmarkRunner`` does with the action it returns: the same
mutation gate (``app.runner.mutation_gate.mutation_blocked``) applies
exactly as it does for ``ScriptedHostAdapter``. A model can *propose*
``attempt_mutating_tool``; this adapter always returns ``approved=False``
for it (the model has no path to grant its own approval — only a case's
own pre-configured policy could, and this adapter never sees or sets that),
so only the runner's existing, model-independent gate decides whether it
executes.

Deliberately NOT a subclass of, or a merge with, ``OpenAIResponsesAdapter``
(MCP's real adapter): composed's action space (four fixed actions, no
per-turn MCP-tool-call shape, no ``call_id``-threaded conversation state)
is different enough that forcing a shared base class would blur, not
clarify, either one. Only genuinely provider-neutral helpers
(``openai_sdk_available``, ``build_openai_responses_client``,
``ResponsesClient``, ``_sanitize_provider_error``) are reused from
``app.runner.openai_adapter`` — the two adapter *classes* stay fully
separate.

Each decision is a single, independent Responses API request: the full
observable history is serialized fresh into ``input`` every time (no
``call_id`` conversation-continuation state is threaded between decisions),
so this adapter is fully stateless across turns aside from its own
decision counter and accumulated provenance.

No chain-of-thought is ever read: only ``response.output``'s function-call
item (name + arguments) is inspected; any reasoning item is ignored and
never stored.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Collection, Iterable
from typing import Any

from pydantic import BaseModel, ValidationError

from app.models.composed import HostActionSpec
from app.models.composed_provenance import ComposedModelRunProvenance, ComposedProviderCallRecord
from app.models.host_context import HostDecisionContext
from app.runner.host_action_schema_openai import (
    ALL_HOST_ACTION_TOOLS,
    HOST_ACTION_TOOLS_FOR_OPENAI,
    host_action_schema_fingerprint,
)
from app.runner.host_adapters import HostAgentAdapter
from app.runner.openai_adapter import (
    ResponsesClient,
    _sanitize_provider_error,
    build_openai_responses_client,
    openai_sdk_available,
)

DEFAULT_MAX_OUTPUT_TOKENS = 256
DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 0
# Explicitly frozen (Phase 4A.3c): never rely on the provider's default
# reasoning effort. Always sent verbatim in every request's `reasoning.effort`.
DEFAULT_REASONING_EFFORT = "low"

_VALID_ACTIONS = frozenset(
    {"call_local_tool", "call_tool", "relay_to_remote", "attempt_mutating_tool", "stop"}
)


class RealHostAdapterError(RuntimeError):
    """A controlled adapter-level failure: provider error, incomplete
    response, wrong number of function calls, unparseable/non-object
    arguments, schema-invalid arguments, an unknown action name, or an
    exhausted decision budget.

    Always raised with a sanitized message (see ``_sanitize_provider_error``)
    and exception chaining suppressed (``from None``) — the same discipline
    ``OpenAIAdapterError`` uses. This is what "fail safely and observably"
    means here: a malformed or unrecognized model response never becomes an
    executed action; it becomes this exception instead, propagating out of
    ``decide()`` uncaught, exactly like any other adapter failure.
    """


class InvalidToolSelectionError(RealHostAdapterError):
    """A ``call_tool`` action named a tool that is NOT in the trial's exact
    model-visible MCP tool set (the Phase 6B 12-tool surface for that
    trial).

    Provider-neutral: raised from the ONE shared post-parse path
    (``build_host_action_spec``) so OpenAI and Anthropic treat an
    out-of-surface tool name identically. Both adapters record it as the
    pre-registered ``provider_protocol_error`` attrition status. The trial
    then persists terminally with NO ``tool_invocation`` event stamped, NO
    MCP execution attempt, and NO taxonomy classification of a nonexistent
    tool; there is no retry and no replacement; the run continues to the
    next scheduled trial. Covers a hallucinated name, the ``stop`` sentinel
    passed as if it were a tool, and a legacy server-only tool that is not
    in the model-visible surface.
    """


class _CallLocalToolArgs(BaseModel):
    tool_name: str
    # Carried as a JSON string on the wire: an open argument object cannot be
    # expressed under OpenAI strict-schema mode (see host_action_schema_openai).
    tool_arguments_json: str


class _CallToolArgs(BaseModel):
    """Phase 6B ``call_tool`` -- a neutral "call any discovered tool" action.
    ``arguments_json`` is the strict-schema JSON-string form of the argument
    object, decoded and validated before execution (identical discipline to
    ``call_local_tool``)."""

    tool_name: str
    arguments_json: str


class _RelayToRemoteArgs(BaseModel):
    content: str
    content_type: str = "text/plain"


class _AttemptMutatingToolArgs(BaseModel):
    tool_name: str
    tool_arguments_json: str


def _decode_tool_arguments(raw: str) -> dict[str, Any]:
    """Decode the strict-schema ``tool_arguments_json`` string back into the
    mapping ``HostActionSpec.tool_arguments`` has always been. A non-JSON or
    non-object payload is a controlled, sanitized adapter failure -- never a
    silently-accepted or coerced action."""
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RealHostAdapterError(f"tool_arguments_json is not valid JSON: {exc}") from None
    if not isinstance(decoded, dict):
        raise RealHostAdapterError(
            f"tool_arguments_json must encode a JSON object, got {type(decoded).__name__}"
        )
    return decoded


def build_host_action_spec(
    name: str | None,
    parsed: dict[str, Any],
    *,
    allowed_action_names: set[str] | None,
    available_tool_names: Collection[str] | None = None,
) -> HostActionSpec:
    """The ONE post-parse path from ``(action name, decoded arguments)`` to a
    validated ``HostActionSpec`` -- shared by the OpenAI adapter
    (``RealHostAgentAdapter``) and the Anthropic adapter
    (``AnthropicHostAgentAdapter``), so both providers compile the identical
    canonical decision semantics: same names, same required arguments, same
    validation, same resulting ``HostDecision``.

    A model can never grant its own approval: ``call_tool`` /
    ``attempt_mutating_tool`` always come back ``approved=False``; only the
    runner's model-independent mutation gate decides execution.

    ``available_tool_names`` (when given) is the trial's exact model-visible
    MCP tool allowlist. A ``call_tool`` naming anything outside it -- a
    hallucinated name, the ``stop`` sentinel passed as a tool, or a
    server-only legacy tool that is not model-visible -- raises
    ``InvalidToolSelectionError`` (a ``RealHostAdapterError``), which the
    caller records as ``provider_protocol_error``. The name is validated
    AFTER provider parsing and BEFORE the engine ever dispatches the call,
    so no ``tool_invocation`` event and no MCP execution occur.

    Raises ``RealHostAdapterError`` for an unknown / disallowed action, and
    lets ``pydantic.ValidationError`` / ``RealHostAdapterError`` from
    argument decoding propagate (the caller records provenance and converts
    to a controlled failure).
    """
    if name not in _VALID_ACTIONS:
        raise RealHostAdapterError(f"Unknown action {name!r}")

    if allowed_action_names is not None and name not in allowed_action_names:
        raise RealHostAdapterError(
            f"Action {name!r} is not permitted at this decision point "
            f"(allowed: {sorted(allowed_action_names)})"
        )

    if name == "call_local_tool":
        args = _CallLocalToolArgs.model_validate(parsed)
        return HostActionSpec(
            action="call_local_tool",
            tool_name=args.tool_name,
            tool_arguments=_decode_tool_arguments(args.tool_arguments_json),
        )
    if name == "call_tool":
        ct_args = _CallToolArgs.model_validate(parsed)
        if available_tool_names is not None and ct_args.tool_name not in available_tool_names:
            raise InvalidToolSelectionError(
                f"call_tool named tool {ct_args.tool_name!r}, which is not in the "
                f"model-visible tool set for this trial "
                f"(visible: {sorted(available_tool_names)})"
            )
        return HostActionSpec(
            action="call_tool",
            tool_name=ct_args.tool_name,
            tool_arguments=_decode_tool_arguments(ct_args.arguments_json),
            approved=False,
            trigger_name=None,
        )
    if name == "relay_to_remote":
        args = _RelayToRemoteArgs.model_validate(parsed)
        return HostActionSpec(
            action="relay_to_remote",
            relay_template=args.content,
            content_type=args.content_type,
        )
    if name == "attempt_mutating_tool":
        args = _AttemptMutatingToolArgs.model_validate(parsed)
        return HostActionSpec(
            action="attempt_mutating_tool",
            tool_name=args.tool_name,
            tool_arguments=_decode_tool_arguments(args.tool_arguments_json),
            approved=False,
            trigger_name=None,
        )
    return HostActionSpec(action="stop")


def _canonical_history_event(event: Any) -> dict[str, Any]:
    """One model-visible history event. For an ``mcp_tool_result`` the raw
    trace keeps BOTH a structured and a textual protocol representation of
    the same result (scientifically useful); the MODEL sees exactly ONE
    canonical record representation, so no record value is duplicated in the
    serialized decision input (Phase 6B)."""
    dumped = event.model_dump(exclude={"is_mutating", "approved", "executed"})
    if dumped.get("event_type") == "mcp_tool_result":
        payload = dumped.get("payload", {})
        structured = payload.get("structured_output") or {}
        record = structured.get("record") if isinstance(structured, dict) else None
        if record is None:
            record = payload.get("text_output")
        dumped["payload"] = {"is_error": payload.get("is_error"), "record": record}
    return dumped


def _build_input(context: HostDecisionContext) -> list[dict[str, Any]]:
    """Serializes the full sanitized context fresh, every decision -- no
    provider-side conversation state is threaded between calls."""
    payload = {
        "user_prompt": context.user_prompt,
        "current_step": context.current_step,
        "target_agent_card": context.target_agent_card.model_dump(by_alias=True),
        # Phase 6B model-blindness: the model sees a tool's name / neutral
        # description / input schema only -- NEVER the benchmark's trusted
        # ``is_mutating`` classification (see ToolDefinition.model_visible_dump),
        # and never a per-event is_mutating / approved / executed / gate label.
        "available_mcp_tools": [tool.model_visible_dump() for tool in context.available_tools],
        "history": [_canonical_history_event(event) for event in context.history],
    }
    return [{"role": "user", "content": json.dumps(payload, default=str, sort_keys=True)}]


class RealHostAgentAdapter(HostAgentAdapter):
    """Real-model ``HostAgentAdapter`` using OpenAI's Responses API."""

    def __init__(
        self,
        client: ResponsesClient,
        model: str,
        *,
        max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        max_decisions: int | None = None,
        case_id: str = "",
        reasoning_effort: str = DEFAULT_REASONING_EFFORT,
        allowed_actions: Iterable[str] | None = None,
    ) -> None:
        self._client = client
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._max_decisions = max_decisions
        self._decisions_made = 0
        self._case_id = case_id
        self._reasoning_effort = reasoning_effort
        # The trial's exact model-visible MCP tool allowlist, captured from
        # each decide() context. A call_tool naming anything outside this set
        # is a provider_protocol_error (see build_host_action_spec).
        self._visible_tool_names: set[str] = set()
        # allowed_actions=None -> the full canonical four-tool surface. A
        # subset (Phase 4A.3d decision points) filters BOTH what is offered on
        # the wire and what a returned action is allowed to be -- so the model
        # never even sees a disallowed action, and a disallowed one coming
        # back anyway is a controlled, sanitized failure, never an execution.
        if allowed_actions is None:
            # Unrestricted default wire surface -- the frozen 4 tools only
            # (call_tool is Phase 6B and only ever offered via an explicit
            # allowed_actions subset).
            self._tools_for_request = HOST_ACTION_TOOLS_FOR_OPENAI
            self._allowed_action_names: set[str] | None = None
        else:
            names = set(allowed_actions)
            self._tools_for_request = [
                tool for tool in ALL_HOST_ACTION_TOOLS if tool["name"] in names
            ]
            if len(self._tools_for_request) != len(names):
                raise ValueError(
                    f"allowed_actions {sorted(names)} does not match the host-action "
                    "tool set "
                    f"{sorted(tool['name'] for tool in ALL_HOST_ACTION_TOOLS)}"
                )
            self._allowed_action_names = names
        self.provenance = ComposedModelRunProvenance(
            adapter_type="openai_responses_host",
            provider="openai",
            requested_model=model,
            # filled in on the first decide() call, once host_policy is known
            host_policy_sha256="",
            tool_schema_sha256=host_action_schema_fingerprint(),
            configured_timeout_seconds=timeout_seconds,
            configured_max_retries=max_retries,
            configured_max_output_tokens=max_output_tokens,
            configured_max_decisions=max_decisions,
            reasoning_effort=reasoning_effort,
            restricted_to_actions=(
                sorted(self._allowed_action_names)
                if self._allowed_action_names is not None
                else None
            ),
        )

    async def decide(self, context: HostDecisionContext) -> HostActionSpec:
        if not self.provenance.host_policy_sha256:
            self.provenance.host_policy_sha256 = hashlib.sha256(
                context.host_policy.encode("utf-8")
            ).hexdigest()

        if self._max_decisions is not None and self._decisions_made >= self._max_decisions:
            raise RealHostAdapterError(
                f"Composed provider-decision budget exhausted "
                f"({self._max_decisions} decisions); refusing to make another "
                "provider call for this run."
            )
        self._decisions_made += 1

        self._visible_tool_names = {tool.name for tool in context.available_tools}
        input_list = _build_input(context)
        started = time.perf_counter()
        try:
            response = await self._client.create(
                model=self._model,
                instructions=context.host_policy,
                input=input_list,
                tools=self._tools_for_request,
                tool_choice="required",
                parallel_tool_calls=False,
                max_output_tokens=self._max_output_tokens,
                reasoning={"effort": self._reasoning_effort},
            )
        except Exception as exc:  # noqa: BLE001 - deliberately broad: ANY provider
            # failure must become one controlled, sanitized adapter error.
            sanitized = _sanitize_provider_error(exc)
            self._record_call(
                status="error", error=sanitized, latency_ms=(time.perf_counter() - started) * 1000
            )
            raise RealHostAdapterError(f"OpenAI request failed: {sanitized}") from None

        latency_ms = (time.perf_counter() - started) * 1000
        return self._handle_response(response, latency_ms)

    def _handle_response(self, response: Any, latency_ms: float) -> HostActionSpec:
        response_id = getattr(response, "id", None)
        returned_model = getattr(response, "model", None)
        usage = getattr(response, "usage", None)

        incomplete_details = getattr(response, "incomplete_details", None)
        incomplete_reason = (
            getattr(incomplete_details, "reason", None) if incomplete_details else None
        )
        if incomplete_reason is not None:
            self._record_call(
                status="error",
                response_id=response_id,
                returned_model=returned_model,
                usage=usage,
                latency_ms=latency_ms,
                error=f"Incomplete response (reason={incomplete_reason})",
            )
            raise RealHostAdapterError(
                f"Provider response was incomplete (reason={incomplete_reason}); "
                "refusing to interpret a partial response as a valid decision."
            )

        output = getattr(response, "output", []) or []
        function_calls = [item for item in output if getattr(item, "type", None) == "function_call"]

        if len(function_calls) != 1:
            self._record_call(
                status="error",
                response_id=response_id,
                returned_model=returned_model,
                usage=usage,
                latency_ms=latency_ms,
                error=f"Expected exactly one function call, got {len(function_calls)}",
            )
            raise RealHostAdapterError(
                f"Provider returned {len(function_calls)} function calls; expected exactly "
                "one host action (call_local_tool / call_tool / relay_to_remote / "
                "attempt_mutating_tool / stop)."
            )

        call = function_calls[0]
        name = getattr(call, "name", None)
        raw_arguments = getattr(call, "arguments", None) or "{}"

        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            self._record_call(
                status="error",
                response_id=response_id,
                returned_model=returned_model,
                usage=usage,
                latency_ms=latency_ms,
                error=f"Unparseable arguments for '{name}': {exc}",
            )
            raise RealHostAdapterError(
                f"Provider returned unparseable arguments for '{name}': {exc}"
            ) from None

        if not isinstance(parsed, dict):
            self._record_call(
                status="error",
                response_id=response_id,
                returned_model=returned_model,
                usage=usage,
                latency_ms=latency_ms,
                error=f"Non-object arguments for '{name}': {type(parsed).__name__}",
            )
            raise RealHostAdapterError(
                f"Provider returned non-object arguments for '{name}': {type(parsed).__name__}"
            )

        try:
            action_spec = self._to_action_spec(name, parsed)
        except InvalidToolSelectionError as exc:
            self._record_call(
                status="provider_protocol_error",
                response_id=response_id,
                returned_model=returned_model,
                usage=usage,
                latency_ms=latency_ms,
                error=f"Invalid tool selection from provider: {exc}",
            )
            raise RealHostAdapterError(
                f"Provider selected a tool outside the model-visible surface: {exc}"
            ) from None
        except (ValidationError, RealHostAdapterError) as exc:
            self._record_call(
                status="error",
                response_id=response_id,
                returned_model=returned_model,
                usage=usage,
                latency_ms=latency_ms,
                error=f"Invalid action from provider: {exc}",
            )
            raise RealHostAdapterError(f"Provider returned an invalid action: {exc}") from None

        self._record_call(
            status="ok",
            response_id=response_id,
            returned_model=returned_model,
            usage=usage,
            latency_ms=latency_ms,
            observable_action=action_spec.model_dump(),
        )
        return action_spec

    def _to_action_spec(self, name: str | None, parsed: dict[str, Any]) -> HostActionSpec:
        # Thin delegation to the shared, provider-neutral post-parse path so
        # OpenAI and Anthropic produce byte-identical HostDecisions.
        return build_host_action_spec(
            name,
            parsed,
            allowed_action_names=self._allowed_action_names,
            available_tool_names=self._visible_tool_names,
        )

    def _record_call(
        self,
        *,
        status: str,
        response_id: str | None = None,
        returned_model: str | None = None,
        usage: Any | None = None,
        latency_ms: float | None = None,
        observable_action: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.provenance.provider_calls.append(
            ComposedProviderCallRecord(
                case_id=self._case_id,
                decision_index=len(self.provenance.provider_calls),
                provider_response_id=response_id,
                requested_model=self._model,
                returned_model=returned_model,
                input_tokens=getattr(usage, "input_tokens", None) if usage is not None else None,
                output_tokens=getattr(usage, "output_tokens", None) if usage is not None else None,
                total_tokens=getattr(usage, "total_tokens", None) if usage is not None else None,
                latency_ms=latency_ms,
                observable_action=observable_action,
                status=status,
                error=error,
            )
        )


__all__ = [
    "InvalidToolSelectionError",
    "RealHostAdapterError",
    "RealHostAgentAdapter",
    "build_host_action_spec",
    "build_openai_responses_client",
    "openai_sdk_available",
]
