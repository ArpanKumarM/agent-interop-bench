"""Provenance for real-model (non-deterministic) runs.

Kept deliberately separate from ``TurnResult``/``RunResult`` (the canonical,
provider-agnostic scientific interaction trace — see
``app.models.execution``): a real model's identity, the exact policy it was
given, and its observed token/call usage are audit metadata about *how* a
run was produced, not something any evaluator scores. A deterministic run
never has any of this; ``Report.model_provenance`` is ``None`` for every
deterministic run and is the single, unambiguous signal that a report came
from a live model instead of the free, reproducible fixture adapter.

Nothing here ever holds a credential: no API key, authorization header,
environment dump, hidden reasoning/chain-of-thought, or raw SDK object is
persisted — only benchmark-relevant, already-public-by-nature model/tool
behavior (which model, which policy, how many tokens, how many calls).
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ProviderCallRecord(BaseModel):
    """One call made to a model provider during a live-model run."""

    case_id: str
    turn_index: int
    provider_response_id: str | None = None
    requested_model: str
    returned_model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    status: str
    """"ok" or "error"."""
    error: str | None = None
    """Sanitized, credential-free error string. None when status == "ok"."""


class ModelRunProvenance(BaseModel):
    """Full audit record for a live-model run, attached to ``Report.model_provenance``.

    Answers: exactly which model, given exactly which policy and tool
    schemas, under exactly which cost-safety configuration, made exactly
    how many calls consuming exactly how many tokens. A future re-run with
    the same configuration is not guaranteed to reproduce the same scores —
    that non-determinism is the whole reason this provenance exists.
    """

    adapter_type: str
    provider: str
    requested_model: str
    baseline_policy_version: str
    baseline_policy_sha256: str
    tool_schema_sha256: str
    configured_timeout_seconds: float
    configured_max_retries: int
    configured_max_output_tokens: int
    run_started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider_calls: list[ProviderCallRecord] = Field(default_factory=list)

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
