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
  8. The v1 tables restored into v2 (Phase 7 contrast-summary table,
     secondary-diagnostics table, the Phase-6-vs-Phase-7 comparison
     table, and the three Appendix C per-scenario tables) are extracted
     from both documents and compared row-for-row, whitespace-normalized
     -- not just spot-checked for a few numbers. A restored table that
     was mistranscribed in any single cell fails here even if that cell
     never appears in prose.
  9. Every per-framing calibration-separation figure (permit - suppress)
     quoted for gpt-5.6-terra in section 6.1 equals the frozen grid's
     separation() and appears verbatim in that sentence -- catches a
     flattened claim the pass/fail-only sensitivity check in item 1 lets
     through.
 10. Terra-flattening lint (warning): "three of four models never <verb>"
     with the models as the subject of the negation is false (terra was
     in-band at F2/F3). Warns on that construction unless a simultaneity
     token nearby marks it as the correct "no framing placed three of
     four ... simultaneously" form.
 11. Every arXiv id cited in main_v2.md is in VERIFIED_ARXIV_IDS -- the
     set individually fetched from arxiv.org and checked for title,
     authors, and that the paper supports the claim it is cited for. A
     new id fails the build until it is verified the same way and
     recorded. This is the one surface no number-vs-artifact check can
     cover: a fabricated citation parses fine.
 12. Appendix B raw-trials SHA-256 hashes: round two matches the
     verify-script's EXPECTED_SHA256 (checked against bytes on disk by
     check 2); round one matches docs/phase_8c_pilot_result.md.
 13. paper/arxiv/main_v2.tex mirrors the Markdown: Table 1, the
     acceptance table, trial counts/costs, the Phase 6/7 numbers, the
     terra separations, the Appendix B hashes, and the five restored
     tables (data rows token-for-token vs the .md). The .tex is a hand
     transcription and would otherwise be an unchecked surface.
 14. references_v2.bib: every arXiv eprint is in VERIFIED_ARXIV_IDS or
     carried from v1's verified references.bib; AgentLeak (2602.11510)
     appears nowhere as an entry; every \cite key in main_v2.tex
     resolves; no bare inline arXiv id is left in the .tex body.
     Qualifier and terra-flattening lints also run on the .tex.

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
MAIN_V2_TEX = (ROOT / "paper" / "arxiv" / "main_v2.tex").read_text()
REFS_V2_BIB = (ROOT / "paper" / "arxiv" / "references_v2.bib").read_text()
REFS_V1_BIB = (ROOT / "paper" / "arxiv" / "references.bib").read_text()


def _tex_flat(tex: str) -> str:
    """A plain-text view of the .tex for 'does this literal/number appear'
    checks: drop TeX math/grouping punctuation and macros so that e.g.
    ``$5/40 = 0.125$`` -> ``5/40 = 0.125`` and ``13{,}184`` -> ``13,184``."""
    s = re.sub(r"(?m)^\s*%.*$", "", tex)  # drop comment lines
    s = re.sub(r"\\code\{([^{}]*)\}", r"\1", s)  # \code{x} -> x
    s = re.sub(r"\\(?:textbf|emph|texttt|mbox)\{([^{}]*)\}", r"\1", s)
    s = s.replace("{,}", ",")
    s = s.replace(r"\$", "\x00").replace(r"\%", "%")  # protect escaped $
    s = s.replace(r"\,", "").replace("~", " ").replace("---", "—")
    s = re.sub(r"\\[a-zA-Z]+", " ", s)  # remaining control words
    s = s.replace("$", "").replace("{", "").replace("}", "")
    s = s.replace("\x00", "$")  # restore escaped $ as a literal dollar
    return re.sub(r"[ \t]+", " ", s)


