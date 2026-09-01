"""Phase 7E -- automated QA for the frozen three-arm scientific analysis.

Checks the structural invariants of ``docs/phase_7a_neutral_baseline_design.md``
section 8 against the analysis objects produced from the Phase 7D frozen raw
copies, and reconciles every generated table against those objects. No
provider call, no trial execution, no raw mutation.
"""

from __future__ import annotations

import hashlib
import json
import statistics

import pytest

from app.reporting.phase_7e_neutral import (
    ARMS,
    CONTRASTS,
    EXECUTION_SOURCE_SHA,
    FROZEN_FINAL_FINGERPRINT,
    FROZEN_RAW_ROOT,
    FROZEN_RAW_TRIALS_SHA256,
    PANEL,
    RUN_DIRNAME,
    SCENARIOS,
    load_trials,
    run_analysis,
)
from app.reporting.rq1_field_egress import PRIMARY_VALUE_FIELDS, STRUCTURED_FIELDS

_HAVE_FROZEN = all(
    (FROZEN_RAW_ROOT / run / "trials.jsonl").exists() for run in RUN_DIRNAME.values()
)
pytestmark = pytest.mark.skipif(
    not _HAVE_FROZEN, reason="Phase 7D frozen raw copies not present on this checkout"
)

_VALID_RATES = {0.0, 0.25, 0.5, 0.75, 1.0}


@pytest.fixture(scope="module")
def raw() -> dict[str, list[dict]]:
    return load_trials()


@pytest.fixture(scope="module")
def summary() -> dict:
    return run_analysis()


# --------------------------------------------------------------------------- #
# raw dataset shape (section 8, items 1-6, 15-16)
# --------------------------------------------------------------------------- #
def test_exactly_480_frozen_trials_consumed(summary):
    assert summary["structure"]["trials_consumed"] == 480


def test_exactly_120_per_model(summary):
    assert summary["structure"]["per_model"] == {m: 120 for m in PANEL}


def test_exactly_40_confidential_40_neutral_40_public_per_model(raw):
    for m, recs in raw.items():
        counts = {"confidential": 0, "neutral": 0, "public": 0}
        for r in recs:
            arm = r["overlay_id"].rsplit("-", 1)[1]
            counts[arm] += 1
        assert counts == {"confidential": 40, "neutral": 40, "public": 40}, m


def test_exactly_10_scenarios_and_4_repeats_per_cell(raw):
    for m, recs in raw.items():
        cells: dict[tuple[str, str], list[int]] = {}
        for r in recs:
            body = r["overlay_id"][len("rq1-") :]
            scenario, arm = body.rsplit("-", 1)
            cells.setdefault((scenario, arm), []).append(r["trial_index"])
        scenarios = {s for (s, _a) in cells}
        assert scenarios == set(SCENARIOS), m
        assert len(cells) == 30, m
        for key, idxs in cells.items():
            assert sorted(idxs) == [0, 1, 2, 3], (m, key)


def test_no_duplicate_trial_ids_within_model(raw):
    for m, recs in raw.items():
        ids = [r["trial_id"] for r in recs]
        assert len(ids) == len(set(ids)), m


def test_only_the_phase7_study_run_id_is_present(raw):
    run_ids = {r["run_id"] for recs in raw.values() for r in recs}
    assert run_ids == {"composed-live-canary-007a"}


def test_no_smoke_surface_leaks_into_the_dataset(raw):
    # the study action surface is {relay_to_remote, stop}; the smoke surface
    # {call_tool, stop} must never appear.
    for m, recs in raw.items():
        for r in recs:
            action = r["outcomes"]["decision_point_action"]
            assert action in {"relay_to_remote", "stop"}, (m, r["trial_id"], action)


# --------------------------------------------------------------------------- #
# provenance pins (section 8, items 7-9)
# --------------------------------------------------------------------------- #
def test_source_sha_correct_in_every_record(raw):
    for m, recs in raw.items():
        for r in recs:
            fp = r["provenance"]["execution_fingerprint"]
            assert fp["source_commit_sha"] == EXECUTION_SOURCE_SHA, (m, r["trial_id"])


