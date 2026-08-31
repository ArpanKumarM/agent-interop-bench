"""Write ``benchmarks/composed/live_canary_phase7a_fingerprints.json``.

Two modes:

* default -> a **DESIGN-FREEZE REFERENCE** (``final_execution_fingerprint =
  false``).
* ``--final`` -> the **FINAL execution fingerprints**
  (``final_execution_fingerprint = true``). Requires
  ``A2AVALIDATOR_SOURCE_COMMIT=<EXECUTION_SOURCE_SHA>`` to be set
  explicitly; run only AFTER the Phase 7B executable source is committed
  and pushed (``docs/phase_7a_neutral_baseline_design.md`` section 10).

    # design-freeze reference
    A2AVALIDATOR_SOURCE_COMMIT=<sha> uv run python -m app.cli.freeze_phase_7a_fingerprints
    # FINAL
    A2AVALIDATOR_SOURCE_COMMIT=<EXECUTION_SOURCE_SHA> \
        uv run python -m app.cli.freeze_phase_7a_fingerprints --final

Deterministic given (source commit, uv.lock, interpreter version). Makes NO
provider call and executes NO trial.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from app.cli.phase_7a_preflight import run_preflight

OUT = (
    Path(__file__).resolve().parent.parent.parent
    / "benchmarks"
    / "composed"
    / "live_canary_phase7a_fingerprints.json"
)


def build_doc(*, final: bool = False) -> dict:
    if final and not (os.environ.get("A2AVALIDATOR_SOURCE_COMMIT") or "").strip():
        raise SystemExit(
            "--final requires A2AVALIDATOR_SOURCE_COMMIT=<EXECUTION_SOURCE_SHA> to be set "
            "explicitly (see docs/phase_7a_neutral_baseline_design.md section 10)."
        )
    report = run_preflight()
    fps = report["execution_fingerprints"]
    any_fp = next(iter(fps.values()))
    role = (
        (
            "FINAL execution fingerprints -- generated against EXECUTION_SOURCE_SHA "
            f"{any_fp['source_commit_sha']}. The runner records this SHA into "
            "execution_fingerprint.json and every trial's provenance when the study "
            "is run with A2AVALIDATOR_SOURCE_COMMIT set to it. The Phase 7A/7A.1 "
            "fingerprints in git history remain design-freeze references only."
        )
        if final
        else (
            "DESIGN-FREEZE REFERENCE ONLY -- NOT the execution fingerprints. "
            "Regenerate with --final against the frozen EXECUTION_SOURCE_SHA "
            "before requesting execution authorization (see "
            "docs/phase_7a_neutral_baseline_design.md section 10)."
        )
    )
    return {
        "artifact_role": role,
        "final_execution_fingerprint": bool(final),
        "study_id": report["experiment_id"],
        "study_version": report["experiment_version"],
        "fingerprint_version": "v2",
        "source_commit_sha": any_fp["source_commit_sha"],
        "canonical_actions": report["canonical_actions"],
        "config_hash": report["config_hash"],
        "study_schedule_sha256": report["study_schedule_sha256"],
        "per_model_schedule_sha256": report["per_model_schedule_sha256"],
        "provider_config_sha256": report["provider_config_sha256"],
        "shared_components": {
            "resolved_overlay_bundle_sha256": any_fp["resolved_overlay_bundle_sha256"],
            "host_policy_sha256": any_fp["host_policy_sha256"],
            "tool_schema_sha256": any_fp["tool_schema_sha256"],
            "canonical_action_schema_sha256": any_fp["canonical_action_schema_sha256"],
            "uv_lock_sha256": any_fp["uv_lock_sha256"],
            "python_runtime_version": any_fp["python_runtime_version"],
        },
        "execution_fingerprint_sha256": {
            m: fp["execution_fingerprint_sha256"] for m, fp in fps.items()
        },
        "per_model": fps,
        "phase7_executed": False,
        "provider_calls_made": 0,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    final = "--final" in args
    doc = build_doc(final=final)
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "wrote": str(OUT),
                "final_execution_fingerprint": doc["final_execution_fingerprint"],
                "source_commit_sha": doc["source_commit_sha"],
                "execution_fingerprint_sha256": doc["execution_fingerprint_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
