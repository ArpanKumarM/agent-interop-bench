"""AnthropicHostAgentAdapter: a ``HostAgentAdapter`` backed by
``claude-sonnet-5`` via the Anthropic Messages API (Phase 6C external-family
robustness model).

Provider-neutral by construction:

* the sanitized decision context is serialized by the SAME
  ``app.runner.real_host_adapter._build_input`` the OpenAI adapter uses --
  identical host policy, sanitized history (one canonical record field, no
  ``is_mutating``/``approved``/``executed``), 12-tool MCP surface, user
  prompt, target Agent Card;
* the canonical action schema is compiled to Anthropic's wire format by
  ``AnthropicHostDecisionClient`` (semantic names/args identical to
  OpenAI's);
* the accepted tool call is mapped to a ``HostActionSpec`` by the SAME
  shared ``build_host_action_spec`` -- so the resulting ``HostDecision`` is
  byte-identical to OpenAI's for the same decision.

Parser / status rules (pre-registered, Phase 6C):

* exactly one valid allowed tool call            -> accept
* zero tool_use blocks                           -> ``provider_protocol_error``
* more than one tool_use block                   -> ``provider_protocol_error``
* unknown action name                            -> ``provider_protocol_error``
* ``call_tool`` tool_name not in the trial's     -> ``provider_protocol_error``
  model-visible MCP surface (hallucinated name,     (via the shared
  ``stop`` passed as a tool, or a legacy               ``InvalidToolSelectionError``;
  server-only tool)                                    no tool_invocation event, no
                                                       MCP call, no taxonomy step)
* malformed / non-object arguments               -> ``provider_protocol_error``
* schema-invalid arguments (pydantic)            -> ``provider_protocol_error``
* explicit refusal (stop_reason/refusal block)   -> ``provider_refusal``
* ``stop_reason == "max_tokens"`` (truncation)   -> ``provider_error``
* timeout / any transport or API exception       -> ``provider_error``
  (a timeout is a ``provider_error`` whose sanitized message names the
  timeout; no separate ``timeout`` code is emitted here because the SDK
  raises the same ``APITimeoutError`` type for it -- the trial-level
  attrition classifier maps it)

NEVER: turn a refusal into ``stop``; pick the first of multiple tool calls;
retry; repair malformed arguments; silently coerce invalid output. Each of
those becomes a raised, recorded, terminal failure instead.

No chain-of-thought is read or stored: only ``tool_use`` blocks are
inspected. One Messages request per decision; zero retries.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from app.models.composed import HostActionSpec
from app.models.composed_provenance import ComposedModelRunProvenance, ComposedProviderCallRecord
from app.models.host_context import HostDecisionContext
from app.runner.anthropic_adapter import _sanitize_provider_error
from app.runner.execution_fingerprint import host_policy_sha256
from app.runner.host_action_schema_anthropic import anthropic_wire_tool_schema_sha256
from app.runner.host_adapters import HostAgentAdapter
from app.runner.host_decision_client import (
    AnthropicHostDecisionClient,
    AnthropicProtocolError,
    AnthropicRefusalError,
)
from app.runner.model_panel import (
    ANTHROPIC_MAX_OUTPUT_TOKENS,
    LOW_EFFORT,
    provider_config_sha256,
    provider_request_config,
)
from app.runner.real_host_adapter import (
    _VALID_ACTIONS,
    RealHostAdapterError,
    _build_input,
    build_host_action_spec,
)

DEFAULT_TIMEOUT_SECONDS = 30.0

# Pre-registered attrition statuses (Phase 6C). ``ok`` is the success case.
STATUS_OK = "ok"
STATUS_REFUSAL = "provider_refusal"
STATUS_PROTOCOL_ERROR = "provider_protocol_error"
STATUS_ERROR = "provider_error"
STATUS_TIMEOUT = "timeout"

_ANTHROPIC_ACTION_SURFACE = "anthropic.messages"


class AnthropicHostAdapterError(RuntimeError):
    """A controlled, sanitized adapter-level failure. Carries the
    pre-registered ``status`` so the trial record can report it without
    re-parsing the message."""

    def __init__(self, message: str, *, status: str) -> None:
        super().__init__(message)
        self.status = status


class AnthropicHostAgentAdapter(HostAgentAdapter):
    """Real-model ``HostAgentAdapter`` using the Anthropic Messages API."""

    def __init__(
        self,
        client: AnthropicHostDecisionClient,
        model: str = "claude-sonnet-5",
        *,
        max_output_tokens: int = ANTHROPIC_MAX_OUTPUT_TOKENS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_decisions: int | None = None,
        case_id: str = "",
        reasoning_effort: str = LOW_EFFORT,
        allowed_actions: Iterable[str] | None = None,
        canonical_actions: tuple[str, ...] = ("relay_to_remote", "call_tool", "stop"),
    ) -> None:
        self._client = client
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds
        self._max_decisions = max_decisions
        self._decisions_made = 0
        self._case_id = case_id
        self._reasoning_effort = reasoning_effort
        self._canonical_actions_for_fp = canonical_actions
        # The trial's exact model-visible MCP tool allowlist, captured from
        # each decide() context. A call_tool naming anything outside this set
        # is a provider_protocol_error (see build_host_action_spec) --
        # identical semantics to the OpenAI adapter.
        self._visible_tool_names: set[str] = set()
        if allowed_actions is None:
            self._allowed_action_names: set[str] | None = None
            self._wire_actions: tuple[str, ...] = ("relay_to_remote", "call_tool", "stop")
        else:
            names = set(allowed_actions)
            unknown = names - _VALID_ACTIONS
            if unknown:
                raise ValueError(f"allowed_actions has unknown action(s): {sorted(unknown)}")
            self._allowed_action_names = names
            self._wire_actions = tuple(
                a for a in ("relay_to_remote", "call_tool", "stop") if a in names
            )

        cfg = provider_request_config(model, timeout_seconds=timeout_seconds)
        self.provenance = ComposedModelRunProvenance(
            adapter_type="anthropic_messages_host",
            provider="anthropic",
            requested_model=model,
            host_policy_sha256="",  # filled on first decide(), once policy known
            tool_schema_sha256=anthropic_wire_tool_schema_sha256(self._wire_actions),
            configured_timeout_seconds=timeout_seconds,
            configured_max_retries=0,
            configured_max_output_tokens=max_output_tokens,
            configured_max_decisions=max_decisions,
            reasoning_effort=reasoning_effort,
            restricted_to_actions=(
                sorted(self._allowed_action_names)
                if self._allowed_action_names is not None
                else None
            ),
            provider_api_surface=_ANTHROPIC_ACTION_SURFACE,
            provider_request_config=cfg,
            provider_config_sha256=provider_config_sha256(
                model,
                canonical_actions=self._canonical_actions_for_fp,
                timeout_seconds=timeout_seconds,
            ),
        )

    async def decide(self, context: HostDecisionContext) -> HostActionSpec:
        if not self.provenance.host_policy_sha256:
            self.provenance.host_policy_sha256 = host_policy_sha256(context.host_policy)

        if self._max_decisions is not None and self._decisions_made >= self._max_decisions:
            raise AnthropicHostAdapterError(
                f"Composed provider-decision budget exhausted ({self._max_decisions} "
                "decisions); refusing to make another provider call for this run.",
                status=STATUS_ERROR,
            )
        self._decisions_made += 1

        self._visible_tool_names = {tool.name for tool in context.available_tools}
        input_list = _build_input(context)
        input_payload = json.loads(input_list[0]["content"])

        started = time.perf_counter()
        try:
            response = await self._client.decide(
                model=self._model,
                instructions=context.host_policy,
                input_payload=input_payload,
                canonical_actions=self._wire_actions,
                max_output_tokens=self._max_output_tokens,
                reasoning_effort=self._reasoning_effort,
            )
        except Exception as exc:  # noqa: BLE001 - ANY provider failure -> one sanitized error
            sanitized = _sanitize_provider_error(exc)
            status = (
                STATUS_TIMEOUT
                if "Timeout" in type(exc).__name__ or "timeout" in sanitized.lower()
                else STATUS_ERROR
            )
            self._record_call(
                status=status,
                error=sanitized,
                latency_ms=(time.perf_counter() - started) * 1000,
            )
            raise AnthropicHostAdapterError(
                f"Anthropic request failed: {sanitized}", status=status
            ) from None

        latency_ms = (time.perf_counter() - started) * 1000
        return self._handle_response(response, latency_ms)

    def _handle_response(self, response: Any, latency_ms: float) -> HostActionSpec:
        response_id = getattr(response, "id", None)
        returned_model = getattr(response, "model", None)
        usage = getattr(response, "usage", None)
        stop_reason = AnthropicHostDecisionClient.response_stop_reason(response)

        if AnthropicHostDecisionClient.is_refusal(response):
            self._record_call(
                status=STATUS_REFUSAL,
                response_id=response_id,
                returned_model=returned_model,
                usage=usage,
                latency_ms=latency_ms,
                stop_reason=stop_reason,
                refusal=True,
                error="Provider explicitly refused (stop_reason/refusal block).",
            )
            raise AnthropicHostAdapterError(
                "Anthropic explicitly refused; a refusal is never coerced into a stop.",
                status=STATUS_REFUSAL,
            )

        if stop_reason == "max_tokens":
            self._record_call(
                status=STATUS_ERROR,
                response_id=response_id,
                returned_model=returned_model,
                usage=usage,
                latency_ms=latency_ms,
                stop_reason=stop_reason,
                error="Response truncated (stop_reason=max_tokens); not a decision.",
            )
            raise AnthropicHostAdapterError(
                "Anthropic response was truncated (stop_reason=max_tokens); refusing "
                "to interpret a partial response as a valid decision.",
                status=STATUS_ERROR,
            )

        try:
            parsed_call = self._client.parse_tool_call(response)
        except (AnthropicProtocolError, AnthropicRefusalError) as exc:
            status = (
                STATUS_REFUSAL if isinstance(exc, AnthropicRefusalError) else STATUS_PROTOCOL_ERROR
            )
            self._record_call(
                status=status,
                response_id=response_id,
                returned_model=returned_model,
                usage=usage,
                latency_ms=latency_ms,
                stop_reason=stop_reason,
                refusal=(status == STATUS_REFUSAL),
                error=f"Tool-call parse failed: {exc}",
            )
            raise AnthropicHostAdapterError(
                f"Anthropic returned no single usable tool call: {exc}", status=status
            ) from None

        try:
            action_spec = build_host_action_spec(
                parsed_call.name,
                parsed_call.arguments,
                allowed_action_names=self._allowed_action_names,
                available_tool_names=self._visible_tool_names,
            )
        except (ValidationError, RealHostAdapterError) as exc:
            self._record_call(
                status=STATUS_PROTOCOL_ERROR,
                response_id=response_id,
                returned_model=returned_model,
                usage=usage,
                latency_ms=latency_ms,
                stop_reason=stop_reason,
                error=f"Invalid action from provider: {exc}",
            )
            raise AnthropicHostAdapterError(
                f"Anthropic returned an invalid action: {exc}", status=STATUS_PROTOCOL_ERROR
            ) from None

        self._record_call(
            status=STATUS_OK,
            response_id=response_id,
            returned_model=returned_model,
            usage=usage,
            latency_ms=latency_ms,
            stop_reason=stop_reason,
            refusal=False,
            observable_action=action_spec.model_dump(),
            action_parsed=action_spec.action,
        )
        return action_spec

    def _record_call(
        self,
        *,
        status: str,
        response_id: str | None = None,
        returned_model: str | None = None,
        usage: Any | None = None,
        latency_ms: float | None = None,
        stop_reason: str | None = None,
        refusal: bool | None = None,
        observable_action: dict[str, Any] | None = None,
        action_parsed: str | None = None,
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
                output_tokens=(
                    getattr(usage, "output_tokens", None) if usage is not None else None
                ),
                total_tokens=None,
                latency_ms=latency_ms,
                observable_action=observable_action,
                status=status,
                error=error,
                provider="anthropic",
                provider_api_surface=_ANTHROPIC_ACTION_SURFACE,
                stop_reason=stop_reason,
                refusal=refusal,
                action_parsed=action_parsed,
            )
        )


__all__ = [
    "AnthropicHostAdapterError",
    "AnthropicHostAgentAdapter",
    "STATUS_ERROR",
    "STATUS_OK",
    "STATUS_PROTOCOL_ERROR",
    "STATUS_REFUSAL",
    "STATUS_TIMEOUT",
]
