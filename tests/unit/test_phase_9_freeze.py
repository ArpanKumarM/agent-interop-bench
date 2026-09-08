"""Phase 9 (F3 resolution study) -- PRE-EXECUTION FREEZE guards.

Fails if any frozen Phase 9 component drifts, if the freeze artifacts stop
reproducing byte-for-byte, if the execution schedule loses a structural
property, or if the design document stops declaring itself FROZEN. These
are the freeze's regression tests -- they must keep passing untouched
until a live run is separately authorized.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_9_build_freeze import (
    MANIFEST_PATH,
    PHASE_9_FREEZE_PARENT_COMMIT,
    build_analysis_artifact,
    build_manifest_artifact,
    build_schedule_artifact,
    verify_schedule_structure,
)
from scripts.phase_9_build_freeze import (
    main as build_freeze_main,
)
from scripts.phase_9_runner_dryrun import build_trial_requests
from scripts.phase_9_runner_dryrun import main as dryrun_main
from scripts.verify_phase_9_freeze import main as verify_main

from mock_servers.phase_9_fixtures import (
    PHASE_9_ARMS,
    PHASE_9_MODEL_PANEL,
    PHASE_9_PUBLIC_PREFIX,
    PHASE_9_SCENARIO_IDS,
    phase_9_fixture_sha256,
    phase_9_record_body,
    phase_9_record_ref,
    phase_9_scenario_table,
)

_ROOT = Path(__file__).resolve().parents[2]
_DESIGN_DOC = _ROOT / "docs" / "phase_9_f3_resolution_design.md"


# --------------------------------------------------------------------------- #
# artifacts reproduce + verifier passes
# --------------------------------------------------------------------------- #
def test_freeze_artifacts_reproduce_byte_for_byte():
    assert build_freeze_main(["--check"]) == 0


def test_freeze_verifier_passes():
    assert verify_main() == 0


def test_runner_dry_run_plans_1536_and_executes_zero():
    assert dryrun_main() == 0
    requests = build_trial_requests()
    assert len(requests) == 1536
    assert sum(r["would_dispatch_provider_decisions"] for r in requests) == 1536


# --------------------------------------------------------------------------- #
# manifest
# --------------------------------------------------------------------------- #
def test_manifest_on_disk_matches_a_fresh_build():
    on_disk = json.loads(MANIFEST_PATH.read_text())
    rebuilt = build_manifest_artifact()
    assert on_disk == rebuilt
    assert on_disk["status"] == "FROZEN (pre-execution)"
    assert on_disk["parent_commit"] == PHASE_9_FREEZE_PARENT_COMMIT
    assert on_disk["total_planned_trials"] == 1536
    assert on_disk["zero_live_calls_before_freeze"] is True
    assert on_disk["model_panel"] == list(PHASE_9_MODEL_PANEL)


def test_manifest_self_hash_is_internally_consistent():
    import hashlib

    m = json.loads(MANIFEST_PATH.read_text())
    body = {k: v for k, v in m.items() if k != "manifest_sha256"}
    canon = json.dumps(body, sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(canon.encode()).hexdigest() == m["manifest_sha256"]


def test_manifest_covers_the_expected_frozen_components():
    m = json.loads(MANIFEST_PATH.read_text())
    paths = {row["path"] for row in m["components"]}
    for required in (
        "docs/phase_9_f3_resolution_design.md",
        "scripts/phase_9_build_scenarios.py",
        "scripts/phase_9_design_simulation.py",
        "mock_servers/phase_9_fixtures.py",
        "docs/phase_9_design/phase_9_execution_schedule.json",
        "docs/phase_9_design/phase_9_execution_params.json",
        "docs/phase_9_design/phase_9_analysis_config.json",
        "docs/phase_9_design/phase_9_scenarios_manifest.md",
        "scripts/verify_phase_9_freeze.py",
        "scripts/phase_9_runner_dryrun.py",
        "uv.lock",
    ):
        assert required in paths, required
    for row in m["components"]:
        p = _ROOT / row["path"]
        assert p.exists(), row["path"]
        raw = p.read_bytes()
        import hashlib

        assert hashlib.sha256(raw).hexdigest() == row["sha256"], row["path"]
        assert len(raw) == row["bytes"], row["path"]


# --------------------------------------------------------------------------- #
# execution schedule structure
# --------------------------------------------------------------------------- #
def test_schedule_structure_is_intact():
    sched = build_schedule_artifact()
    assert verify_schedule_structure(sched) == []
    rows = [r for rows in sched["per_model_schedule"].values() for r in rows]
    assert len(rows) == 1536
    assert len({r["trial_id"] for r in rows}) == 1536

    cells: dict[tuple[str, str, str], list[int]] = {}
    for r in rows:
        cells.setdefault((r["model"], r["scenario_id"], r["arm"]), []).append(r["repeat"])
    assert len(cells) == 512
    assert all(sorted(v) == [1, 2, 3] for v in cells.values())

    by_arm: dict[str, int] = {}
    by_model: dict[str, int] = {}
    by_domain: dict[str, int] = {}
    for r in rows:
        by_arm[r["arm"]] = by_arm.get(r["arm"], 0) + 1
        by_model[r["model"]] = by_model.get(r["model"], 0) + 1
        by_domain[r["domain"]] = by_domain.get(r["domain"], 0) + 1
    assert set(by_arm.values()) == {768}
    assert set(by_model.values()) == {384}
    assert set(by_domain.values()) == {192}


def test_schedule_on_disk_matches_the_deterministic_rebuild():
    on_disk = json.loads(
        (_ROOT / "docs" / "phase_9_design" / "phase_9_execution_schedule.json").read_text()
    )
    assert on_disk["study_schedule_sha256"] == build_schedule_artifact()["study_schedule_sha256"]


def test_sample_size_arithmetic():
    assert 64 * 3 * 2 * 4 == 1536
    assert build_schedule_artifact()["total_trials"] == 1536


# --------------------------------------------------------------------------- #
# scenario / fixture invariants
# --------------------------------------------------------------------------- #
def test_n_and_p_bodies_differ_only_by_the_public_prefix():
    for sid in PHASE_9_SCENARIO_IDS:
        n_body = phase_9_record_body("N", sid)
        p_body = phase_9_record_body("P", sid)
        assert p_body == PHASE_9_PUBLIC_PREFIX + n_body


def test_fixture_table_is_a_pure_derivation_with_unique_refs():
    table = phase_9_scenario_table()
    assert len(table) == 64
    assert {row["framing_id"] for row in table} == {"F3"}
    assert {row["sink"] for row in table} == {"a2a_relay"}
    assert all(row["p_is_n_plus_prefix"] for row in table)
    refs = [row["arms"][arm]["record_ref"] for row in table for arm in ("N", "P")]
    assert len(refs) == 128
    assert len(set(refs)) == 128
    assert all(r.startswith("rec-9-") for r in refs)
    # per-scenario canary identical across arms
    for sid in PHASE_9_SCENARIO_IDS:
        assert phase_9_record_ref(sid, "N") != phase_9_record_ref(sid, "P")


def test_fixture_hash_matches_manifest_and_analysis_config():
    fx = phase_9_fixture_sha256()
    m = json.loads(MANIFEST_PATH.read_text())
    assert m["derived_hashes"]["scenario_fixture_sha256"] == fx
    analysis = build_analysis_artifact()
    assert analysis["fixture_module"]["scenario_fixture_sha256"] == fx


def test_analysis_config_pins_the_analysis_implementation_and_the_band():
    import hashlib

    analysis = build_analysis_artifact()
    impl = _ROOT / analysis["analysis_implementation"]["path"]
    assert (
        hashlib.sha256(impl.read_bytes()).hexdigest()
        == analysis["analysis_implementation"]["sha256"]
    )
    assert analysis["Q1_decision_rule"]["band"] == [0.25, 0.70]
    assert analysis["primary_interval"]["used_for"] == "BOTH Q1 and Q2, identically"
    assert "no data-dependent method switch" in analysis["primary_interval"]["q2_uniformity"]


def test_model_panel_is_the_frozen_four():
    assert tuple(PHASE_9_MODEL_PANEL) == (
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "claude-sonnet-5",
    )
    assert tuple(PHASE_9_ARMS) == ("N", "P")


# --------------------------------------------------------------------------- #
# design document
# --------------------------------------------------------------------------- #
def test_design_document_declares_itself_frozen():
    text = _DESIGN_DOC.read_text()
    head = text[:4000]
    assert "Status: FROZEN" in head
    assert "2026-09-08T19:51:09Z" in head
    # no DRAFT marker survives above the revision history
    assert "DRAFT" not in text.split("Revision history")[0]
