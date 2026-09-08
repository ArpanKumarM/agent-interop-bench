"""Phase 9 (F3 resolution study) -- EXECUTION-READINESS verifier.

POST-FREEZE EXECUTION-IMPLEMENTATION ADDENDUM (scientific freeze
``32a76bf`` unchanged). Run this immediately before, and immediately
after, each per-model live run.

Makes ZERO network calls and constructs NO provider client. Non-zero exit
unless, for the requested model:

* the scientific freeze verifier passes (scripts/verify_phase_9_freeze.py);
* the execution-addendum manifest is self-consistent and every pinned
  live-path component still matches its hash;
* HEAD contains the scientific freeze commit lineage;
* the frozen 384-row schedule slice loads and passes every structural /
  bijection check;
* the model id is exactly one of the frozen four; its credential env var
  is present (value never printed);
* the plan / execution-fingerprint / schedule hashes resolve;
* the real per-model output directory is pristine (first run) OR a valid
  resumable state with NO indeterminate attempted trial;
* no model-substitution / fallback / provider-retry configuration is set.

Run:  uv run python scripts/verify_phase_9_execution_ready.py --model gpt-5.6-sol
      uv run python scripts/verify_phase_9_execution_ready.py            # all four
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from app.cli.phase_9_execute import (  # noqa: E402
    PHASE_9_MODEL_PANEL,
    PHASE_9_SCIENTIFIC_FREEZE_COMMIT,
    _run_dir_for_run,
    preflight_report,
)


def _check_model(model: str) -> tuple[bool, dict]:
    report = preflight_report(model, _run_dir_for_run(model), for_run=True)
    return (not report["blocking"]), report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify_phase_9_execution_ready")
    parser.add_argument("--model", choices=sorted(PHASE_9_MODEL_PANEL), default=None)
    args = parser.parse_args(argv)

    models = [args.model] if args.model else list(PHASE_9_MODEL_PANEL)
    all_ready = True
    for model in models:
        ready, report = _check_model(model)
        all_ready &= ready
        print(f"=== {model} ===")
        print(f"  ready                      {ready}")
        print(f"  scientific_freeze_commit   {report['scientific_freeze_commit']}")
        print(f"  run_directory              {report['run_directory']}")
        _slice = report.get("frozen_schedule_slice_trials", "n/a")
        print(f"  frozen_schedule_slice      {_slice} trials")
        print(f"  planned_provider_calls     {report.get('planned_provider_calls', 'n/a')}")
        print(f"  execution_fingerprint      {report.get('execution_fingerprint_sha256', 'n/a')}")
        print(f"  provider_config_sha256     {report.get('provider_config_sha256', 'n/a')}")
        print(f"  provider_calls_made        {report['provider_calls_made']}")
        for note in report["notes"]:
            print(f"  NOTE  {note}")
        for blocker in report["blocking"]:
            print(f"  BLOCK {blocker}")

    print()
    if all_ready:
        print("PHASE 9 EXECUTION-READINESS: READY (no network calls made)")
        print(f"  scientific freeze {PHASE_9_SCIENTIFIC_FREEZE_COMMIT} unchanged")
        return 0
    print("PHASE 9 EXECUTION-READINESS: NOT READY", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
