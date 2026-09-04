"""Phase 8 -- run the frozen analysis (docs/phase_8_design.md S7) against
the frozen raw copies and write ``reports/phase_8_analysis/``.

**Not runnable against real data yet.** Phase 8 has not been executed --
there is no Phase 8C pilot result, no Phase 8D raw freeze. This CLI exists
now (Phase 8B) so the analysis engine (``app.reporting.phase_8``) is
built, tested against a synthetic fixture, and ready the moment real raw
data lands; ``main()`` refuses clearly rather than silently doing nothing
if ``RAW_ROOT`` does not exist.

No provider call. No trial re-run. Raw ``trials.jsonl`` bytes are hashed
before and after and asserted identical, mirroring Phase 7E's discipline.

Run:  uv run python -m app.cli.phase_8 [--raw-root PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.reporting.phase_8 import (
    PANEL,
    Phase8AnalysisError,
    analyze_s8a,
    analyze_s8b_calibration,
    analyze_s8c_wording,
    analyze_s8d_policy,
    validate_structure,
)
from mock_servers.phase_8_fixtures import PHASE_8_POLICY_ROBUSTNESS_SCENARIOS, PHASE_8_SCENARIOS

OUT = Path("reports/phase_8_analysis")
# Where the Phase 8D pre-analysis freeze will land, once it exists.
RAW_ROOT = Path("reports/_phase8d_preanalysis_freeze/raw_runs")

# {substudy -> {model -> run-directory basename}}, mirroring Phase 7's
# RUN_DIRNAME convention. Placeholder names; re-pinned at 8D.
RUN_DIRNAME: dict[str, dict[str, str]] = {
    substudy: {model: f"phase-8-{substudy}-{model}" for model in PANEL}
    for substudy in ("v8a", "v8a2", "v8b", "v8c", "v8d")
}

_EXPECTED_TOTAL: dict[str, int] = {
    "v8a": 3456,
    "v8a2": 384,
    "v8b": 1152,
    "v8c": 1152,
    "v8d": 384,
}


class Phase8CliError(RuntimeError):
    """A refused precondition -- e.g. Phase 8 raw data does not exist yet."""


def load_trials(raw_root: Path, substudy: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for model, run in RUN_DIRNAME[substudy].items():
        path = raw_root / run / "trials.jsonl"
        if not path.exists():
            raise Phase8CliError(
                f"{path} does not exist -- Phase 8 has not been executed yet "
                "(no Phase 8C pilot, no Phase 8D raw freeze). This CLI is "
                "pre-built for when it has been; see docs/phase_8_design.md S9."
            )
        out[model] = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return out


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_full_analysis(raw_root: Path = RAW_ROOT) -> dict:
    report: dict[str, dict] = {}

    trials_a = load_trials(raw_root, "v8a")
    validate_structure(trials_a, _EXPECTED_TOTAL["v8a"])
    report["s8a"] = analyze_s8a(trials_a, PHASE_8_SCENARIOS)

    trials_a2 = load_trials(raw_root, "v8a2")
    validate_structure(trials_a2, _EXPECTED_TOTAL["v8a2"])

    trials_b = load_trials(raw_root, "v8b")
    validate_structure(trials_b, _EXPECTED_TOTAL["v8b"])
    report["s8b_calibration"] = analyze_s8b_calibration(trials_b, PHASE_8_SCENARIOS)

    trials_c = load_trials(raw_root, "v8c")
    validate_structure(trials_c, _EXPECTED_TOTAL["v8c"])
    report["s8c_wording"] = analyze_s8c_wording(trials_c, PHASE_8_SCENARIOS)

    trials_d = load_trials(raw_root, "v8d")
    validate_structure(trials_d, _EXPECTED_TOTAL["v8d"])
    report["s8d_policy"] = analyze_s8d_policy(trials_d, PHASE_8_POLICY_ROBUSTNESS_SCENARIOS)

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase_8")
    parser.add_argument("--raw-root", type=Path, default=RAW_ROOT)
    args = parser.parse_args(argv)

    if not args.raw_root.exists():
        raise Phase8CliError(
            f"{args.raw_root} does not exist -- Phase 8 has not been executed yet. "
            "Run the Phase 8C pilot and the Phase 8D raw freeze first."
        )

    trial_files = sorted(args.raw_root.rglob("trials.jsonl"))
    before = {p: _sha256_of(p) for p in trial_files}

    try:
        report = run_full_analysis(args.raw_root)
    except Phase8AnalysisError as exc:
        raise Phase8CliError(str(exc)) from exc

    after = {p: _sha256_of(p) for p in trial_files}
    if before != after:
        raise Phase8CliError("raw trials.jsonl bytes changed during analysis -- aborting")

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "report.json"
    out_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    manifest = {str(p.relative_to(args.raw_root)): sha for p, sha in after.items()}
    manifest["report.json"] = _sha256_of(out_path)
    (OUT / "MANIFEST.sha256").write_text(
        "\n".join(f"{sha}  {name}" for name, sha in sorted(manifest.items())) + "\n"
    )
    print(json.dumps({"wrote": str(out_path), "raw_files_verified_unchanged": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