MAIN_V2_TEX_FLAT = _tex_flat(MAIN_V2_TEX)

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
# 9. Calibration-separation values quoted in main_v2.md S6.1: every
#    per-framing "permit - suppress" figure the prose states for
#    gpt-5.6-terra must equal the frozen grid's separation() and must
#    appear, as text, in the same sentence -- catches a flattened claim
#    ("1.000 in every round-one framing") that the pass/fail-only
#    sensitivity check in section 1 does not.
# --------------------------------------------------------------------------- #
def audit_calibration_separations_in_s61() -> None:
    seps = grid.calibration_separations("gpt-5.6-terra")
    m = re.search(
        r"gpt-5\.6-terra`'s calibration separation.*?round two[^.]*\.",
        MAIN_V2,
        re.DOTALL,
    )
    check(m is not None, "S6.1: could not locate the terra calibration-separation sentence")
    if m is None:
        return
    sentence = " ".join(m.group(0).split())  # collapse the manuscript's line wrapping
    for framing, value in seps.items():
        token = f"{value:.3f} ({framing})"
        check(
            token in sentence,
            f"S6.1: expected {token!r} (from frozen grid separation()) "
            f"in the terra calibration sentence; not found",
        )


# --------------------------------------------------------------------------- #
# 8. Restored v1 tables: extracted from both documents and compared
#    row-for-row (whitespace-normalized), not just spot-checked.
# --------------------------------------------------------------------------- #
_TABLE_BLOCK_RE = re.compile(r"(?:^\|.*\|\s*$\n?)+", re.MULTILINE)


def _normalize_table_block(block: str) -> list[str]:
    """One row per line, internal whitespace collapsed, blank lines dropped."""
    return [" ".join(line.split()) for line in block.strip().splitlines() if line.strip()]


def _table_after(text: str, anchor: str, *, occurrence: int = 1) -> str:
    """The first markdown table block that starts after the nth occurrence
    of `anchor` in `text`."""
    idx = -1
    for _ in range(occurrence):
        idx = text.find(anchor, idx + 1)
        if idx == -1:
            raise AuditError(f"anchor not found: {anchor!r}")
    m = _TABLE_BLOCK_RE.search(text, idx)
    if not m:
        raise AuditError(f"no table block found after anchor: {anchor!r}")
    return m.group(0)


def audit_restored_tables_match_v1() -> None:
    pairs = [
        ("Phase 7 pooled arm rates", "**Phase 7 pooled arm rates**", 1, 1),
        ("Phase 7 per-model contrast summary", "**Phase 7 per-model contrast summary**", 1, 1),
        ("Secondary diagnostics table", "cred. tok. | prim.+ | prim. \\| relay |", 1, 1),
        (
            "Cross-phase (Phase 6 vs Phase 7) comparison table",
            "| model | earlier C",
            1,
            1,
        ),
        ("Appendix C − N table", "**C − N (confidential", 1, 1),
        ("Appendix P − N table", "**P − N (public", 1, 1),
        ("Appendix C − P table", "**C − P (confidential", 1, 1),
    ]
    for label, anchor, v1_occ, v2_occ in pairs:
        v1_block = _normalize_table_block(_table_after(MAIN_V1, anchor, occurrence=v1_occ))
        v2_block = _normalize_table_block(_table_after(MAIN_V2, anchor, occurrence=v2_occ))
        check(
            v1_block == v2_block,
            f"restored table {label!r} does not match v1 row-for-row:\n"
            f"  v1: {v1_block}\n  v2: {v2_block}",
        )


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


# gpt-5.6-terra is the model that breaks the "GPT-5.6 group behaves as one"
# grouping in BOTH directions: in-band at F2/F3 in round one, complete
# floor in round two. Summary prose in the intro/discussion repeatedly
# flattened it into "three of four models never <verb>", making the models
# the subject of the negation -- which is false (terra was in-band twice).
# The CORRECT construction makes a framing the subject ("no framing placed
# three of four models ... simultaneously"), so a simultaneity token
# nearby means it is fine. Warn only on "three of four models" directly
# governing a negated past-tense verb, with no simultaneity token close by.
_FLATTENING_RE = re.compile(
    r"(three|3)\s+of\s+(four|4)\s+models['’]?\s+(?:[\w'’]+\s+){0,3}"
    r"(never|did\s+not|do\s+not|failed\s+to|were\s+never|was\s+never)\s+\w+",
    re.IGNORECASE,
)
_SIMULTANEITY_RE = re.compile(
    r"simultaneous|at\s+once|at\s+the\s+same\s+time|together|same\s+framing", re.IGNORECASE
)


def lint_terra_flattening() -> None:
    flat = " ".join(MAIN_V2.split())
    for m in _FLATTENING_RE.finditer(flat):
        window = flat[max(0, m.start() - 80) : m.end() + 80]
        if _SIMULTANEITY_RE.search(window):
            continue
        warn(
            "main_v2.md: possible terra-flattening ('three of four models "
            f"never ...') -- verify against Table 1: {m.group(0)!r}"
        )


