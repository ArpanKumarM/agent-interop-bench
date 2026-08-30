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
    """"ok" or "error"."""
    error: str | None = None
    """Sanitized, credential-free error string. None when status == "ok"."""


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
