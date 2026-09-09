"""Phase 9 -- raw-data freeze guard (attempt 002, pre-analysis).

Guards ``docs/phase_9_raw_data_freeze_attempt_002_manifest.json``: it must
keep reproducing from the (git-ignored) run dirs and its recorded
execution-integrity verdict must stay PASS. Skips cleanly on a checkout
where the git-ignored raw run dirs are absent.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_RUN_DIRS_PRESENT = all(
    (_ROOT / "reports" / "experiments" / f"phase-9-f3-{s}" / "trials.jsonl").exists()
    for s in ("sol", "terra", "luna", "claude")
)

pytestmark = pytest.mark.skipif(
    not _RUN_DIRS_PRESENT,
    reason="git-ignored Phase 9 attempt-002 raw run dirs not present on this checkout",
)


def test_raw_data_freeze_manifest_reproduces_and_verifies():
    from scripts.phase_9_raw_data_freeze import main as rdf_main
    from scripts.phase_9_raw_data_freeze import verify

    assert rdf_main(["--check"]) == 0
    assert verify() == []


def test_raw_data_freeze_records_a_clean_1536_trial_execution():
    from scripts.phase_9_raw_data_freeze import MANIFEST_PATH

    m = json.loads(MANIFEST_PATH.read_text())
    ei = m["execution_integrity"]
    assert ei["verdict"] == "PASS"
    assert ei["problems"] == []
    assert ei["attempted"] == ei["completed"] == ei["total_provider_calls"] == 1536
    assert ei["protocol_error"] == 0 and ei["indeterminate"] == 0
    assert ei["per_arm_total"] == {"N": 768, "P": 768}
    assert set(ei["per_domain_total"].values()) == {192}
    for model, v in ei["per_model"].items():
        assert v["completed"] == 384
        assert v["returned_model"] == [model]  # no substitution
        assert v["no_retry"] is True
        assert v["recorded_order_equals_frozen_schedule"] is True
        assert v["all_trials_carry_execution_fingerprint"] is True
    assert m["analysis_not_yet_run"] is True


def test_raw_data_freeze_pins_freeze_commits():
    from scripts.phase_9_raw_data_freeze import (
        ATTEMPT_002_FREEZE_COMMIT,
        EXECUTION_IMPLEMENTATION_FREEZE_COMMIT,
        MANIFEST_PATH,
        SCIENTIFIC_FREEZE_COMMIT,
    )

    m = json.loads(MANIFEST_PATH.read_text())
    assert m["scientific_freeze_commit"] == SCIENTIFIC_FREEZE_COMMIT
    assert m["execution_implementation_freeze_commit"] == EXECUTION_IMPLEMENTATION_FREEZE_COMMIT
    assert m["attempt_002_freeze_commit"] == ATTEMPT_002_FREEZE_COMMIT
    assert "contributes NOTHING" in m["attempt_001_note"]