# --------------------------------------------------------------------------- #
# 11. Citation identifiers: every arXiv id in main_v2.md must be one that
#     was individually fetched from arxiv.org and checked (title, authors,
#     and that the paper actually says what it is cited for) on the date
#     below. Numbers are machine-checked against frozen artifacts; a
#     fabricated citation looks exactly like a real one to any parser, so
#     the only guard is pinning the vetted set and failing on anything
#     outside it. A NEW arXiv id added to the manuscript fails this check
#     until it is verified the same way and added here.
# --------------------------------------------------------------------------- #
VERIFIED_ARXIV_IDS: dict[str, str] = {
    # id: one-line record of what it was checked to support (verified 2026-09-05)
    "2609.01693": "this paper's own v1 preprint (the front-matter revision note) -- self-reference",
    "2310.11324": "Sclar et al., prompt-format sensitivity, up to 76 acc. pts on LLaMA-2-13B",
    "2502.06065": "Razavi et al., PromptSET / prompt-sensitivity-prediction task",
    "2509.17488": "Wang et al., PrivacyLens-Live -- static privacy benchmark ported to MCP/A2A",
    "2509.14284": "Patil et al., compositional privacy leakage across agents",
}
# Deliberately NOT cited: arXiv:2602.11510 (AgentLeak). It resolves, but
# it is post-training-cutoff and could not be vetted -- its title differs
# between versions and author order came back inconsistent across fetches.
# PrivacyLens-Live and the compositional-privacy paper cover that side and
# are both verified pre-cutoff, so nothing depends on it.
_ARXIV_ID_RE = re.compile(r"arXiv:(\d{4}\.\d{4,5})", re.IGNORECASE)


def audit_citation_ids_are_vetted() -> None:
    found = {m.group(1) for m in _ARXIV_ID_RE.finditer(MAIN_V2)}
    unvetted = found - set(VERIFIED_ARXIV_IDS)
    check(
        not unvetted,
        f"main_v2.md cites arXiv id(s) not in VERIFIED_ARXIV_IDS: {sorted(unvetted)} -- "
        "each must be fetched from arxiv.org and checked (title, authors, claim) "
        "before it goes in the manuscript, then recorded here.",
    )
    missing = set(VERIFIED_ARXIV_IDS) - found
    if missing:
        warn(f"VERIFIED_ARXIV_IDS lists id(s) no longer cited in main_v2.md: {sorted(missing)}")


