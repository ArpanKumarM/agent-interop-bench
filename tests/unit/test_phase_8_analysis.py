"""Phase 8 analysis engine (docs/phase_8_design.md S7) against a
SYNTHETIC fixture -- no real Phase 8 raw data exists yet. Every expected
contrast value is hand-computed against the fixture below."""

from __future__ import annotations

import math

import pytest

from app.reporting.phase_8 import (
    PANEL,
    Phase8AnalysisError,
    analyze_s8a,
    analyze_s8b_calibration,
    analyze_s8c_wording,
    calibration_gate,
    cell_rate,
    contrast,
    parse_overlay_id,
    scenario_rates,
    validate_structure,
)

_SCENARIOS = ("s1", "s2", "s3")


def _trial(model: str, overlay_id: str, egress: bool, idx: int) -> dict:
    return {
        "requested_model": model,
        "status": "completed",
        "overlay_id": overlay_id,
        "trial_index": idx,
        "outcomes": {"any_sensitive_field_egress": egress},
    }


# gpt-5.6-sol a2a_relay rates by (scenario, arm): k out of 4
_SOL_A2A = {
    ("s1", "confidential"): 0,
    ("s1", "unlabeled"): 0,
    ("s1", "public"): 2,
    ("s2", "confidential"): 0,
    ("s2", "unlabeled"): 1,
    ("s2", "public"): 3,
    ("s3", "confidential"): 1,
    ("s3", "unlabeled"): 1,
    ("s3", "public"): 1,
}


def _build_trials_by_model() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {m: [] for m in PANEL}
    for scenario in _SCENARIOS:
        for arm in ("confidential", "unlabeled", "public"):
            k_sol = _SOL_A2A[(scenario, arm)]
            for i in range(4):
                out["gpt-5.6-sol"].append(
                    _trial(
                        "gpt-5.6-sol",
                        f"p8a-{scenario}-{arm}-a2a_relay",
                        egress=i < k_sol,
                        idx=i,
                    )
                )
                # user_reply: all zero for gpt-5.6-sol
                out["gpt-5.6-sol"].append(
                    _trial(
                        "gpt-5.6-sol", f"p8a-{scenario}-{arm}-user_reply", egress=False, idx=i
                    )
                )
            # every other panel member: flat zero, both sinks
            for model in PANEL:
                if model == "gpt-5.6-sol":
                    continue
                for sink in ("a2a_relay", "user_reply"):
                    for i in range(4):
                        out[model].append(
                            _trial(model, f"p8a-{scenario}-{arm}-{sink}", egress=False, idx=i)
                        )
    return out


def test_parse_overlay_id_all_substudy_shapes():
    assert parse_overlay_id("p8a-saas-support-unlabeled-a2a_relay") == (
        "v8a",
        "saas-support",
        "unlabeled",
        "a2a_relay",
    )
    assert parse_overlay_id("p8a-saas-support-unlabeled-user_reply") == (
        "v8a",
        "saas-support",
        "unlabeled",
        "user_reply",
    )
    assert parse_overlay_id("p8a2-saas-support-public") == (
        "v8a2",
        "saas-support",
        "public",
        "a2a_relay",
    )
    assert parse_overlay_id("p8b-saas-support-suppress") == (
        "v8b",
        "saas-support",
        "suppress",
        "a2a_relay",
    )
    assert parse_overlay_id("p8c-saas-support-pub_only") == (
        "v8c",
        "saas-support",
        "pub_only",
        "a2a_relay",
    )
    assert parse_overlay_id("p8d-saas-support-public") == (
        "v8d",
        "saas-support",
        "public",
        "a2a_relay",
    )


def test_parse_overlay_id_rejects_unknown_prefix():
    with pytest.raises(Phase8AnalysisError):
        parse_overlay_id("not-a-phase8-overlay")


def test_cell_rate_and_scenario_rates_match_fixture():
    trials = _build_trials_by_model()["gpt-5.6-sol"]
    assert cell_rate(trials, "s1", "public", "a2a_relay") == (2, 4)
    assert cell_rate(trials, "s2", "unlabeled", "a2a_relay") == (1, 4)
    rates = scenario_rates(trials, _SCENARIOS, "public", "a2a_relay")
    assert rates == {"s1": 0.5, "s2": 0.75, "s3": 0.25}


def test_validate_structure_ok_and_rejects_wrong_total():
    trials = _build_trials_by_model()
    total = sum(len(v) for v in trials.values())
    validate_structure(trials, total)  # no raise
    with pytest.raises(Phase8AnalysisError, match="expected"):
        validate_structure(trials, total + 1)


def test_validate_structure_rejects_wrong_panel():
    with pytest.raises(Phase8AnalysisError, match="model set mismatch"):
        validate_structure({"not-a-model": []}, 0)


def test_contrast_hand_computed_c_minus_n_a2a():
    trials = _build_trials_by_model()["gpt-5.6-sol"]
    c = contrast(trials, _SCENARIOS, "confidential", "unlabeled", "a2a_relay")
    assert c["diffs"] == [0.0, -0.25, 0.0]
    assert math.isclose(c["mean"], -0.25 / 3)
    assert c["median"] == 0.0
    assert c["sign_counts"] == {"positive": 0, "zero": 2, "negative": 1}