def test_final_fingerprint_correct_in_every_record(raw):
    for m, recs in raw.items():
        for r in recs:
            fp = r["provenance"]["execution_fingerprint"]
            assert fp["execution_fingerprint_sha256"] == FROZEN_FINAL_FINGERPRINT[m], (
                m,
                r["trial_id"],
            )


def test_raw_trials_jsonl_hashes_equal_phase7d_freeze():
    for m, run in RUN_DIRNAME.items():
        digest = hashlib.sha256((FROZEN_RAW_ROOT / run / "trials.jsonl").read_bytes()).hexdigest()
        assert digest == FROZEN_RAW_TRIALS_SHA256[m], m


# --------------------------------------------------------------------------- #
# primary detector unchanged (section 8, item 10)
# --------------------------------------------------------------------------- #
def test_primary_detector_fields_exactly_unchanged(summary):
    assert tuple(PRIMARY_VALUE_FIELDS) == (
        "full_name",
        "email",
        "phone",
        "account_id",
        "internal_note",
        "credential_token",
    )
    assert tuple(STRUCTURED_FIELDS) == (
        "full_name",
        "email",
        "phone",
        "account_id",
        "internal_note",
    )
    assert summary["primary_value_fields"] == list(PRIMARY_VALUE_FIELDS)
    assert summary["structured_fields_for_disclosed_field_count"] == list(STRUCTURED_FIELDS)
    # the six-value primary and the five-field disclosed_field_count are distinct
    assert len(summary["primary_value_fields"]) == 6
    assert len(summary["structured_fields_for_disclosed_field_count"]) == 5
    assert "credential_token" not in summary["structured_fields_for_disclosed_field_count"]


def test_primary_outcome_is_consumed_not_rederived(summary):
    assert summary["primary_outcome"] == "any_sensitive_field_egress"


# --------------------------------------------------------------------------- #
# arithmetic (section 8, items 11-14)
# --------------------------------------------------------------------------- #
def test_scenario_rates_restricted_to_the_quarter_grid(summary):
    for m in PANEL:
        for s in SCENARIOS:
            for a in ARMS:
                rate = summary["arm_rates"][m]["scenarios"][s][a]["rate"]
                assert rate in _VALID_RATES, (m, s, a, rate)


def test_every_contrast_equals_its_arm_rate_arithmetic(summary):
    for m in PANEL:
        rates = summary["arm_rates"][m]["scenarios"]
        sc = summary["contrasts_by_model"][m]["scenario_contrasts"]
        for s in SCENARIOS:
            r = rates[s]
            assert sc[s]["C_minus_N"] == pytest.approx(
                r["confidential"]["rate"] - r["neutral"]["rate"], abs=1e-12
            )
            assert sc[s]["P_minus_N"] == pytest.approx(
                r["public"]["rate"] - r["neutral"]["rate"], abs=1e-12
            )
            assert sc[s]["C_minus_P"] == pytest.approx(
                r["confidential"]["rate"] - r["public"]["rate"], abs=1e-12
            )
            # also equals the integer-count arithmetic k_a - k_b over 4
            assert sc[s]["C_minus_N"] == pytest.approx(
                (r["confidential"]["k"] - r["neutral"]["k"]) / 4, abs=1e-12
            )


def test_model_means_equal_the_mean_of_the_ten_scenario_contrasts(summary):
    for m in PANEL:
        sc = summary["contrasts_by_model"][m]["scenario_contrasts"]
        for c in CONTRASTS:
            b = summary["contrasts_by_model"][m]["summary"][c]
            recomputed = statistics.fmean(sc[s][c] for s in SCENARIOS)
            assert b["mean"] == pytest.approx(recomputed, abs=1e-12)
            assert len(b["ten_values"]) == 10
            assert b["ten_values"] == [sc[s][c] for s in SCENARIOS]
            assert b["median"] == pytest.approx(statistics.median(b["ten_values"]), abs=1e-12)


def test_sign_counts_sum_to_ten(summary):
    for m in PANEL:
        for c in CONTRASTS:
            sc = summary["contrasts_by_model"][m]["summary"][c]["sign_counts"]
            assert sc["positive"] + sc["zero"] + sc["negative"] == 10
            ten = summary["contrasts_by_model"][m]["summary"][c]["ten_values"]
            assert sc["positive"] == sum(1 for v in ten if v > 0)
            assert sc["zero"] == sum(1 for v in ten if v == 0)
            assert sc["negative"] == sum(1 for v in ten if v < 0)


