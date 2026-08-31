"""Phase 6B pairwise analysis: pair-level rates + paired differences + sign
summary + pooled rates + mean/median + seeded bootstrap over the 10 pairs.
Deterministic; no p-values."""

from __future__ import annotations

from app.models.composed_provenance import ComposedModelRunProvenance
from app.models.trial_ledger import TrialOutcomes, TrialRecord
from app.reporting.pilot_analysis import (
    _pair_bootstrap_ci,
    _parse_phase_6b_overlay,
    compute_pairwise_summary,
)


def test_parse_overlay_id():
    assert _parse_phase_6b_overlay("rq1-saas-support-confidential") == (
        "sensitive_egress",
        "saas-support",
        "treatment",
    )
    assert _parse_phase_6b_overlay("rq2-rollback-orders-benign") == (
        "adversarial_influence",
        "rollback-orders",
        "control",
    )
    assert _parse_phase_6b_overlay("live-influence-treatment") is None


def _rec(overlay_id: str, condition: str, **outcome_kwargs) -> TrialRecord:
    prov = ComposedModelRunProvenance(
        adapter_type="x",
        provider="none",
        requested_model="m",
        host_policy_sha256="0" * 64,
        tool_schema_sha256="0" * 64,
        configured_timeout_seconds=1.0,
        configured_max_retries=0,
        configured_max_output_tokens=1,
    )
    return TrialRecord(
        run_id="composed-live-canary-004",
        overlay_id=overlay_id,
        condition=condition,
        trial_index=0,
        trial_id=f"x:{overlay_id}:0",
        requested_model="m",
        status="completed",
        decision_count=1,
        total_input_tokens=0,
        total_output_tokens=0,
        total_tokens=0,
        latency_ms_total=0.0,
        provenance=prov,
        events=[],
        outcomes=TrialOutcomes(**outcome_kwargs),
        termination_reason="completed_normally",
    )


def test_pairwise_summary_rq2():
    records: list[TrialRecord] = []
    # pair A: treatment 3/4 mutating, control 1/4 -> diff +0.5
    for i in range(4):
        records.append(
            _rec("rq2-rollback-orders-adversarial", "treatment", mutating_tool_requested=(i < 3))
        )
        records.append(
            _rec("rq2-rollback-orders-benign", "control", mutating_tool_requested=(i < 1))
        )
    # pair B: treatment 2/4, control 2/4 -> diff 0.0
    for i in range(4):
        records.append(
            _rec("rq2-purge-pricing-adversarial", "treatment", mutating_tool_requested=(i < 2))
        )
        records.append(_rec("rq2-purge-pricing-benign", "control", mutating_tool_requested=(i < 2)))
    out = compute_pairwise_summary(records)
    ai = out["adversarial_influence"]
    assert ai["primary_outcome"] == "mutating_tool_requested"
    assert ai["n_pairs"] == 2
    diffs = sorted(p["paired_difference"] for p in ai["pairs"])
    assert diffs == [0.0, 0.5]
    assert ai["sign_summary"] == {
        "treatment_gt_control": 1,
        "treatment_eq_control": 1,
        "treatment_lt_control": 0,
    }
    assert ai["pair_difference_mean"] == 0.25
    assert ai["pair_difference_median"] == 0.25
    assert ai["pooled_rates"]["treatment"]["successes"] == 5
    assert ai["pooled_rates"]["treatment"]["n"] == 8
    assert "IGNORE between-pair" in ai["pooled_rates"]["note"]
    assert ai["no_p_values"] is True


def test_pair_bootstrap_is_deterministic_and_over_pairs():
    diffs = [0.5, 0.25, 0.0, 0.75, -0.25, 0.5, 0.25, 0.0, 0.5, 0.25]
    a = _pair_bootstrap_ci(diffs)
    b = _pair_bootstrap_ci(diffs)
    assert a == b
    assert a["resamples"] == 10_000
    assert a["ci_low"] <= a["ci_high"]


def test_no_pairwise_when_not_phase_6b():
    assert compute_pairwise_summary([_rec("live-influence-treatment", "treatment")]) is None
