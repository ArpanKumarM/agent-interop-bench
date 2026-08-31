"""Provenance for real-model composed (Phase 4A.2) host-agent runs.

Deliberately separate from ``app.models.provenance.ModelRunProvenance``
(MCP's real-model provenance): composed's decision shape (one of
``call_local_tool``/``relay_to_remote``/``attempt_mutating_tool``/``stop``
per turn, no MCP-tool-call-per-turn concept) is genuinely different, so
this is its own record, not a reuse of the MCP one. Same discipline as the
MCP provenance model: no credential, header, or raw provider response is
ever persisted -- only benchmark-relevant metadata (which model, which
policy/schema hash, how many decisions, how many tokens, and the
*sanitized, already-structured* action the model decided on).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.execution_fingerprint import ExecutionFingerprint


class ComposedProviderCallRecord(BaseModel):
    """One provider call made to decide one host action."""

    case_id: str
    decision_index: int
    provider_response_id: str | None = None
    requested_model: str
    returned_model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    latency_ms: float | None = None
    # The already-parsed-and-validated HostActionSpec the provider's call
    # translated to -- never the raw provider response object, and never
    # any hidden reasoning/chain-of-thought content.
    observable_action: dict[str, Any] | None = None
    status: str
    """One of: ``ok`` | ``provider_refusal`` | ``provider_protocol_error`` |
    ``provider_error`` | ``timeout`` (Phase 6C pre-registered attrition
    classes). ``error`` (legacy) is still written for any non-ok status."""
    error: str | None = None
    """Sanitized, credential-free error string. None when status == "ok"."""
    # ---- Phase 6C provider provenance (never any hidden reasoning) -------
    provider: str | None = None
    """``openai`` | ``anthropic``."""
    provider_api_surface: str | None = None
    """e.g. ``openai.responses`` | ``anthropic.messages``."""
    stop_reason: str | None = None
    """Provider-reported stop reason (OpenAI ``incomplete_details.reason`` or
    completion status; Anthropic ``stop_reason``). Never reasoning content."""
    refusal: bool | None = None
    """True iff the provider explicitly refused (Anthropic
    ``stop_reason == "refusal"`` / a refusal content block; OpenAI refusal
    output item)."""
    action_parsed: str | None = None
    """The canonical action name parsed from the one accepted tool call
    (``call_tool`` / ``relay_to_remote`` / ``stop``); None on any failure."""


class ComposedModelRunProvenance(BaseModel):
    """Full audit record for a live-model composed run."""

    adapter_type: str
    provider: str
    requested_model: str
    host_policy_sha256: str
    tool_schema_sha256: str
    configured_timeout_seconds: float
    configured_max_retries: int
    configured_max_output_tokens: int
    configured_max_decisions: int | None = None
    reasoning_effort: str | None = None
    """Explicitly frozen (Phase 4A.3c) reasoning effort sent on every
    request; never left to the provider's default. For Anthropic this is the
    native ``output_config.effort`` value (``low``)."""
    provider_api_surface: str | None = None
    """Phase 6C: ``openai.responses`` | ``anthropic.messages``."""
    provider_request_config: dict[str, Any] | None = None
    """Phase 6C: the exact, credential-free provider request configuration
    actually sent every call (model, effort/thinking mode, max output cap,
    tool_choice mode, timeout, retries) -- the material behind
    ``provider_config_sha256``."""
    provider_config_sha256: str | None = None
    """Phase 6C: SHA-256 of the canonical provider request configuration +
    wire tool-schema hash; folded into execution fingerprint v2."""
    restricted_to_actions: list[str] | None = None
    """Phase 4A.3d: when set, the ONLY host-action tool schemas offered to
    the model on every request this run (a subset of the canonical four that
    ``tool_schema_sha256`` still fingerprints). None == the full action
    surface was offered (v1 free-run)."""
    execution_fingerprint: ExecutionFingerprint | None = None
    """Phase 4A.3e: the run's full execution fingerprint (config_hash +
    source commit + resolved overlay bundle + host policy + tool schema),
    attached to every trial's provenance by the pilot runner. None for
    non-fingerprinted callers/tests."""
    run_started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider_calls: list[ComposedProviderCallRecord] = Field(default_factory=list)

    @property
    def total_provider_calls(self) -> int:
        return len(self.provider_calls)

    @property
    def total_input_tokens(self) -> int:
        return sum(call.input_tokens or 0 for call in self.provider_calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(call.output_tokens or 0 for call in self.provider_calls)

    @property
    def total_tokens(self) -> int:
        return sum(call.total_tokens or 0 for call in self.provider_calls)
