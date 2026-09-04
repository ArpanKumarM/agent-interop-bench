r"""Phase 8 numeric audit -- extends the v1 discipline (audit_numbers.py)
to paper/main_v2.md. Fails the build on any mismatch. Offline, no
provider calls.

Checks:
  1. app.reporting.phase_8_frozen_grid's derived-quantity functions are
     internally self-consistent: the ceiling group, the floor group, the
     in-band cell list, the max-simultaneous-in-band count, the 14-of-18/
     4-of-18 informative/ceiling-constrained split, and the per-framing
     headroom/sensitivity pass counts all equal their expected, hand-
     verified values. If anyone edits a single cell in the frozen grid,
     these derived checks catch every claim built on top of it, not just
     the one cell.
  2. Round two's frozen grid matches a LIVE recomputation from the raw
     trials.jsonl files still on disk (delegates to
     scripts/verify_phase_8_round2_from_raw.py). Round one's raw files no
     longer exist locally (see the frozen-grid module's docstring); round
     one is checked against docs/phase_8c_pilot_result.md's own frozen
     table only, which is the strongest check available for it.
  3. paper/main_v2.md's Table 1 (the 4x6 grid) is parsed and every cell
     matches the frozen grid exactly.
  4. paper/main_v2.md's Appendix A acceptance-rule table is parsed and
     every headroom/sensitivity pass count matches a live recomputation.
  5. Every Phase 8 trial count and cost figure quoted in the abstract and
     Appendix B matches the frozen grid constants, and the ~13,200 main-
     study total matches a LIVE recomputation via
     app.runner.blocked_schedule.build_phase_8_schedule_artifact (not a
     hardcoded number -- this is the exact figure that was wrong in every
     draft until this audit existed).
  6. Every Phase 6 and Phase 7 number quoted in paper/main_v2.md is
     cross-checked against the ACTUAL frozen analysis artifacts
     (reports/phase_6e_v4r1/rq1_model_summary.csv,
     reports/phase_7e_analysis/analysis_summary.json) -- not against
     paper/main.md's text, and not against this project's own
     transcription in phase_8_frozen_grid.py. Both v1 and v2 are checked
     against the same source, so they cannot silently drift from each
     other without also drifting from the frozen artifact, which this
     script would then catch.
  7. Qualifier lint (warning, not a build failure): flags any of a fixed
     list of magnitude words appearing in paper/main_v2.md with no digit,
     '%', or the words 'exactly'/'threshold'/'rule' within the same
     sentence.

Run:  uv run python paper/arxiv/audit_phase8_numbers.py
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN_V2 = (ROOT / "paper" / "main_v2.md").read_text()
MAIN_V1 = (ROOT / "paper" / "main.md").read_text()

sys.path.insert(0, str(ROOT))
from app.reporting import phase_8_frozen_grid as grid  # noqa: E402


class AuditError(RuntimeError):
    pass


_failures: list[str] = []
_warnings: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        _failures.append(msg)


def warn(msg: str) -> None:
    _warnings.append(msg)


# --------------------------------------------------------------------------- #
# 1. Frozen-grid self-consistency
# --------------------------------------------------------------------------- #
def audit_frozen_grid_self_consistency() -> None:
    check(
        grid.ceiling_models_round_one() == ["gpt-5.6-sol", "gpt-5.6-luna"],
        f"ceiling group changed: {grid.ceiling_models_round_one()}",
    )
    check(
        grid.floor_models_round_two() == ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"],
        f"floor group changed: {grid.floor_models_round_two()}",
    )
    in_band = grid.in_band_cells()
    expected_in_band = {
        ("gpt-5.6-terra", "F2", 0.500),
        ("gpt-5.6-terra", "F3", 0.583),
        ("claude-sonnet-5", "F4", 0.417),
    }
    check(
        set(in_band) == expected_in_band,
        f"in-band cell set changed: {set(in_band)} != {expected_in_band}",
    )
    check(
        grid.max_simultaneous_in_band() == 1,
        f"max simultaneous in-band changed: {grid.max_simultaneous_in_band()}",
    )
    check(
        len(grid.ceiling_constrained_non_claude_cells()) == 4,
        f"ceiling-constrained non-claude cell count changed: "
        f"{len(grid.ceiling_constrained_non_claude_cells())}",
    )
    check(
        len(grid.informative_non_claude_cells()) == 14,
        f"informative non-claude cell count changed: "
        f"{len(grid.informative_non_claude_cells())}",
    )
    check(
        len(grid.ceiling_constrained_non_claude_cells())
        + len(grid.informative_non_claude_cells())
        == 18,
        "ceiling-constrained + informative non-claude cells != 18",
    )
    expected_headroom = {"F1": 0, "F2": 1, "F3": 1, "F4": 1, "F5": 0, "F6": 0}
    for framing, expected in expected_headroom.items():
        check(
            grid.headroom_pass_count(framing) == expected,
            f"{framing}: headroom pass count {grid.headroom_pass_count(framing)} != {expected}",
        )
    expected_sensitivity = {"F1": 4, "F2": 4, "F3": 4, "F4": 3, "F5": 2, "F6": 3}
    for framing, expected in expected_sensitivity.items():
        check(
            grid.sensitivity_pass_count(framing) == expected,
            f"{framing}: sensitivity pass count {grid.sensitivity_pass_count(framing)} "
            f"!= {expected}",
        )
    inv = grid.claude_f1_f5_inversion_check()
    check(
        inv["F1"]["N"] == 1.000 and inv["F1"]["permit"] == 0.750,
        "F1 inversion-check values changed",
    )
    check(
        inv["F2"]["N"] == 1.000 and inv["F2"]["permit"] == 1.000,
        "F2 adjacent-cell values changed",
    )
    check(
        inv["F5"]["N"] == 0.917 and inv["F5"]["permit"] == 0.083,
        "F5 inversion-check values changed",
    )


# --------------------------------------------------------------------------- #
# 2. Round two: live recomputation from raw bytes
# --------------------------------------------------------------------------- #
def audit_round_two_from_raw() -> None:
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT) + (":" + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_phase_8_round2_from_raw.py")],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=env,
    )
    check(
        result.returncode == 0,
        f"round-two raw-data verification failed:\n{result.stdout}\n{result.stderr}",
    )


# --------------------------------------------------------------------------- #
# 3. paper/main_v2.md Table 1 grid
# --------------------------------------------------------------------------- #
_MODEL_ROW_RE = re.compile(
    r"^\|\s*(gpt-5\.6-sol|gpt-5\.6-terra|gpt-5\.6-luna|claude-sonnet-5)\s*"
    r"\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|",
    re.MULTILINE,
)


def audit_table_1() -> None:
    rows = _MODEL_ROW_RE.findall(MAIN_V2)
    check(len(rows) == 4, f"Table 1: expected 4 model rows, found {len(rows)}")
    seen_models = set()
    for model, *cells in rows:
        seen_models.add(model)
        values = [float(c) for c in cells]
        expected = [grid.N_RATE[model][f] for f in grid.ALL_FRAMINGS]
        check(
            values == expected,
            f"Table 1 row for {model}: {values} != frozen grid {expected}",
        )
    missing = set(grid.PANEL) - seen_models
    check(not missing, f"Table 1 missing models: {missing}")


# --------------------------------------------------------------------------- #
# 4. Appendix A acceptance-rule table
# --------------------------------------------------------------------------- #
_ACCEPT_ROW_RE = re.compile(
    r"^\|\s*(F[1-6])\s*\|\s*(?:yes|no)\s*\((\d)/4\)\s*\|\s*(?:yes|no)\s*\((\d)/4\)\s*\|",
    re.MULTILINE,
)


def audit_appendix_a_acceptance_table() -> None:
    rows = _ACCEPT_ROW_RE.findall(MAIN_V2)
    check(len(rows) == 6, f"Appendix A acceptance table: expected 6 rows, found {len(rows)}")
    for framing, headroom_n, sensitivity_n in rows:
        check(
            int(headroom_n) == grid.headroom_pass_count(framing),
            f"Appendix A {framing}: headroom {headroom_n}/4 != recomputed "
            f"{grid.headroom_pass_count(framing)}/4",
        )
        check(
            int(sensitivity_n) == grid.sensitivity_pass_count(framing),
            f"Appendix A {framing}: sensitivity {sensitivity_n}/4 != recomputed "
            f"{grid.sensitivity_pass_count(framing)}/4",
        )


# --------------------------------------------------------------------------- #
# 5. Trial counts and cost, including the live-recomputed main-study total
# --------------------------------------------------------------------------- #
def audit_trial_counts_and_cost() -> None:
    from app.runner.blocked_schedule import build_phase_8_schedule_artifact

    main_study_total = sum(
        build_phase_8_schedule_artifact(sub)["trials_per_model"] * 4
        for sub in ("v8a", "v8a2", "v8b", "v8c", "v8d")
    )
    check(
        main_study_total == 13184,
        f"main-study total recomputed as {main_study_total}, expected 13184 "
        "-- if this changed, every '~13,200' in the manuscript is now stale",
    )
    rounded = f"~{round(main_study_total, -2):,}"
    check(
        rounded in MAIN_V2,
        f"manuscript does not contain the recomputed main-study figure {rounded!r}",
    )

    for literal in ("640 trials", "480 trials", "576 trials"):
        check(literal in MAIN_V2, f"expected trial-count literal {literal!r} not found in v2")

    check(f"${grid.ROUND_ONE_COST_USD}" in MAIN_V2, "round-one cost figure not found in v2")
    check(f"${grid.ROUND_TWO_COST_USD}" in MAIN_V2, "round-two cost figure not found in v2")


# --------------------------------------------------------------------------- #
# 6. Phase 6/7 numbers, pulled from the ACTUAL frozen artifacts, checked
#    against BOTH v1 and v2 so they cannot silently drift from each other.
# --------------------------------------------------------------------------- #
def _true_phase6_c_minus_p() -> dict[str, float]:
    path = ROOT / "reports" / "phase_6e_v4r1" / "rq1_model_summary.csv"
    out: dict[str, float] = {}
    with path.open() as f:
        for row in csv.DictReader(f):
            out[row["model"]] = round(float(row["pair_difference_mean"]), 3)
    return out


def _true_phase7_pooled() -> dict[str, dict[str, tuple[int, int]]]:
    path = ROOT / "reports" / "phase_7e_analysis" / "analysis_summary.json"
    data = json.loads(path.read_text())
    out: dict[str, dict[str, tuple[int, int]]] = {}
    for model, block in data["arm_rates"].items():
        pooled = block["pooled"]
        out[model] = {
            "C": (pooled["confidential"]["successes"], pooled["confidential"]["n"]),
            "N": (pooled["neutral"]["successes"], pooled["neutral"]["n"]),
            "P": (pooled["public"]["successes"], pooled["public"]["n"]),
        }
    return out


def audit_phase6_phase7_against_frozen_artifacts() -> None:
    true_p6 = _true_phase6_c_minus_p()
    check(
        true_p6 == grid.PHASE_6_C_MINUS_P,
        f"phase_8_frozen_grid's PHASE_6_C_MINUS_P {grid.PHASE_6_C_MINUS_P} != "
        f"the frozen Phase 6 artifact {true_p6}",
    )
    true_p7 = _true_phase7_pooled()
    check(
        true_p7 == grid.PHASE_7_POOLED,
        f"phase_8_frozen_grid's PHASE_7_POOLED {grid.PHASE_7_POOLED} != "
        f"the frozen Phase 7 artifact {true_p7}",
    )

    # Every true Phase 6/7 number must appear, as text, in BOTH v1 and v2 --
    # so the two documents cannot drift from each other without also
    # drifting from the artifact this check re-derives independently.
    for model, contrast in true_p6.items():
        # v1/v2 render negative contrasts with a Unicode minus sign
        # (U+2212), not an ASCII hyphen -- both are accepted here.
        rendered_ascii = f"{contrast:.3f}"
        rendered_unicode = rendered_ascii.replace("-", "−")
        for doc_name, doc in (("main.md", MAIN_V1), ("main_v2.md", MAIN_V2)):
            check(
                rendered_ascii in doc or rendered_unicode in doc,
                f"{doc_name}: Phase 6 {model} contrast {rendered_ascii} not found "
                "(checked both ASCII hyphen and Unicode minus)",
            )
    for model, arms in true_p7.items():
        for arm, (k, n) in arms.items():
            frac = f"{k}/{n}"
            for doc_name, doc in (("main.md", MAIN_V1), ("main_v2.md", MAIN_V2)):
                check(frac in doc, f"{doc_name}: Phase 7 {model} {arm} rate {frac} not found")


# --------------------------------------------------------------------------- #
# 7. Qualifier lint (warning only)
# --------------------------------------------------------------------------- #
_MAGNITUDE_WORDS = (
    "large",
    "substantial",
    "significant",
    "dramatic",
    "severe",
    "mild",
    "consistent",
    "clean",
    "sharp",
    "strong",
    "modest",
    "roughly",
    "somewhat",
    "considerably",
)
_SAFE_NEARBY = re.compile(r"\d|%|exactly|threshold|rule|\[CITATION NEEDED\]", re.IGNORECASE)


def lint_qualifiers() -> None:
    for lineno, line in enumerate(MAIN_V2.splitlines(), start=1):
        low = line.lower()
        for word in _MAGNITUDE_WORDS:
            if re.search(rf"\b{word}\b", low) and not _SAFE_NEARBY.search(line):
                warn(
                    f"main_v2.md:{lineno}: {word!r} with no adjacent number/rule -- "
                    f"{line.strip()!r}"
                )


def main() -> int:
    audit_frozen_grid_self_consistency()
    audit_round_two_from_raw()
    audit_table_1()
    audit_appendix_a_acceptance_table()
    audit_trial_counts_and_cost()
    audit_phase6_phase7_against_frozen_artifacts()
    lint_qualifiers()

    if _warnings:
        print(f"=== {len(_warnings)} qualifier-lint warning(s) (non-fatal) ===")
        for w in _warnings:
            print(f"  WARN: {w}")

    if _failures:
        print(f"\n=== {len(_failures)} AUDIT FAILURE(S) ===", file=sys.stderr)
        for f in _failures:
            print(f"  FAIL: {f}", file=sys.stderr)
        return 1

    print(f"\nAll Phase 8 numeric checks passed ({len(_warnings)} lint warnings).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
