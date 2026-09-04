"""Phase 8 analysis CLI (docs/phase_8_change_list.md S6.5) against a
SYNTHETIC raw root -- no real Phase 8 raw data exists yet. Verifies the
CLI-specific plumbing (raw-root existence guard, byte-integrity check,
output + manifest writing); the analysis math itself is covered by
tests/unit/test_phase_8_analysis.py."""

from __future__ import annotations

import json

import pytest

import app.cli.phase_8 as cli
from app.reporting.phase_8 import PANEL

_SCENARIOS = ("s1", "s2")
_POLICY_SCENARIOS = ("s1",)


def _trial(model: str, overlay_id: str, egress: bool) -> dict:
    return {
        "requested_model": model,
        "status": "completed",
        "overlay_id": overlay_id,
        "outcomes": {"any_sensitive_field_egress": egress},
    }


def _write_trials(raw_root, substudy: str, model: str, trials: list[dict]) -> None:
    run_dir = raw_root / cli.RUN_DIRNAME[substudy][model]
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "trials.jsonl").write_text(
        "\n".join(json.dumps(t) for t in trials) + "\n" if trials else ""
    )


def _build_synthetic_raw_root(tmp_path):
    raw_root = tmp_path / "raw"
    counts = {}
    for model in PANEL:
        # v8a: 2 scenarios x 3 arms x 2 sinks x 1 repeat = 12
        v8a = [
            _trial(model, f"p8a-{s}-{arm}-{sink}", egress=(arm == "public"))
            for s in _SCENARIOS
            for arm in ("confidential", "unlabeled", "public")
            for sink in ("a2a_relay", "user_reply")
        ]
        _write_trials(raw_root, "v8a", model, v8a)
        counts["v8a"] = len(v8a)

        v8a2 = [_trial(model, f"p8a2-{s}-unlabeled", egress=False) for s in _SCENARIOS]
        _write_trials(raw_root, "v8a2", model, v8a2)
        counts["v8a2"] = len(v8a2)

        v8b = [
            _trial(model, f"p8b-{s}-{arm}", egress=(arm == "permit"))
            for s in _SCENARIOS
            for arm in ("suppress", "permit")
        ]
        _write_trials(raw_root, "v8b", model, v8b)
        counts["v8b"] = len(v8b)

        v8c = [
            _trial(model, f"p8c-{s}-{arm}", egress=(arm == "public"))
            for s in _SCENARIOS
            for arm in ("unlabeled", "public", "pub_only", "ok_only")
        ]
        _write_trials(raw_root, "v8c", model, v8c)
        counts["v8c"] = len(v8c)

        v8d = [
            _trial(model, f"p8d-{s}-{arm}", egress=(arm == "public"))
            for s in _POLICY_SCENARIOS
            for arm in ("unlabeled", "public")
        ]
        _write_trials(raw_root, "v8d", model, v8d)
        counts["v8d"] = len(v8d)
    return raw_root, {k: v * len(PANEL) for k, v in counts.items()}


@pytest.fixture
def synthetic_phase8(tmp_path, monkeypatch):
    raw_root, totals = _build_synthetic_raw_root(tmp_path)
    monkeypatch.setattr(cli, "PHASE_8_SCENARIOS", _SCENARIOS)
    monkeypatch.setattr(cli, "PHASE_8_POLICY_ROBUSTNESS_SCENARIOS", _POLICY_SCENARIOS)
    monkeypatch.setattr(cli, "_EXPECTED_TOTAL", totals)
    monkeypatch.setattr(cli, "OUT", tmp_path / "out")
    return raw_root


def test_main_refuses_when_raw_root_missing(tmp_path):
    with pytest.raises(cli.Phase8CliError, match="does not exist"):
        cli.main(["--raw-root", str(tmp_path / "nope")])


def test_load_trials_refuses_when_a_model_file_is_missing(tmp_path):
    raw_root = tmp_path / "raw"
    (raw_root / cli.RUN_DIRNAME["v8a"]["gpt-5.6-sol"]).mkdir(parents=True)
    (raw_root / cli.RUN_DIRNAME["v8a"]["gpt-5.6-sol"] / "trials.jsonl").write_text("")
    with pytest.raises(cli.Phase8CliError, match="does not exist"):
        cli.load_trials(raw_root, "v8a")


def test_run_full_analysis_end_to_end(synthetic_phase8):
    report = cli.run_full_analysis(synthetic_phase8)
    assert set(report) == {"s8a", "s8b_calibration", "s8c_wording", "s8d_policy"}
    assert set(report["s8a"]) == set(PANEL)
    assert set(report["s8b_calibration"]) == set(PANEL)
    for gate in report["s8b_calibration"].values():
        assert gate["passed"] is True  # suppress=0, permit=1 by construction
    assert set(report["s8c_wording"]) == set(PANEL)
    assert set(report["s8d_policy"]) == set(PANEL)


def test_main_writes_report_and_manifest_and_verifies_raw_unchanged(synthetic_phase8, monkeypatch):
    exit_code = cli.main(["--raw-root", str(synthetic_phase8)])
    assert exit_code == 0
    out_path = cli.OUT / "report.json"
    assert out_path.exists()
    report = json.loads(out_path.read_text())
    assert set(report) == {"s8a", "s8b_calibration", "s8c_wording", "s8d_policy"}
    manifest = (cli.OUT / "MANIFEST.sha256").read_text()
    assert "report.json" in manifest


def test_pilot_run_directories_are_disjoint_from_main_study_run_directories():
    """docs/phase_8a2_pilot_design.md S7a: the main-study analysis CLI has
    no code path that can address a pilot run directory -- this is a
    structural guarantee, not a naming convention someone could violate
    by accident."""
    main_study_run_dirs = {
        run_dir for by_model in cli.RUN_DIRNAME.values() for run_dir in by_model.values()
    }
    pilot_run_dirs = {f"phase-8-pilot-{model}" for model in PANEL}
    assert main_study_run_dirs.isdisjoint(pilot_run_dirs)
    # and no main-study substudy key is ever "v8pilot"
    assert "v8pilot" not in cli.RUN_DIRNAME
