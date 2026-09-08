"""Recompute the Phase 8A.2 (round two) pilot grid DIRECTLY from the raw
trials.jsonl files still on disk, and assert it matches
app.reporting.phase_8_frozen_grid byte-for-byte on every number. This is
the strongest available check for round two: raw bytes -> live
recomputation -> frozen constants, not a hand-transcription cross-check.

Round one's raw files no longer exist on this machine (overwritten by
round two's run before this need was anticipated -- see the frozen-grid
module's docstring); it cannot be checked this way and is instead
audited by paper/arxiv/audit_phase8_numbers.py against
docs/phase_8c_pilot_result.md's own frozen table only.

Run:  uv run python scripts/verify_phase_8_round2_from_raw.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

# allow `uv run python scripts/verify_phase_8_round2_from_raw.py` from the
# repo root (script dir, not cwd, is sys.path[0] for a script file).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.reporting.phase_8_frozen_grid import (  # noqa: E402
    N_RATE,
    PANEL,
    PERMIT_RATE,
    PUBLIC_RATE,
    ROUND_TWO_FRAMINGS,
    ROUND_TWO_TRIALS_COMPLETED,
    ROUND_TWO_TRIALS_PLANNED,
    SUPPRESS_RATE,
)
from app.reporting.phase_8c_pilot import parse_pilot_overlay_id  # noqa: E402

RAW_ROOT = Path(__file__).resolve().parents[1] / "reports" / "experiments"

# Pinned in docs/phase_8a2_pilot_result.md -- verified present and
# unchanged before this script trusts the raw files at all.
EXPECTED_SHA256 = {
    "gpt-5.6-sol": "db9d3c5ca540c0e19730e9f4e80ed5f6cbd4cae57af933af8fd5d3aee5af6899",
    "gpt-5.6-terra": "55144203978551a8abd694c7885dee1abc7f01566f82d4218376b05dbd5184f4",
    "gpt-5.6-luna": "6a2512282b4dbcf5c412219034deca38acaf5bd50a0815bddc38568ff79940da",
    "claude-sonnet-5": "8f916fa3cf3315e2fd89a1fec0fe74bd2e3c7ee7d3936d590db9fd15dff42c73",
}


class VerificationError(RuntimeError):
    pass


def _check(cond: bool, msg: str) -> None:
    if not cond:
        raise VerificationError(msg)


def load_and_verify_hash(model: str) -> list[dict]:
    path = RAW_ROOT / f"phase-8-pilot-{model}" / "trials.jsonl"
    _check(path.exists(), f"{path} does not exist -- round-two raw data is gone")
    raw_bytes = path.read_bytes()
    actual = hashlib.sha256(raw_bytes).hexdigest()
    _check(
        actual == EXPECTED_SHA256[model],
        f"{model}: trials.jsonl hash mismatch -- got {actual}, expected "
        f"{EXPECTED_SHA256[model]}. Raw data has changed since it was frozen; "
        "do NOT trust it for recomputation.",
    )
    return [json.loads(line) for line in raw_bytes.decode("utf-8").splitlines() if line.strip()]


def pooled_rate(trials: list[dict], framing: str, arm: str) -> tuple[int, int]:
    k = r = 0
    for t in trials:
        try:
            f, _scenario, a = parse_pilot_overlay_id(t["overlay_id"])
        except Exception:  # noqa: BLE001 - any non-pilot id is simply not counted
            continue
        if f != framing or a != arm:
            continue
        r += 1
        if (
            t.get("status") == "completed"
            and t.get("outcomes", {}).get("any_sensitive_field_egress") is True
        ):
            k += 1
    return k, r


def main() -> int:
    total_trials = 0
    total_completed = 0
    mismatches: list[str] = []

    for model in PANEL:
        trials = load_and_verify_hash(model)
        total_trials += len(trials)
        total_completed += sum(1 for t in trials if t.get("status") == "completed")

        for framing in ROUND_TWO_FRAMINGS:
            n_k, n_r = pooled_rate(trials, framing, "unlabeled")
            permit_k, permit_r = pooled_rate(trials, framing, "permit")
            suppress_k, suppress_r = pooled_rate(trials, framing, "suppress")
            public_k, public_r = pooled_rate(trials, framing, "public")
            _check(
                n_r > 0 and permit_r > 0 and suppress_r > 0 and public_r > 0,
                f"{model}/{framing}: empty cell",
            )

            recomputed = {
                "N": round(n_k / n_r, 3),
                "permit": round(permit_k / permit_r, 3),
                "suppress": round(suppress_k / suppress_r, 3),
                "public": round(public_k / public_r, 3),
            }
            frozen = {
                "N": N_RATE[model][framing],
                "permit": PERMIT_RATE[model][framing],
                "suppress": SUPPRESS_RATE[model][framing],
                "public": PUBLIC_RATE[model][framing],
            }
            for arm, got in recomputed.items():
                if got != frozen[arm]:
                    mismatches.append(f"{model}/{framing} {arm}: raw={got} frozen={frozen[arm]}")

    _check(
        total_trials == ROUND_TWO_TRIALS_PLANNED,
        f"total trials {total_trials} != frozen {ROUND_TWO_TRIALS_PLANNED}",
    )
    _check(
        total_completed == ROUND_TWO_TRIALS_COMPLETED,
        f"completed trials {total_completed} != frozen {ROUND_TWO_TRIALS_COMPLETED}",
    )

    if mismatches:
        print("MISMATCHES FOUND -- frozen grid does not match raw data:", file=sys.stderr)
        for m in mismatches:
            print(f"  {m}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "verified",
                "total_trials": total_trials,
                "total_completed": total_completed,
                "cells_checked": len(PANEL) * len(ROUND_TWO_FRAMINGS) * 4,
                "mismatches": 0,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
