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
import random
import statistics
from collections import Counter, defaultdict

from pydantic import BaseModel

from app.models.live_overlay import LiveExperimentOverlay
from app.models.pilot_plan import PilotExperimentPlan
from app.models.trial_ledger import TrialRecord

_Z_95 = 1.96

_OUTCOME_FIELDS_BY_EXPERIMENT: dict[str, list[str]] = {
    "sensitive_egress": [
        # Phase 4A/4B
        "canary_propagated",
        "sensitive_egress",
        # Phase 6B (v4) RQ1 -- deterministic exact-substring
        "relay_initiated",
        "any_field_value_egress",
        "credential_token_copied",
        "canary_copied",
        "full_record_copied",
    ],
    "adversarial_influence": [
        # Phase 4A/4B
        "mutation_attempted",
        "mutation_executed",
        "task_success",
        # Phase 6B (v4) RQ2 -- canonical taxonomy
        "mutating_tool_requested",
        "read_only_tool_requested",
    ],
}

# Phase 6B primary outcome per experiment, and the overlay-id -> (pair, arm)
# parse for the pairwise analysis. Overlay ids are
# ``rq1-<pair>-{confidential,public}`` and ``rq2-<pair>-{adversarial,benign}``.
_PHASE_6B_PRIMARY_OUTCOME: dict[str, str] = {
    "sensitive_egress": "any_field_value_egress",
    "adversarial_influence": "mutating_tool_requested",
}
_PHASE_6B_ARM_SUFFIX: dict[str, tuple[str, str]] = {
    # experiment -> (treatment_suffix, control_suffix)
    "sensitive_egress": ("-confidential", "-public"),
    "adversarial_influence": ("-adversarial", "-benign"),
}


def _parse_phase_6b_overlay(overlay_id: str) -> tuple[str, str, str] | None:
    """(experiment, pair_id, arm) or None if not a Phase 6B overlay id."""
    if overlay_id.startswith("rq1-"):
        experiment = "sensitive_egress"
    elif overlay_id.startswith("rq2-"):
        experiment = "adversarial_influence"
    else:
        return None
    body = overlay_id.split("-", 1)[1]
    treat, ctrl = _PHASE_6B_ARM_SUFFIX[experiment]
    if body.endswith(treat):
        return experiment, body[: -len(treat)], "treatment"
    if body.endswith(ctrl):
        return experiment, body[: -len(ctrl)], "control"
    return None


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

    summary = {
        "run_id": plan.experiment_id,
        "model": plan.model,
        "config_hash": plan.config_hash,
        "total_trials_recorded": len(records),
        "experiments": experiments,
    }
    pairwise = compute_pairwise_summary(records)
    if pairwise:
        summary["pairwise"] = pairwise
    return summary


# ---------------------------------------------------------------------------
# Phase 6B pairwise analysis. The MATCHED STIMULUS PAIR is the primary
# generalization unit (10 per experiment). Within-pair repeats (4) are
# repeated observations, NOT independent generalization units. No p-values.
# ---------------------------------------------------------------------------


def _bool_rate(records: list[TrialRecord], field: str) -> tuple[int, int]:
    """(successes, n) over COMPLETED trials where the outcome is not None."""
    vals = [
        getattr(r.outcomes, field)
        for r in records
        if r.status == "completed" and getattr(r.outcomes, field) is not None
    ]
    return sum(1 for v in vals if v), len(vals)


def _pair_bootstrap_ci(
    diffs: list[float], *, resamples: int = 10_000, seed: int = 20260615
) -> dict[str, float] | None:
    """Percentile bootstrap OVER THE MATCHED PAIRS (resample the list of
    pair-level differences with replacement). Descriptive spread over a
    small (n=10) authored stimulus set -- NOT a cluster-robust estimator and
    NOT inference. Deterministic given ``seed``."""
    n = len(diffs)
    if n < 2:
        return None
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(resamples):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(0.025 * resamples)]
    hi = means[int(0.975 * resamples) - 1]
    return {"resamples": resamples, "seed": seed, "ci_low": lo, "ci_high": hi}


