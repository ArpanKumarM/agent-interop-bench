"""Phase 9 -- execution-ATTEMPT freeze guard (attempt 002 after the
attempt-001 billing abort).

The scientific freeze (32a76bf) and execution-implementation freeze
(a347a8b) are unchanged; this only guards the attempt-level re-freeze
manifest.
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.phase_9_attempt_freeze import (
    ATTEMPT_ID,
    EXECUTION_IMPLEMENTATION_FREEZE_COMMIT,
    MANIFEST_PATH,
    SCIENTIFIC_FREEZE_COMMIT,
    build_manifest,
    verify_attempt_manifest,
)
from scripts.phase_9_attempt_freeze import main as attempt_freeze_main

_ROOT = Path(__file__).resolve().parents[2]


def test_attempt_002_manifest_reproduces_and_verifies():
    assert attempt_freeze_main(["--check"]) == 0
    assert verify_attempt_manifest() == []


def test_attempt_002_manifest_on_disk_matches_a_fresh_build():
    on_disk = json.loads(MANIFEST_PATH.read_text())
    assert on_disk == build_manifest()


def test_attempt_002_changes_no_frozen_parameter():
    m = json.loads(MANIFEST_PATH.read_text())
    assert m["attempt_id"] == ATTEMPT_ID == "002"
    assert m["scientific_freeze_commit"] == SCIENTIFIC_FREEZE_COMMIT
    assert m["execution_implementation_freeze_commit"] == EXECUTION_IMPLEMENTATION_FREEZE_COMMIT
    assert m["scientific_freeze_unchanged"] is True
    assert m["execution_implementation_unchanged"] is True
    assert m["no_scientific_parameter_changed"] is True
    assert m["no_execution_parameter_changed"] is True
    assert m["reused_verbatim"]["total_planned_trials"] == 1536
    assert m["reused_verbatim"]["retry_behavior"].startswith("max_retries = 0")
    # same frozen schedule / scenarios / overlays as the scientific + addendum manifests
    sci = json.loads((_ROOT / "docs" / "phase_9_freeze_manifest.json").read_text())
    assert (
        m["reused_verbatim"]["study_schedule_sha256"]
        == sci["derived_hashes"]["study_schedule_sha256"]
    )
    assert (
        m["reused_verbatim"]["scenario_fixture_sha256"]
        == sci["derived_hashes"]["scenario_fixture_sha256"]
    )


def test_attempt_001_contributed_zero_observations():
    m = json.loads(MANIFEST_PATH.read_text())
    a1 = m["aborted_attempt_001"]
    assert a1["scientific_observations_contributed"] == 0
    assert a1["successful_model_responses"] == 0
    assert a1["generated_tokens"] == 0
    assert a1["billed_cost_usd"] == 0.0
    assert a1["provider_attempts"] == 9
    assert "insufficient_quota" in a1["all_attempts_status"]
    assert m["not_outcome_based_rerun"].startswith("no model output was ever observed")


def test_attempt_002_requires_pristine_output_dirs():
    m = json.loads(MANIFEST_PATH.read_text())
    state = m["attempt_002_preconditions"]["real_output_dir_state"]
    assert set(state) == {"gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "claude-sonnet-5"}
    assert all("NOT PRISTINE" not in v for v in state.values())