def test_pooled_rates_equal_sum_of_scenario_counts_over_40(summary):
    for m in PANEL:
        block = summary["arm_rates"][m]
        for a in ARMS:
            k = sum(block["scenarios"][s][a]["k"] for s in SCENARIOS)
            assert block["pooled"][a]["successes"] == k
            assert block["pooled"][a]["n"] == 40
            assert block["pooled"][a]["rate"] == pytest.approx(k / 40, abs=1e-12)


# --------------------------------------------------------------------------- #
# no inferential statistics anywhere (section 8, item 17)
# --------------------------------------------------------------------------- #
def test_analysis_object_declares_no_inferential_statistics(summary):
    assert summary["no_p_values"] is True
    assert summary["no_significance_tests"] is True
    assert summary["no_bootstrap_or_intervals"] is True
    assert summary["no_cross_model_pooling"] is True
    assert summary["phase6_phase7_pooled"] is False
    assert summary["repeats_are_independent"] is False


def test_no_inferential_statistic_keys_in_analysis_object(summary):
    from app.cli.phase_7e_neutral import _FORBIDDEN_RESULT_KEYS

    seen: list[str] = []

    def _walk(obj: object) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if str(k).lower() in _FORBIDDEN_RESULT_KEYS:
                    seen.append(str(k))
                _walk(v)
        elif isinstance(obj, list):
            for v in obj:
                _walk(v)

    _walk(summary)
    assert seen == []


# --------------------------------------------------------------------------- #
# end-to-end: the CLI writes every artifact and its own QA is all-green
# (section 8, item 18 -- table <-> object reconciliation)
# --------------------------------------------------------------------------- #
def test_cli_generates_all_artifacts_and_reconciles(tmp_path, monkeypatch):
    from app.cli import phase_7e_neutral as cli

    monkeypatch.setattr(cli, "OUT", tmp_path / "phase_7e_analysis")
    rc = cli.main([])
    assert rc == 0

    out = tmp_path / "phase_7e_analysis"
    expected = {
        "analysis_summary.json",
        "arm_rates.csv",
        "scenario_rates.csv",
        "scenario_contrasts.csv",
        "model_contrast_summary.csv",
        "relay_diagnostics.csv",
        "field_diagnostics.csv",
        "phase6_phase7_descriptive_comparison.csv",
        "figure_data_scenario_contrasts.csv",
        "analysis_report.md",
        "analysis_audit.json",
        "MANIFEST.sha256",
    }
    assert expected.issubset({p.name for p in out.iterdir()})

    audit = json.loads((out / "analysis_audit.json").read_text())
    failed = [k for k, v in audit["qa"]["checks"].items() if not v]
    assert failed == [], failed
    assert audit["qa"]["forbidden_stat_hits"] == []
    assert audit["provenance"]["raw_bytes_identical_before_and_after"] is True
    assert audit["provenance"]["execution_source_sha"] == EXECUTION_SOURCE_SHA
    assert audit["no_provider_calls"] is True

    # MANIFEST lists every other artifact with its real digest
    manifest = (out / "MANIFEST.sha256").read_text().splitlines()
    listed = {ln.split("  ", 1)[1]: ln.split("  ", 1)[0] for ln in manifest if ln.strip()}
    for name in expected - {"MANIFEST.sha256"}:
        digest = hashlib.sha256((out / name).read_bytes()).hexdigest()
        assert listed[name] == digest, name


def test_cli_does_not_mutate_the_frozen_raw_copies(tmp_path, monkeypatch):
    before = {
        run: hashlib.sha256((FROZEN_RAW_ROOT / run / "trials.jsonl").read_bytes()).hexdigest()
        for run in RUN_DIRNAME.values()
    }
    from app.cli import phase_7e_neutral as cli

    monkeypatch.setattr(cli, "OUT", tmp_path / "phase_7e_analysis")
    cli.main([])
    after = {
        run: hashlib.sha256((FROZEN_RAW_ROOT / run / "trials.jsonl").read_bytes()).hexdigest()
        for run in RUN_DIRNAME.values()
    }
    assert before == after
    assert after == {RUN_DIRNAME[m]: FROZEN_RAW_TRIALS_SHA256[m] for m in PANEL}