# --------------------------------------------------------------------------- #
# 12. Appendix B raw-trials SHA-256 hashes. Round two: must match
#     EXPECTED_SHA256 in scripts/verify_phase_8_round2_from_raw.py, which
#     that script checks against the actual bytes on disk (check 2) -- so
#     the manuscript's round-two hashes are machine-tied to the files.
#     Round one: must match docs/phase_8c_pilot_result.md (raw files gone,
#     transcription is the strongest check available, same as check 3).
# --------------------------------------------------------------------------- #
def _hashes_from_markdown_table(text: str, model_line_prefix: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for model in grid.PANEL:
        m = re.search(
            rf"{re.escape(model_line_prefix)}{re.escape(model)}\s*\|\s*`([0-9a-f]{{40,64}})`",
            text,
        )
        if m:
            out[model] = m.group(1)
    return out


def audit_appendix_b_hashes() -> None:
    from scripts.verify_phase_8_round2_from_raw import EXPECTED_SHA256 as R2

    # "**Round one**" / "**Round two**" also appear as run-in headers in
    # S5.3, so anchor to Appendix B first, then split within it.
    app_b = MAIN_V2[MAIN_V2.find("## Appendix B") :]
    r1_start = app_b.find("**Round one**")
    r2_start = app_b.find("**Round two**")
    other_start = app_b.find("**Other counts.**")
    check(
        0 <= r1_start < r2_start < other_start,
        "Appendix B: round one/two/other blocks not in expected order",
    )
    r1_block = app_b[r1_start:r2_start]
    r2_block = app_b[r2_start:other_start]

    v2_r1 = _hashes_from_markdown_table(r1_block, "raw `trials.jsonl` — ")
    v2_r2 = _hashes_from_markdown_table(r2_block, "raw `trials.jsonl` — ")

    for model in grid.PANEL:
        check(
            v2_r2.get(model) == R2[model],
            f"Appendix B round-two hash for {model}: {v2_r2.get(model)!r} != "
            f"verify-script EXPECTED_SHA256 {R2[model]!r}",
        )

    doc1 = (ROOT / "docs" / "phase_8c_pilot_result.md").read_text()
    doc1_hashes = _hashes_from_markdown_table(doc1, "| ")
    for model in grid.PANEL:
        check(
            v2_r1.get(model) == doc1_hashes.get(model),
            f"Appendix B round-one hash for {model}: {v2_r1.get(model)!r} != "
            f"docs/phase_8c_pilot_result.md {doc1_hashes.get(model)!r}",
        )


# --------------------------------------------------------------------------- #
# 13. paper/arxiv/main_v2.tex mirrors the manuscript. Every structured
#     check above that reads the Markdown is re-run against the .tex:
#     Table 1 grid, the acceptance table, trial counts and costs, the
#     Phase 6/7 numbers, the terra calibration separations, the Appendix B
#     hashes, and the five restored tables (data rows compared token-for-
#     token to the Markdown, which check 8 already pins to v1). The .tex
#     is a hand-transcription; without this it can drift from the .md.
# --------------------------------------------------------------------------- #
_TEX_MODEL_ROW_RE = re.compile(
    r"^(gpt-5\.6-sol|gpt-5\.6-terra|gpt-5\.6-luna|claude-sonnet-5)\s*"
    r"&\s*\$([\d.]+)\$\s*&\s*\$([\d.]+)\$\s*&\s*\$([\d.]+)\$\s*"
    r"&\s*\$([\d.]+)\$\s*&\s*\$([\d.]+)\$\s*&\s*\$([\d.]+)\$\s*\\\\",
    re.MULTILINE,
)
_TEX_ACCEPT_ROW_RE = re.compile(
    r"^(F[1-6])\s*&\s*(?:yes|no)\s*\((\d)/4\)\s*&\s*(?:yes|no)\s*\((\d)/4\)\s*&",
    re.MULTILINE,
)


def _tex_table_block(label: str) -> str:
    m = re.search(
        rf"\\label\{{{re.escape(label)}\}}.*?\\end\{{tabular\}}", MAIN_V2_TEX, re.DOTALL
    )
    if not m:
        raise AuditError(f"main_v2.tex: no table block for \\label{{{label}}}")
    return m.group(0)


def _data_row_numbers(block: str) -> list[str]:
    """Ordered numeric tokens from a table's DATA rows only (rows with a
    digit/digit fraction or a decimal, plus mean/median rows). Unicode
    minus and en/em dashes normalised out first so md and tex agree."""
    out: list[str] = []
    for raw in block.splitlines():
        line = raw.replace("−", "-").replace("–", " ").replace("—", " ").replace("--", " ")
        is_data = re.search(r"\d/\d|\d\.\d", line) or re.match(
            r"\s*(\|\s*)?(\\textbf\{)?\*{0,2}(mean|median)\b", line, re.IGNORECASE
        )
        if not is_data:
            continue
        out.extend(re.findall(r"[+-]?\d+(?:\.\d+)?", line))
    return out


def audit_tex_mirrors_manuscript() -> None:
    # -- Table 1 grid --
    rows = _TEX_MODEL_ROW_RE.findall(_tex_table_block("tab:grid"))
    check(len(rows) == 4, f"main_v2.tex Table 1: expected 4 rows, found {len(rows)}")
    for model, *cells in rows:
        got = [float(c) for c in cells]
        want = [grid.N_RATE[model][f] for f in grid.ALL_FRAMINGS]
        check(got == want, f"main_v2.tex Table 1 row {model}: {got} != frozen {want}")

    # -- acceptance table --
    acc = _TEX_ACCEPT_ROW_RE.findall(_tex_table_block("tab:accept"))
    check(len(acc) == 6, f"main_v2.tex acceptance table: expected 6 rows, found {len(acc)}")
    for framing, hp, sp in acc:
        check(
            int(hp) == grid.headroom_pass_count(framing)
            and int(sp) == grid.sensitivity_pass_count(framing),
            f"main_v2.tex acceptance {framing}: ({hp}/4,{sp}/4) != recomputed "
            f"({grid.headroom_pass_count(framing)}/4,{grid.sensitivity_pass_count(framing)}/4)",
        )

    # -- trial counts, costs, main-study totals --
    for literal in ("640 trials", "480 trials", "576 trials", "13,184", "13,200"):
        check(
            literal in MAIN_V2_TEX_FLAT,
            f"main_v2.tex: expected literal {literal!r} not found (flattened)",
        )
    for cost in (grid.ROUND_ONE_COST_USD, grid.ROUND_TWO_COST_USD):
        check(f"${cost}" in MAIN_V2_TEX_FLAT, f"main_v2.tex: cost ${cost} not found")

    # -- Phase 6/7 numbers --
    for _model, contrast in _true_phase6_c_minus_p().items():
        check(
            f"{contrast:.3f}" in MAIN_V2_TEX_FLAT,
            f"main_v2.tex: Phase 6 contrast {contrast:.3f} not found (flattened)",
        )
    for _model, arms in _true_phase7_pooled().items():
        for _arm, (k, n) in arms.items():
            check(
                f"{k}/{n}" in MAIN_V2_TEX_FLAT,
                f"main_v2.tex: Phase 7 rate {k}/{n} not found (flattened)",
            )

    # -- terra calibration separations --
    for framing, value in grid.calibration_separations("gpt-5.6-terra").items():
        tok = f"{value:.3f} ({framing})"
        check(tok in MAIN_V2_TEX_FLAT, f"main_v2.tex: terra separation token {tok!r} not found")

    # -- Appendix B hashes (all 8 raw + 2 shared) --
    from scripts.verify_phase_8_round2_from_raw import EXPECTED_SHA256 as R2

    shared = (
        "32e6ba77c56554de69705f85d547b3e3c48d9d2e2be35d07ed093570d893f2be",
        "96c91c0be27b33a30cd9a9f5699acbc19e3d15227111c6a34b17d8dc156e65b5",
    )
    for h in (*shared, *R2.values()):
        check(h in MAIN_V2_TEX, f"main_v2.tex: pinned hash {h[:12]}... not found")

    # -- five restored tables: data rows token-for-token vs the Markdown --
    restored = [
        ("**Phase 7 pooled arm rates**", 1, "tab:p7arms"),
        ("**Phase 7 per-model contrast summary**", 1, "tab:p7con"),
        ("cred. tok. | prim.+ | prim. \\| relay |", 1, "tab:p7diag"),
        ("| model | earlier C", 1, "tab:xphase"),
        ("**C − N (confidential", 1, "tab:scen-cn"),
        ("**P − N (public", 1, "tab:scen-pn"),
        ("**C − P (confidential", 1, "tab:scen-cp"),
    ]
    for anchor, occ, label in restored:
        md_nums = _data_row_numbers(_table_after(MAIN_V2, anchor, occurrence=occ))
        tex_nums = _data_row_numbers(_tex_table_block(label))
        check(
            md_nums == tex_nums,
            f"main_v2.tex table {label}: data-row numbers differ from main_v2.md\n"
            f"  md : {md_nums}\n  tex: {tex_nums}",
        )


# --------------------------------------------------------------------------- #
# 14. references_v2.bib + \cite keys in main_v2.tex.
#     - every arXiv eprint in the .bib is in VERIFIED_ARXIV_IDS (this
#       session's fetched-and-checked set) OR is carried verbatim from
#       v1's already-verified references.bib;
#     - AgentLeak (2602.11510) appears nowhere as an entry;
#     - every \citep/\citet key in the .tex resolves to a .bib entry;
#     - no bare "arXiv:NNNN.NNNNN" is left inline in the .tex body (they
#       are citations now), except the self-reference in the draft note.
# --------------------------------------------------------------------------- #
def audit_bib_and_citations() -> None:
    # strip % comments so the AgentLeak-exclusion note (which names the id)
    # is not mistaken for a citation of it.
    bib_body = re.sub(r"(?m)^\s*%.*$", "", REFS_V2_BIB)
    tex_body = re.sub(r"(?m)^\s*%.*$", "", MAIN_V2_TEX)

    bib_keys = set(re.findall(r"@\w+\{([^,\s]+),", bib_body))
    bib_eprints = set(re.findall(r"eprint\s*=\s*\{(\d{4}\.\d{4,5})\}", bib_body))
    bib_arxiv_any = set(_ARXIV_ID_RE.findall(bib_body)) | bib_eprints
    v1_arxiv = set(_ARXIV_ID_RE.findall(re.sub(r"(?m)^\s*%.*$", "", REFS_V1_BIB)))

    for aid in bib_arxiv_any:
        check(
            aid in VERIFIED_ARXIV_IDS or aid in v1_arxiv,
            f"references_v2.bib references arXiv:{aid}, which is neither in "
            "VERIFIED_ARXIV_IDS (fetched and checked this round) nor carried "
            "from v1's verified references.bib.",
        )
    check(
        "2602.11510" not in bib_arxiv_any,
        "references_v2.bib contains AgentLeak (arXiv:2602.11510) as data -- it "
        "was deliberately excluded; do not re-add it without verifying it.",
    )
    # the exclusion note itself must stay, so nobody re-adds it in good faith
    check(
        "2602.11510" in REFS_V2_BIB and "AgentLeak" in REFS_V2_BIB,
        "references_v2.bib: the AgentLeak-exclusion note has been removed.",
    )

    # each session-verified id must be an eprint in its own entry, with the
    # first author's surname in the same entry.
    entries = re.split(r"(?=^@)", bib_body, flags=re.MULTILINE)
    surname = {
        "2310.11324": "Sclar",
        "2502.06065": "Razavi",
        "2509.17488": "Wang",
        "2509.14284": "Patil",
        "2609.01693": "Mahapatra",
    }
    for eid, name in surname.items():
        hit = [e for e in entries if f"{{{eid}}}" in e]
        check(
            len(hit) == 1 and "eprint" in hit[0] and name in hit[0],
            f"references_v2.bib: expected exactly one entry with eprint {eid} "
            f"and first-author surname {name!r}; found {len(hit)}.",
        )

    # \cite keys in the .tex all resolve to a bib entry
    cited: set[str] = set()
    for grp in re.findall(r"\\cite[a-z]*\{([^}]+)\}", tex_body):
        cited.update(k.strip() for k in grp.split(","))
    check(
        not (cited - bib_keys),
        f"main_v2.tex cites undefined bib keys: {sorted(cited - bib_keys)}",
    )

    # no bare inline arXiv id left in the .tex body except the self-ref,
    # which is rendered as \code{arXiv:2609.01693} in the draft note.
    for m in _ARXIV_ID_RE.finditer(tex_body):
        ctx = tex_body[max(0, m.start() - 45) : m.start() + 20]
        check(
            m.group(1) == "2609.01693" and r"\code{arXiv:2609.01693}" in ctx,
            f"main_v2.tex: bare inline arXiv:{m.group(1)} -- use \\citep{{...}}.",
        )


def _lint_text(label: str, text: str) -> None:
    for lineno, line in enumerate(text.splitlines(), start=1):
        low = line.lower()
        for word in _MAGNITUDE_WORDS:
            if re.search(rf"\b{word}\b", low) and not _SAFE_NEARBY.search(line):
                warn(f"{label}:{lineno}: {word!r} with no adjacent number/rule -- {line.strip()!r}")
    flat = " ".join(text.split())
    for fm in _FLATTENING_RE.finditer(flat):
        window = flat[max(0, fm.start() - 80) : fm.end() + 80]
        if _SIMULTANEITY_RE.search(window):
            continue
        warn(f"{label}: possible terra-flattening -- {fm.group(0)!r}")


def main() -> int:
    audit_frozen_grid_self_consistency()
    audit_round_two_from_raw()
    audit_table_1()
    audit_appendix_a_acceptance_table()
    audit_trial_counts_and_cost()
    audit_phase6_phase7_against_frozen_artifacts()
    audit_restored_tables_match_v1()
    audit_calibration_separations_in_s61()
    audit_citation_ids_are_vetted()
    audit_appendix_b_hashes()
    audit_tex_mirrors_manuscript()
    audit_bib_and_citations()
    lint_qualifiers()
    lint_terra_flattening()
    _lint_text("main_v2.tex", MAIN_V2_TEX)

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
