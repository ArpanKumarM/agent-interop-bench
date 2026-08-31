"""Write ``benchmarks/composed/live_canary_phase7a_fingerprints.json``.

IMPORTANT -- these are a **DESIGN-FREEZE REFERENCE**, not the execution
fingerprints. The final execution fingerprints must be generated only
AFTER the Phase 7B execution-wiring source is itself frozen and pushed,
against that exact final source SHA (see
``docs/phase_7a_neutral_baseline_design.md`` section 10). The output file
carries an ``artifact_role`` field stating this.

The fingerprint stamps whatever commit is resolved (env
``A2AVALIDATOR_SOURCE_COMMIT`` wins, else ``git rev-parse HEAD``); pass the
current design-freeze commit explicitly for a stable reference:

    A2AVALIDATOR_SOURCE_COMMIT=<sha> uv run python -m app.cli.freeze_phase_7a_fingerprints

Deterministic given (source commit, uv.lock, interpreter version). Makes NO
provider call and executes NO trial.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.cli.phase_7a_preflight import run_preflight

OUT = (
    Path(__file__).resolve().parent.parent.parent
    / "benchmarks"
    / "composed"
    / "live_canary_phase7a_fingerprints.json"
)


def build_doc() -> dict:
    report = run_preflight()
    fps = report["execution_fingerprints"]
    any_fp = next(iter(fps.values()))
    return {
        "artifact_role": (
            "DESIGN-FREEZE REFERENCE ONLY -- NOT the execution fingerprints. "
            "Regenerate against the frozen Phase 7B execution-wiring source SHA "
            "before requesting execution authorization (see "
            "docs/phase_7a_neutral_baseline_design.md section 10)."
        ),
        "final_execution_fingerprint": False,
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
    doc = build_doc()
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "wrote": str(OUT),
                "source_commit_sha": doc["source_commit_sha"],
                "execution_fingerprint_sha256": doc["execution_fingerprint_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
