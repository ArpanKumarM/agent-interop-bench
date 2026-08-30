"""CLI: write the offline Phase 4B outcome-taxonomy audit artifact
(Phase 4B.1).

    uv run python -m app.cli.phase_4b_audit

Writes ``reports/experiments/phase_4b_outcome_audit.json``. Reads only the
frozen v3 run artifacts; makes no provider call; NEVER writes to any
``summary.json``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.reporting.phase_4b_audit import Phase4BAuditError, build_audit

AUDIT_PATH = Path("reports/experiments/phase_4b_outcome_audit.json")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    analysis_commit_sha = None
    if "--analysis-commit-sha" in argv:
        analysis_commit_sha = argv[argv.index("--analysis-commit-sha") + 1]
    try:
        payload = build_audit(analysis_commit_sha=analysis_commit_sha)
    except Phase4BAuditError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1
    if AUDIT_PATH.name == "summary.json":  # defensive; cannot happen
        print("refused: will not write summary.json", file=sys.stderr)
        return 1
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True))
    print(json.dumps({"wrote": str(AUDIT_PATH)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
