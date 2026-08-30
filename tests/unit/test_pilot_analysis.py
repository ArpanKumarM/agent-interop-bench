"""Unit tests for Wilson intervals and treatment/control diffs, using
hand-verifiable reference values (Phase 4A.3a) -- no scipy/statistics
dependency, plain closed-form Wilson score formula."""

from __future__ import annotations

import pytest

from app.models.composed_provenance import ComposedModelRunProvenance
from app.models.trial_ledger import TrialOutcomes, TrialRecord
from app.reporting.pilot_analysis import (
    ConditionStats,
    compute_attrition_stats,
    compute_condition_stats,
    compute_treatment_control_diff,
    wilson_interval,
)


def _provenance() -> ComposedModelRunProvenance:
    return ComposedModelRunProvenance(
        adapter_type="fake",
        provider="fake",
        requested_model="fake-model",
        host_policy_sha256="x" * 64,
        tool_schema_sha256="y" * 64,
        configured_timeout_seconds=5.0,
        configured_max_retries=0,
        configured_max_output_tokens=100,
    )


def _record(
    trial_index: int,
    status: str,
    termination_reason: str,
    outcomes: TrialOutcomes | None = None,
) -> TrialRecord:
    return TrialRecord(
        run_id="run-1",
        overlay_id="overlay-1",
        condition="treatment",
        trial_index=trial_index,
        trial_id=f"run-1:overlay-1:{trial_index}",
        requested_model="fake-model",
        status=status,
        decision_count=1,
        total_input_tokens=0,
        total_output_tokens=0,
        total_tokens=0,
        latency_ms_total=0.0,
        provenance=_provenance(),
        events=[],
        outcomes=outcomes or TrialOutcomes(),
        termination_reason=termination_reason,
    )


def test_wilson_interval_n1_x1_matches_hand_computed_reference():
    low, high = wilson_interval(successes=1, n=1)
    assert low == pytest.approx(0.2065, abs=1e-3)
    assert high == pytest.approx(1.0, abs=1e-9)


def test_wilson_interval_n1_x0_matches_hand_computed_reference():
    low, high = wilson_interval(successes=0, n=1)
    assert low == pytest.approx(0.0, abs=1e-9)
    assert high == pytest.approx(0.7935, abs=1e-3)


def test_wilson_interval_n10_x5_matches_hand_computed_reference():
    low, high = wilson_interval(successes=5, n=10)
    assert low == pytest.approx(0.2367, abs=1e-3)
    assert high == pytest.approx(0.7634, abs=1e-3)


def test_wilson_interval_bounds_always_within_zero_one():
    for n in (1, 2, 5, 20, 100):
        for successes in range(n + 1):
            low, high = wilson_interval(successes, n)
            assert 0.0 <= low <= high <= 1.0


def test_wilson_interval_rejects_zero_n():
    with pytest.raises(ValueError, match="n > 0"):
        wilson_interval(successes=0, n=0)


def test_treatment_control_diff_is_signed_not_absolute_only():
    treatment = ConditionStats(n=10, successes=8, rate=0.8, ci_low=0.4, ci_high=0.95)
    control = ConditionStats(n=10, successes=2, rate=0.2, ci_low=0.05, ci_high=0.6)
    diff = compute_treatment_control_diff(treatment, control)
    assert diff["treatment_rate"] == 0.8
    assert diff["control_rate"] == 0.2
    assert diff["rate_difference"] == pytest.approx(0.6)
    assert diff["absolute_difference"] == pytest.approx(0.6)


def test_treatment_control_diff_rate_difference_is_negative_when_control_higher():
    """The primary effect must be signed: treatment_rate - control_rate,
    never abs(treatment_rate - control_rate)."""
    treatment = ConditionStats(n=10, successes=2, rate=0.2, ci_low=0.05, ci_high=0.6)
    control = ConditionStats(n=10, successes=8, rate=0.8, ci_low=0.4, ci_high=0.95)
    diff = compute_treatment_control_diff(treatment, control)
    assert diff["rate_difference"] == pytest.approx(-0.6)
    assert diff["absolute_difference"] == pytest.approx(0.6)  # retained, but not primary


def test_treatment_control_diff_not_applicable_when_either_side_has_no_data():
    treatment = ConditionStats(n=0, successes=0, rate=None, ci_low=None, ci_high=None)
    control = ConditionStats(n=10, successes=2, rate=0.2, ci_low=0.05, ci_high=0.6)
    diff = compute_treatment_control_diff(treatment, control)
    assert diff["treatment_rate"] is None
    assert diff["rate_difference"] is None
    assert diff["absolute_difference"] is None


def test_compute_condition_stats_excludes_failed_trials_from_denominator():
    records = [
        _record(0, "completed", "completed_normally", TrialOutcomes(mutation_attempted=True)),
        _record(1, "completed", "completed_normally", TrialOutcomes(mutation_attempted=True)),
        # A failed trial with a non-None outcome would be a bug elsewhere,
        # but even if one somehow existed, it must never be counted here.
        _record(2, "failed", "adapter_error", TrialOutcomes(mutation_attempted=True)),
    ]
    stats = compute_condition_stats(records, "mutation_attempted")
    assert stats.n == 2  # the failed trial's outcome is excluded, not counted as a 3rd success
    assert stats.successes == 2
    assert stats.rate == 1.0


def test_compute_condition_stats_treats_none_outcome_as_not_applicable():
    records = [
        _record(0, "completed", "completed_normally", TrialOutcomes(sensitive_egress=None)),
        _record(1, "completed", "completed_normally", TrialOutcomes(sensitive_egress=True)),
    ]
    stats = compute_condition_stats(records, "sensitive_egress")
    assert stats.n == 1
    assert stats.successes == 1


def test_compute_attrition_stats_counts_and_reasons():
    records = [
        _record(0, "completed", "completed_normally"),
        _record(1, "completed", "completed_normally"),
        _record(2, "failed", "global_budget_exhausted"),
        _record(3, "failed", "adapter_error"),
        _record(4, "failed", "adapter_error"),
    ]
    stats = compute_attrition_stats(records, trials_planned=5)
    assert stats.trials_planned == 5
    assert stats.trials_recorded == 5
    assert stats.trials_completed == 2
    assert stats.trials_failed == 3
    assert stats.failure_reasons == {"global_budget_exhausted": 1, "adapter_error": 2}


def test_compute_attrition_stats_with_no_records_yet():
    stats = compute_attrition_stats([], trials_planned=10)
    assert stats.trials_planned == 10
    assert stats.trials_recorded == 0
    assert stats.trials_completed == 0
    assert stats.trials_failed == 0
    assert stats.failure_reasons == {}


def test_no_p_value_or_significance_field_exists_anywhere_in_condition_stats():
    stats = ConditionStats(n=10, successes=5, rate=0.5, ci_low=0.24, ci_high=0.76)
    dumped = stats.model_dump()
    for banned in ("p_value", "pvalue", "significant", "significance", "confidence_level_test"):
        assert banned not in dumped
