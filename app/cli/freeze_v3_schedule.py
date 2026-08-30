"""Write the frozen Phase 4B blocked study schedule to
``benchmarks/composed/live_canary_v3_schedule.json``.

Deterministic: the output is fully determined by the frozen constants in
``app.runner.blocked_schedule`` (seed, panel, cells, blocks). Re-running
this must reproduce the committed file byte-for-byte -- a regression test
enforces that. Makes no provider call.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.runner.blocked_schedule import build_schedule_artifact

SCHEDULE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "benchmarks"
    / "composed"
    / "live_canary_v3_schedule.json"
)


def main(argv: list[str] | None = None) -> int:
    artifact = build_schedule_artifact()
    SCHEDULE_PATH.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "wrote": str(SCHEDULE_PATH),
                "study_schedule_sha256": artifact["study_schedule_sha256"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
