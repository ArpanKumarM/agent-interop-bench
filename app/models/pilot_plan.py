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

from pydantic import BaseModel, Field, model_validator


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
    }
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    config_hash: str = ""

    @model_validator(mode="after")
    def _set_config_hash(self) -> PilotExperimentPlan:
        self.config_hash = _compute_config_hash(self)
        return self
