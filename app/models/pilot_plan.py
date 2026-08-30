"""The pilot experiment plan (Phase 4A.3a): everything needed to
reproduce, resume, or refuse-to-resume one composed real-model pilot run.

Deliberately does not hard-code a production model — ``model`` is a plain
required string the caller supplies; nothing in this module chooses one.

``config_hash`` is always derived from the plan's own substantive fields
(never independently settable, and never includes ``created_at``, since two
runs of the identical methodology started at different times must still be
recognized as the same experiment for resume purposes) — see
``TrialLedger.write_or_verify_plan`` in ``app.runner.pilot_ledger`` for how
this refuses a resume against a changed configuration.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# The v1 free-run execution mode: the real host is asked for every decision
# in an open ComposedBenchmarkRunner step loop. "decision_point" (Phase
# 4A.3d) is a NEW mode that deterministically bootstraps the trace up to the
# single decision each experiment is designed to measure, then asks the real
# host exactly once with a restricted action set -- see
# app.runner.decision_point_pilot.
ExecutionMode = Literal["free_run", "decision_point"]
_DEFAULT_EXECUTION_MODE: ExecutionMode = "free_run"


def _compute_config_hash(plan: PilotExperimentPlan) -> str:
    payload = {
        "experiment_id": plan.experiment_id,
        "experiment_version": plan.experiment_version,
        "model": plan.model,
        "overlay_ids": sorted(plan.overlay_ids),
        "trials_per_condition": plan.trials_per_condition,
        "max_decisions_per_trial": plan.max_decisions_per_trial,
        "max_total_decisions": plan.max_total_decisions,
        "timeout_seconds": plan.timeout_seconds,
        "max_output_tokens": plan.max_output_tokens,
        "reasoning_effort": plan.reasoning_effort,
    }
    # Only folded in when it is NOT the v1 default, so every already-frozen v1
    # plan (which never carried this key) keeps its exact committed
    # config_hash -- b7df0171... -- byte for byte, while a decision_point plan
    # necessarily hashes differently.
    if plan.execution_mode != _DEFAULT_EXECUTION_MODE:
        payload["execution_mode"] = plan.execution_mode
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class PilotExperimentPlan(BaseModel):
    experiment_id: str
    experiment_version: str
    model: str
    overlay_ids: list[str]
    trials_per_condition: int = Field(ge=1)
    # Per-trial provider-decision cap (passed to RealHostAgentAdapter's own
    # max_decisions) -- independent of the GLOBAL cap below.
    max_decisions_per_trial: int = Field(ge=1)
    # The GLOBAL provider-decision budget for the ENTIRE run, across every
    # trial and every overlay -- checked before every single provider call
    # (see app.runner.pilot_budget.GlobalDecisionBudget). Trials are not the
    # billing unit; provider decisions are.
    max_total_decisions: int = Field(ge=1)
    timeout_seconds: float = Field(gt=0)
    max_output_tokens: int = Field(ge=1)
    # Explicitly frozen (Phase 4A.3c): never rely on the provider's default
    # reasoning effort. Sent verbatim on every request by RealHostAgentAdapter
    # -- see app.runner.real_host_adapter.
    reasoning_effort: str = "low"
    # v1 plans omit this entirely (-> "free_run"); a Phase 4A.3d decision-point
    # plan sets it to "decision_point". Part of config_hash only when non-default.
    execution_mode: ExecutionMode = _DEFAULT_EXECUTION_MODE
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    config_hash: str = ""

    @model_validator(mode="after")
    def _set_config_hash(self) -> PilotExperimentPlan:
        self.config_hash = _compute_config_hash(self)
        return self