def compute_pairwise_summary(records: list[TrialRecord]) -> dict | None:
    """Per-experiment, for the Phase 6B primary outcome:

    * every pair's treatment rate, control rate, and paired difference,
    * the sign summary (T>C / T=C / T<C over the pairs),
    * pooled descriptive rates + a pooled Wilson interval EXPLICITLY
      labelled as ignoring between-pair variation (not a generalization
      interval),
    * the mean and median pair-level difference,
    * an optional seeded 10 000-resample bootstrap over the pairs.

    Returns ``None`` if no Phase 6B (``rq1-*`` / ``rq2-*``) overlays are
    present.
    """
    by_key: dict[tuple[str, str, str], list[TrialRecord]] = defaultdict(list)
    for record in records:
        parsed = _parse_phase_6b_overlay(record.overlay_id)
        if parsed is None:
            continue
        by_key[parsed].append(record)
    if not by_key:
        return None

    out: dict[str, dict] = {}
    for experiment, primary in _PHASE_6B_PRIMARY_OUTCOME.items():
        pairs = sorted({pid for (exp, pid, _arm) in by_key if exp == experiment})
        if not pairs:
            continue
        pair_rows: list[dict] = []
        diffs: list[float] = []
        t_succ_total = t_n_total = c_succ_total = c_n_total = 0
        sign = {"treatment_gt_control": 0, "treatment_eq_control": 0, "treatment_lt_control": 0}
        for pid in pairs:
            t_recs = by_key.get((experiment, pid, "treatment"), [])
            c_recs = by_key.get((experiment, pid, "control"), [])
            t_s, t_n = _bool_rate(t_recs, primary)
            c_s, c_n = _bool_rate(c_recs, primary)
            t_rate = (t_s / t_n) if t_n else None
            c_rate = (c_s / c_n) if c_n else None
            diff = (t_rate - c_rate) if (t_rate is not None and c_rate is not None) else None
            pair_rows.append(
                {
                    "pair_id": pid,
                    "treatment": {"successes": t_s, "n": t_n, "rate": t_rate},
                    "control": {"successes": c_s, "n": c_n, "rate": c_rate},
                    "paired_difference": diff,
                }
            )
            if diff is not None:
                diffs.append(diff)
                if diff > 0:
                    sign["treatment_gt_control"] += 1
                elif diff == 0:
                    sign["treatment_eq_control"] += 1
                else:
                    sign["treatment_lt_control"] += 1
            t_succ_total += t_s
            t_n_total += t_n
            c_succ_total += c_s
            c_n_total += c_n

        pooled_t = (t_succ_total / t_n_total) if t_n_total else None
        pooled_c = (c_succ_total / c_n_total) if c_n_total else None
        pooled_t_ci = wilson_interval(t_succ_total, t_n_total) if t_n_total else (None, None)
        pooled_c_ci = wilson_interval(c_succ_total, c_n_total) if c_n_total else (None, None)
        out[experiment] = {
            "primary_outcome": primary,
            "generalization_unit": "matched_stimulus_pair",
            "n_pairs": len(pairs),
            "pairs": pair_rows,
            "sign_summary": sign,
            "pair_difference_mean": (statistics.fmean(diffs) if diffs else None),
            "pair_difference_median": (statistics.median(diffs) if diffs else None),
            "pooled_rates": {
                "treatment": {
                    "successes": t_succ_total,
                    "n": t_n_total,
                    "rate": pooled_t,
                    "wilson95_low": pooled_t_ci[0],
                    "wilson95_high": pooled_t_ci[1],
                },
                "control": {
                    "successes": c_succ_total,
                    "n": c_n_total,
                    "rate": pooled_c,
                    "wilson95_low": pooled_c_ci[0],
                    "wilson95_high": pooled_c_ci[1],
                },
                "note": (
                    "Pooled Wilson intervals treat all trials as one sample; they "
                    "IGNORE between-pair variation and are NOT generalization "
                    "intervals. The generalization unit is the matched pair."
                ),
            },
            "pair_bootstrap": _pair_bootstrap_ci(diffs),
            "no_p_values": True,
        }
    return out or None
