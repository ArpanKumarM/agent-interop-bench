"""The trial ledger record (Phase 4A.3a): one persisted, machine-readable
observation per pilot trial.

Every outcome field is computed only from the trial's real
``CrossProtocolEvent`` trace (via the existing, unmodified
``evaluate_propagation``/``evaluate_sensitive_egress`` evaluators and plain
event-type inspection) — never asserted, never derived from category/id
naming. A ``None`` outcome means "not applicable to this trial" (e.g.
``sensitive_egress`` for a public-twin control trial that never declares a
sensitive canary), exactly the same "never a fabricated pass/fail"
discipline every other evaluator in this project already follows.

No hidden reasoning/chain-of-thought is ever persisted here — the embedded
``ComposedModelRunProvenance`` already guarantees that (see
``app.models.composed_provenance``), and this model adds nothing that could
carry it.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.composed import CrossProtocolEvent
from app.models.composed_provenance import ComposedModelRunProvenance


class TrialOutcomes(BaseModel):
    canary_propagated: bool | None = None
    sensitive_egress: bool | None = None
    mutation_attempted: bool | None = None
    mutation_executed: bool | None = None
    task_success: bool | None = None


class TrialRecord(BaseModel):
    run_id: str
    overlay_id: str
    condition: Literal["treatment", "control"]
    trial_index: int
    trial_id: str
    """Deterministic: f"{run_id}:{overlay_id}:{trial_index}" -- the resume/
    dedup key. Never regenerated with any randomness."""

    requested_model: str
    returned_model: str | None = None
    status: Literal["completed", "failed"]
    decision_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    latency_ms_total: float

    provenance: ComposedModelRunProvenance
    events: list[CrossProtocolEvent] = Field(default_factory=list)
    outcomes: TrialOutcomes

    error: str | None = None
    termination_reason: str
    """One of: "completed_normally", "global_budget_exhausted",
    "trial_decision_budget_exhausted", "adapter_error", "runner_error"."""

    def model_dump_summary(self) -> dict[str, Any]:
        """A compact view (no full event trace/provenance) for quick
        inspection -- the full record is always in trials.jsonl regardless."""
        return {
            "trial_id": self.trial_id,
            "overlay_id": self.overlay_id,
            "condition": self.condition,
            "status": self.status,
            "termination_reason": self.termination_reason,
            "decision_count": self.decision_count,
            "outcomes": self.outcomes.model_dump(),
        }