def test_contrast_hand_computed_p_minus_n_a2a():
    trials = _build_trials_by_model()["gpt-5.6-sol"]
    c = contrast(trials, _SCENARIOS, "public", "unlabeled", "a2a_relay")
    assert c["diffs"] == [0.5, 0.5, 0.0]
    assert math.isclose(c["mean"], 1.0 / 3)
    assert c["median"] == 0.5
    assert c["sign_counts"] == {"positive": 2, "zero": 1, "negative": 0}


def test_contrast_hand_computed_c_minus_p_a2a():
    trials = _build_trials_by_model()["gpt-5.6-sol"]
    c = contrast(trials, _SCENARIOS, "confidential", "public", "a2a_relay")
    assert c["diffs"] == [-0.5, -0.75, 0.0]
    assert math.isclose(c["mean"], -1.25 / 3)
    assert c["median"] == -0.5
    assert c["sign_counts"] == {"positive": 0, "zero": 1, "negative": 2}


def test_contrast_user_reply_is_all_zero_for_flat_fixture():
    trials = _build_trials_by_model()["gpt-5.6-sol"]
    c = contrast(trials, _SCENARIOS, "public", "unlabeled", "user_reply")
    assert c["diffs"] == [0.0, 0.0, 0.0]
    assert c["mean"] == 0.0


def test_analyze_s8a_sink_interaction_matches_hand_computation():
    trials = _build_trials_by_model()
    report = analyze_s8a(trials, _SCENARIOS)
    interaction = report["gpt-5.6-sol"]["sink_interaction_P_minus_N"]
    assert interaction["deltas"] == [0.5, 0.5, 0.0]
    assert math.isclose(interaction["mean"], 1.0 / 3)
    assert interaction["sign_counts"] == {"positive": 2, "zero": 1, "negative": 0}
    # every other model is flat zero in both sinks -> zero interaction
    for model in PANEL:
        if model == "gpt-5.6-sol":
            continue
        assert report[model]["sink_interaction_P_minus_N"]["deltas"] == [0.0, 0.0, 0.0]


def test_analyze_s8a_holm_adjusted_p_at_least_raw_p():
    trials = _build_trials_by_model()
    report = analyze_s8a(trials, _SCENARIOS)
    for sink_block in report["gpt-5.6-sol"]["by_sink"].values():
        for c in sink_block.values():
            assert c["permutation_p_holm"] >= c["permutation_p"] - 1e-12


def test_analyze_s8a_covers_full_panel():
    trials = _build_trials_by_model()
    report = analyze_s8a(trials, _SCENARIOS)
    assert set(report) == set(PANEL)
    for model_report in report.values():
        assert set(model_report["by_sink"]) == {"a2a_relay", "user_reply"}


def test_calibration_gate_passes_when_separated():
    scenarios = ("s1", "s2")
    trials = []
    for scenario in scenarios:
        for r in range(4):
            trials.append(
                _trial("gpt-5.6-sol", f"p8b-{scenario}-suppress", egress=False, idx=r)
            )
            trials.append(
                _trial("gpt-5.6-sol", f"p8b-{scenario}-permit", egress=True, idx=r)
            )
    gate = calibration_gate(trials, scenarios)
    assert gate["suppress_rate"] == 0.0
    assert gate["permit_rate"] == 1.0
    assert gate["passed"] is True


def test_calibration_gate_fails_when_not_separated():
    scenarios = ("s1",)
    trials = [
        _trial("gpt-5.6-sol", "p8b-s1-suppress", egress=True, idx=0),
        _trial("gpt-5.6-sol", "p8b-s1-permit", egress=False, idx=0),
    ]
    gate = calibration_gate(trials, scenarios)
    assert gate["passed"] is False


def test_analyze_s8b_calibration_over_full_panel():
    trials_by_model = {}
    for model in PANEL:
        trials_by_model[model] = [
            _trial(model, "p8b-s1-suppress", egress=False, idx=0),
            _trial(model, "p8b-s1-permit", egress=True, idx=0),
        ]
    report = analyze_s8b_calibration(trials_by_model, scenarios=("s1",))
    assert set(report) == set(PANEL)
    for gate in report.values():
        assert gate["passed"] is True


def test_analyze_s8c_wording_shapes():
    scenarios = ("s1",)
    trials_by_model = {}
    for model in PANEL:
        trials = []
        for arm in ("unlabeled", "public", "pub_only", "ok_only"):
            for i in range(4):
                trials.append(_trial(model, f"p8c-s1-{arm}", egress=(arm == "public"), idx=i))
        trials_by_model[model] = trials
    report = analyze_s8c_wording(trials_by_model, scenarios)
    assert set(report) == set(PANEL)
    for contrasts in report.values():
        assert set(contrasts) == {
            "pub_only_minus_N",
            "ok_only_minus_N",
            "P_minus_pub_only",
            "P_minus_ok_only",
        }
        assert contrasts["P_minus_pub_only"]["diffs"] == [1.0]
