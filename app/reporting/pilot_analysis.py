"""Pilot analysis (Phase 4A.3a): per-condition rates with Wilson score
intervals, and matched treatment/control SIGNED rate differences.

Deliberately NO significance testing (no p-values, no chi-square/t-test):
pilot sample sizes are too small for that to mean anything, and reporting
one would invite exactly the "significance theater" the Phase 4A design
lock explicitly rejected. A Wilson interval is reported instead because,
unlike a normal-approximation interval, it stays well-behaved at small n
and near-0/near-1 observed proportions -- both of which are expected here.

Behavioral outcome rates (and their Wilson intervals) are computed ONLY
over trials with ``status == "completed"``. A failed trial (provider
error, global/per-trial budget exhaustion) is an immutable terminal ledger
record -- its partial trace, if any, is never inspected for outcomes, and
it never enters a rate denominator. Attrition (how many trials were
planned vs. actually completed vs. failed, and why) is reported
separately per condition so it stays visible instead of silently
disappearing from the rate.

The two research experiments (sensitive_egress, adversarial_influence) are
kept as separate top-level keys with their own denominators -- never
merged or blended, per the Phase 4A design lock's explicit requirement.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict

from pydantic import BaseModel

from app.models.live_overlay import LiveExperimentOverlay
from app.models.pilot_plan import PilotExperimentPlan
from app.models.trial_ledger import TrialRecord

_Z_95 = 1.96

_OUTCOME_FIELDS_BY_EXPERIMENT: dict[str, list[str]] = {
    "sensitive_egress": ["canary_propagated", "sensitive_egress"],
    "adversarial_influence": ["mutation_attempted", "mutation_executed", "task_success"],
}


class ConditionStats(BaseModel):
    n: int
    successes: int
    rate: float | None
    ci_low: float | None
    ci_high: float | None


class AttritionStats(BaseModel):
    trials_planned: int
    trials_recorded: int
    trials_completed: int
    trials_failed: int
    failure_reasons: dict[str, int]


def wilson_interval(successes: int, n: int, z: float = _Z_95) -> tuple[float, float]:
    """The Wilson score interval for a binomial proportion. ``n`` must be > 0."""
    if n <= 0:
        raise ValueError("wilson_interval requires n > 0")
    phat = successes / n
    z2 = z * z
    denominator = 1 + z2 / n
    center = phat + z2 / (2 * n)
    margin = z * math.sqrt((phat * (1 - phat) + z2 / (4 * n)) / n)
    low = (center - margin) / denominator
    high = (center + margin) / denominator
    return max(0.0, low), min(1.0, high)


def compute_condition_stats(records: list[TrialRecord], outcome_field: str) -> ConditionStats:
    """Behavioral outcome rate over COMPLETED, applicable trials only.
    A failed trial's outcomes are always all-``None`` (see
    ``app.runner.pilot_runner``) and its ``status != "completed"`` filter
    here is a second, independent guard against a failed/partial trace
    ever contributing to this denominator."""
    applicable = [
        getattr(record.outcomes, outcome_field)
        for record in records
        if record.status == "completed" and getattr(record.outcomes, outcome_field) is not None
    ]
    n = len(applicable)
    if n == 0:
        return ConditionStats(n=0, successes=0, rate=None, ci_low=None, ci_high=None)
    successes = sum(1 for value in applicable if value)
    rate = successes / n
    ci_low, ci_high = wilson_interval(successes, n)
    return ConditionStats(n=n, successes=successes, rate=rate, ci_low=ci_low, ci_high=ci_high)


def compute_attrition_stats(records: list[TrialRecord], trials_planned: int) -> AttritionStats:
    completed = [record for record in records if record.status == "completed"]
    failed = [record for record in records if record.status == "failed"]
    failure_reasons = Counter(record.termination_reason for record in failed)
    return AttritionStats(
        trials_planned=trials_planned,
        trials_recorded=len(records),
        trials_completed=len(completed),
        trials_failed=len(failed),
        failure_reasons=dict(failure_reasons),
    )


def compute_treatment_control_diff(treatment: ConditionStats, control: ConditionStats) -> dict:
    """``rate_difference`` (SIGNED: treatment_rate - control_rate) is the
    primary reported effect. ``absolute_difference`` is retained
    additionally for convenience, never as the primary value."""
    if treatment.rate is None or control.rate is None:
        return {
            "treatment_rate": treatment.rate,
            "control_rate": control.rate,
            "rate_difference": None,
            "absolute_difference": None,
        }
    rate_difference = treatment.rate - control.rate
    return {
        "treatment_rate": treatment.rate,
        "control_rate": control.rate,
        "rate_difference": rate_difference,
        "absolute_difference": abs(rate_difference),
    }


def compute_summary(
    plan: PilotExperimentPlan,
    overlays: list[LiveExperimentOverlay],
    records: list[TrialRecord],
) -> dict:
    overlays_by_id = {overlay.id: overlay for overlay in overlays}

    grouped: dict[tuple[str, str], list[TrialRecord]] = defaultdict(list)
    for record in records:
        overlay = overlays_by_id[record.overlay_id]
        grouped[(overlay.experiment, overlay.condition)].append(record)

    planned_overlay_count: dict[tuple[str, str], int] = defaultdict(int)
    for overlay_id in plan.overlay_ids:
        overlay = overlays_by_id[overlay_id]
        planned_overlay_count[(overlay.experiment, overlay.condition)] += 1

    experiments: dict[str, dict] = {}
    for experiment_name, fields in _OUTCOME_FIELDS_BY_EXPERIMENT.items():
        treatment_records = grouped.get((experiment_name, "treatment"), [])
        control_records = grouped.get((experiment_name, "control"), [])
        if not treatment_records and not control_records:
            continue

        treatment_planned = (
            planned_overlay_count.get((experiment_name, "treatment"), 0) * plan.trials_per_condition
        )
        control_planned = (
            planned_overlay_count.get((experiment_name, "control"), 0) * plan.trials_per_condition
        )

        experiment_summary: dict[str, dict] = {
            "treatment": {
                "attrition": compute_attrition_stats(
                    treatment_records, treatment_planned
                ).model_dump(),
                "outcomes": {},
            },
            "control": {
                "attrition": compute_attrition_stats(control_records, control_planned).model_dump(),
                "outcomes": {},
            },
            "treatment_vs_control": {},
        }
        for field in fields:
            treatment_stats = compute_condition_stats(treatment_records, field)
            control_stats = compute_condition_stats(control_records, field)
            experiment_summary["treatment"]["outcomes"][field] = treatment_stats.model_dump()
            experiment_summary["control"]["outcomes"][field] = control_stats.model_dump()
            experiment_summary["treatment_vs_control"][field] = compute_treatment_control_diff(
                treatment_stats, control_stats
            )
        experiments[experiment_name] = experiment_summary

    return {
        "run_id": plan.experiment_id,
        "model": plan.model,
        "config_hash": plan.config_hash,
        "total_trials_recorded": len(records),
        "experiments": experiments,
    }
