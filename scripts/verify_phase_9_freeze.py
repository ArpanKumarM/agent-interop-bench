"""Phase 9 (F3 resolution study) -- FREEZE VERIFIER.

Fails (non-zero exit) if any frozen Phase 9 component has drifted from the
state recorded in ``docs/phase_9_freeze_manifest.json``. Run it before any
live execution and in CI.

Checks:

* every component hash / byte-size in the freeze manifest still matches
  the file on disk;
* the manifest's self-hash is internally consistent;
* the execution schedule has exactly 1,536 rows, 512 (model, scenario,
  arm) cells each with repeats {1, 2, 3}, no duplicate trial ids, N/P and
  model and domain counts balanced;
* the 64-scenario panel still passes every builder invariant;
* N and P record bodies differ only by the frozen public-label prefix;
* the fixture's canonical hash matches the manifest and the analysis config;
* the analysis-implementation hash matches the manifest;
* the required four-model panel is intact;
* the sample-size arithmetic 64 * 3 * 2 * 4 == 1,536 holds;
* the design document's status line reads FROZEN.

Makes NO provider call. Executes NO trial. Read-only.

Run:  uv run python scripts/verify_phase_9_freeze.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from scripts.phase_9_build_freeze import (  # noqa: E402
    MANIFEST_PATH,
    build_manifest_artifact,
    build_schedule_artifact,
    verify_schedule_structure,
)
from scripts.phase_9_build_scenarios import build_scenarios, run_checks  # noqa: E402

from mock_servers.phase_9_fixtures import (  # noqa: E402
    PHASE_9_ARMS,
    PHASE_9_MODEL_PANEL,
    PHASE_9_PUBLIC_PREFIX,
    PHASE_9_SCENARIO_IDS,
    phase_9_fixture_sha256,
    phase_9_record_body,
)

_DESIGN_DOC = _ROOT / "docs" / "phase_9_f3_resolution_design.md"
_SCHEDULE_PATH = _ROOT / "docs" / "phase_9_design" / "phase_9_execution_schedule.json"
_ANALYSIS_PATH = _ROOT / "docs" / "phase_9_design" / "phase_9_analysis_config.json"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canon(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def _check(fails: list[str], cond: bool, msg: str) -> None:
    if not cond:
        fails.append(msg)


def main() -> int:
    fails: list[str] = []

    # ---- 1. manifest present + self-consistent ---------------------------- #
    if not MANIFEST_PATH.exists():
        print(f"FAIL: missing {MANIFEST_PATH.relative_to(_ROOT)}", file=sys.stderr)
        return 1
    manifest = json.loads(MANIFEST_PATH.read_text())

    recorded_self = manifest.get("manifest_sha256", "")
    body = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    _check(
        fails,
        _sha256(_canon(body).encode()) == recorded_self,
        "manifest self-hash (manifest_sha256) is inconsistent with its body",
    )
    _check(
        fails,
        manifest.get("status") == "FROZEN (pre-execution)",
        "manifest status is not FROZEN (pre-execution)",
    )
    _check(
        fails,
        manifest.get("total_planned_trials") == 1536,
        "manifest total_planned_trials != 1536",
    )
    _check(
        fails,
        manifest.get("zero_live_calls_before_freeze") is True,
        "manifest zero_live_calls_before_freeze flag not set",
    )

    # ---- 2. rebuild the manifest and compare ---------------------------- #
    rebuilt = build_manifest_artifact()
    _check(
        fails,
        rebuilt["manifest_sha256"] == recorded_self,
        "rebuilt manifest self-hash differs from the recorded one -- a frozen component changed",
    )

    # ---- 3. every recorded component hash still matches disk ------------ #
    for row in manifest["components"]:
        p = _ROOT / row["path"]
        if not p.exists():
            fails.append(f"component missing on disk: {row['path']}")
            continue
        raw = p.read_bytes()
        if _sha256(raw) != row["sha256"]:
            fails.append(f"component sha256 drift: {row['path']}")
        if len(raw) != row["bytes"]:
            fails.append(f"component byte-size drift: {row['path']}")

    # ---- 4. schedule structure ---------------------------------------- #
    if not _SCHEDULE_PATH.exists():
        fails.append("execution schedule artifact is missing")
    else:
        on_disk_sched = json.loads(_SCHEDULE_PATH.read_text())
        rebuilt_sched = build_schedule_artifact()
        _check(
            fails,
            on_disk_sched["study_schedule_sha256"] == rebuilt_sched["study_schedule_sha256"],
            "on-disk schedule hash != deterministically rebuilt schedule hash",
        )
        for f in verify_schedule_structure(on_disk_sched):
            fails.append(f"schedule: {f}")
        _check(
            fails,
            on_disk_sched["study_schedule_sha256"]
            == manifest["derived_hashes"]["study_schedule_sha256"],
            "schedule hash in manifest.derived_hashes != on-disk schedule hash",
        )

    # ---- 5. scenario panel invariants -------------------------------- #
    scen = build_scenarios()
    for f in run_checks(scen):
        fails.append(f"scenario panel: {f}")
    _check(fails, len(scen) == 64, f"scenario panel has {len(scen)} rows, expected 64")

    # ---- 6. N/P byte-difference invariant --------------------------- #
    for sid in PHASE_9_SCENARIO_IDS:
        n_body = phase_9_record_body("N", sid)
        p_body = phase_9_record_body("P", sid)
        if p_body != PHASE_9_PUBLIC_PREFIX + n_body:
            fails.append(f"N/P invariant broken for {sid}")

    # ---- 7. fixture / analysis-config agreement --------------------- #
    fx = phase_9_fixture_sha256()
    _check(
        fails,
        fx == manifest["derived_hashes"]["scenario_fixture_sha256"],
        "fixture canonical hash != manifest.derived_hashes.scenario_fixture_sha256",
    )
    if _ANALYSIS_PATH.exists():
        analysis = json.loads(_ANALYSIS_PATH.read_text())
        _check(
            fails,
            analysis["fixture_module"]["scenario_fixture_sha256"] == fx,
            "analysis config fixture hash != live fixture hash",
        )
        impl_p = _ROOT / analysis["analysis_implementation"]["path"]
        _check(
            fails,
            _sha256(impl_p.read_bytes()) == analysis["analysis_implementation"]["sha256"],
            "analysis-implementation file hash != analysis config recorded hash",
        )
        _check(
            fails,
            analysis["analysis_implementation"]["sha256"]
            == manifest["derived_hashes"]["analysis_implementation_sha256"],
            "analysis-implementation hash mismatch between analysis config and manifest",
        )
        _check(
            fails,
            analysis["Q1_decision_rule"]["band"] == [0.25, 0.70],
            "analysis config Q1 band is not [0.25, 0.70]",
        )
    else:
        fails.append("analysis config artifact is missing")

    # ---- 8. model panel + arithmetic ------------------------------- #
    _check(
        fails,
        tuple(manifest["model_panel"]) == tuple(PHASE_9_MODEL_PANEL)
        and len(PHASE_9_MODEL_PANEL) == 4,
        "four-model panel drift",
    )
    _check(fails, tuple(PHASE_9_ARMS) == ("N", "P"), "arms are not exactly (N, P)")
    _check(fails, 64 * 3 * 2 * 4 == 1536, "sample-size arithmetic 64*3*2*4 != 1536")

    # ---- 9. design doc status is FROZEN --------------------------- #
    head = _DESIGN_DOC.read_text()[:4000]
    _check(
        fails,
        "FROZEN" in head and "Status: FROZEN" in head,
        "design document status line does not read FROZEN",
    )
    _check(
        fails,
        "DRAFT" not in _DESIGN_DOC.read_text().split("Revision history")[0],
        "design document still contains a DRAFT marker above the revision history",
    )

    # ---- report ---------------------------------------------------- #
    if fails:
        print(f"PHASE 9 FREEZE VERIFICATION FAILED ({len(fails)} issue(s)):", file=sys.stderr)
        for f in fails:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("PHASE 9 FREEZE VERIFICATION PASSED")
    print(f"  manifest_sha256          {recorded_self}")
    print(f"  study_schedule_sha256    {manifest['derived_hashes']['study_schedule_sha256']}")
    print(f"  scenario_fixture_sha256  {manifest['derived_hashes']['scenario_fixture_sha256']}")
    print(f"  components verified       {len(manifest['components'])}")
    print("  total planned trials      1536   (64 scenarios x 3 repeats x 2 arms x 4 models)")
    print("  status                    FROZEN (pre-execution) -- NOT executed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
