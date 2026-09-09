"""Phase 9 -- frozen analysis guard (attempt 002).

Confirms the frozen analysis driver reproduces deterministically from the
frozen raw bytes, uses the hash-pinned analysis implementation, and that
its recorded confirmatory verdict is internally consistent. Skips cleanly
if the git-ignored raw run dirs are absent.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_RUN_DIRS_PRESENT = all(
    (_ROOT / "reports" / "experiments" / f"phase-9-f3-{s}" / "trials.jsonl").exists()
    for s in ("sol", "terra", "luna", "claude")
)
pytestmark = pytest.mark.skipif(
    not _RUN_DIRS_PRESENT, reason="git-ignored Phase 9 attempt-002 raw run dirs not present"
)

_RESULTS = _ROOT / "docs" / "phase_9_design" / "phase_9_results_attempt_002.json"


def test_analysis_uses_the_hash_pinned_implementation():
    live = hashlib.sha256(
        (_ROOT / "scripts" / "phase_9_design_simulation.py").read_bytes()
    ).hexdigest()
    pinned = json.loads(
        (_ROOT / "docs" / "phase_9_design" / "phase_9_analysis_config.json").read_text()
    )["analysis_implementation"]["sha256"]
    assert live == pinned
    assert json.loads(_RESULTS.read_text())["analysis_implementation_sha256"] == pinned


def test_analysis_is_deterministic():
    from scripts.phase_9_analyze import OUT_JSON
    from scripts.phase_9_analyze import main as analyze_main

    analyze_main()
    h1 = hashlib.sha256(OUT_JSON.read_bytes()).hexdigest()
    analyze_main()
    h2 = hashlib.sha256(OUT_JSON.read_bytes()).hexdigest()
    assert h1 == h2


def test_confirmatory_verdict_is_internally_consistent():
    r = json.loads(_RESULTS.read_text())["CONFIRMATORY_primary"]
    classes = [v["Q1"]["classification"] for v in r["per_model"].values()]
    # frozen framing rule
    if sum(c == "IN_BAND" for c in classes) >= 3:
        expect = "MEETS"
    elif sum(c in ("BELOW", "ABOVE") for c in classes) >= 2:
        expect = "FAILS"
    else:
        expect = "UNRESOLVED"
    assert r["panel_Q1_verdict"] == expect
    # Q2 detected iff CI excludes 0
    for v in r["per_model"].values():
        lo, hi = v["Q2"]["ci95"]
        assert v["Q2"]["detected_label_effect"] == (not (lo <= 0.0 <= hi))
    # attrition-exclusion variant is identical here (0 protocol errors)
    excl = json.loads(_RESULTS.read_text())["SENSITIVITY_attrition_exclusion"]
    assert excl["panel_Q1_verdict"] == r["panel_Q1_verdict"]
