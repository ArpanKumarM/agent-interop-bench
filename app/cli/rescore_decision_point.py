"""CLI: offline forensic rescore of a frozen decision-point live run
(Phase 4A.3g).

    uv run python -m app.cli.rescore_decision_point \
      --run-dir reports/experiments/composed-live-canary-002-gpt56terra-attempt-1

Writes ``summary_rescored_v2.json`` next to the frozen artifacts. NEVER
writes to ``summary.json`` and NEVER makes a provider call.
"""

from __future__ import annotations

import argparse
import json
import sys

from app.reporting.decision_point_rescore import RescoreEvidenceError, write_rescored_summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rescore_decision_point")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument(
        "--analysis-commit-sha",
        default=None,
        help="override the recorded analysis commit SHA (default: git rev-parse HEAD).",
    )
    args = parser.parse_args(argv)
    try:
        target = write_rescored_summary(args.run_dir, analysis_commit_sha=args.analysis_commit_sha)
    except RescoreEvidenceError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"wrote": str(target)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
