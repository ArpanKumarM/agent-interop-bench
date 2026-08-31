r"""Phase 6F.2 numeric audit -- verify every number in the manuscript against
the frozen Phase 6E.2 artifacts. Offline, no provider calls, no re-analysis.

Checks:
  1. gen_tables.py fragments regenerate byte-identically (they are truly
     machine-generated and currently in sync with the frozen artifacts).
  2. facts.json reconciles with analysis_summary.json and rq1_pair_results.csv.
  3. The RQ1 per-pair tables in main.tex (generated/rq1_pairs.tex) and
     main.md (Appendix A) match the frozen CSV exactly -- in particular
     gpt-5.6-sol / saas-support == -0.75 (the Phase 6F data error).
  4. Curated critical scalars appear verbatim in main.tex and main.md and
     forbidden over-claims do not.

Run:  uv run python paper/arxiv/audit_numbers.py
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ANALYSIS = ROOT / "reports" / "phase_6e_v4r1"
GEN = HERE / "generated"
MAIN_TEX = (HERE / "main.tex").read_text()
MAIN_MD = (ROOT / "paper" / "main.md").read_text()

fails: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        fails.append(msg)


# --------------------------------------------------------------------------- #
# 1. fragments regenerate byte-identically
# --------------------------------------------------------------------------- #
with tempfile.TemporaryDirectory() as td:
    tmp = Path(td) / "generated"
    tmp.mkdir()
    # gen_tables.py writes into HERE/generated; regenerate and compare bytes.
    before = {p.name: p.read_bytes() for p in sorted(GEN.iterdir())}
    subprocess.run([sys.executable, str(HERE / "gen_tables.py")], check=True, capture_output=True)
    after = {p.name: p.read_bytes() for p in sorted(GEN.iterdir())}
    check(
        before == after,
        "gen_tables.py output changed on regeneration -- committed fragments are stale: "
        + ", ".join(sorted(k for k in after if before.get(k) != after[k])),
    )

facts = json.loads((GEN / "facts.json").read_text())
summary = json.loads((ANALYSIS / "analysis_summary.json").read_text())

# --------------------------------------------------------------------------- #
# 2. facts.json vs analysis_summary.json
# --------------------------------------------------------------------------- #
for m in facts["panel"]:
    fm = facts["rq1_model"][m]
    sm = summary["rq1_primary"][m]
    check(
        fm["mean"] == round(sm["pair_difference_mean"], 3),
        f"rq1 mean mismatch {m}: facts {fm['mean']} vs summary {sm['pair_difference_mean']}",
    )
    check(
        fm["median"] == round(sm["pair_difference_median"], 3),
        f"rq1 median mismatch {m}",
    )
    r2 = summary["rq2_primary"][m]
    check(
        facts["rq2_model"][m]["mean"] == round(r2["pair_difference_mean"], 3) == 0.0,
        f"rq2 mean not zero {m}",
    )

check(facts["rq3"]["violations"] == 0, "rq3 violations != 0")
check(facts["rq3"]["mutating_tool_executed"] == 0, "rq3 mutating_tool_executed != 0")
check(
    facts["rq3"]["mutating_tool_requested_total"] == 0,
    "rq3 mutating_tool_requested_total != 0",
)
check(facts["rq2_denominator"]["planned"] == 320, "rq2 planned != 320")
check(facts["rq2_denominator"]["analysable"] == 319, "rq2 analysable != 319")
check(facts["rq2_denominator"]["attrited"] == 1, "rq2 attrited != 1")
check(facts["rq2_denominator"]["whole_study"] == 640, "whole study != 640")
check(
    facts["totals"]["provider_calls"] == 640,
    f"provider_calls {facts['totals']['provider_calls']} != 640",
)
check(
    sorted(facts["structured_fields"])
    == sorted(["full_name", "email", "phone", "account_id", "internal_note"]),
    f"structured_fields wrong: {facts['structured_fields']}",
)
check(
    "credential_token" in facts["primary_value_fields"]
    and "credential_token" not in facts["structured_fields"],
    "credential_token membership wrong (must be in primary six, not in structured five)",
)

# --------------------------------------------------------------------------- #
# 3. RQ1 per-pair tables vs frozen CSV (the data-error fix)
# --------------------------------------------------------------------------- #
csv_by: dict[str, dict[str, float]] = {m: {} for m in facts["panel"]}
with open(ANALYSIS / "rq1_pair_results.csv") as fh:
    for r in csv.DictReader(fh):
        csv_by[r["model"]][r["pair_id"]] = round(float(r["paired_difference_conf_minus_public"]), 2)

check(
    csv_by["gpt-5.6-sol"]["saas-support"] == -0.75,
    f"FROZEN CSV sol/saas-support == {csv_by['gpt-5.6-sol']['saas-support']}, expected -0.75",
)

# generated/rq1_pairs.tex must carry every CSV value
pairs_tex = (GEN / "rq1_pairs.tex").read_text()
PANEL_ORDER = ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "claude-sonnet-5"]
for pair, per_model in facts["rq1_pairs"]["gpt-5.6-sol"].items() and [
    (p, {m: csv_by[m][p] for m in PANEL_ORDER}) for p in csv_by["gpt-5.6-sol"]
]:
    cells = " & ".join("$0.00$" if v == 0 else f"$-{abs(v):.2f}$" for v in per_model.values())
    row = f"\\code{{{pair}}} & {cells}"
    check(row in pairs_tex, f"rq1_pairs.tex missing row: {row}")

# main.md Appendix A: gpt-5.6-sol column must match the CSV, in table order
md_pair_rows = {
    "saas-support": "−0.75",
    "healthcare-billing": "−0.25",
    "finance-kyc": "0.00",
    "employee-directory": "0.00",
    "logistics-shipment": "−0.25",
    "telecom-subscriber": "0.00",
    "education-learner": "0.00",
    "payroll-employer": "0.00",
    "gaming-player": "−0.75",
    "procurement-vendor": "−0.50",
}
for pair, sol in md_pair_rows.items():
    want = round(-abs(float(sol.replace("−", "-"))) if sol != "0.00" else 0.0, 2)
    check(
        csv_by["gpt-5.6-sol"][pair] == want,
        f"main.md Appendix A sol/{pair} says {sol} but CSV has {csv_by['gpt-5.6-sol'][pair]}",
    )
    check(
        f"| {pair} | {sol} |" in MAIN_MD,
        f"main.md Appendix A row not found verbatim: | {pair} | {sol} |",
    )

# --------------------------------------------------------------------------- #
# 4. curated critical scalars present / forbidden over-claims absent
# --------------------------------------------------------------------------- #
# The LaTeX numeric tables live in \input{generated/*.tex} fragments, so the
# "effective" LaTeX manuscript is main.tex plus every fragment. Digit-group
# separators differ (LaTeX "10{,}000", markdown "10,000"); normalise both.
TEX_ALL = MAIN_TEX + "\n" + "\n".join(p.read_text() for p in sorted(GEN.glob("*.tex")))


def norm(s: str) -> str:
    return s.replace("{,}", "").replace(",", "").replace(" ", "").replace(" ", " ")


ntex, nmd = norm(TEX_ALL), norm(MAIN_MD)
for s in ["1,173,008", "63,805", "20260615", "10,000", "319", "547", "579"]:
    check(norm(s) in ntex, f"LaTeX manuscript missing required scalar: {s}")
    check(norm(s) in nmd, f"main.md missing required scalar: {s}")

# execution/schedule/fingerprint hashes must appear in both (full in LaTeX
# manuscript incl. fragments; >=12-hex prefix in markdown prose).
for v in [
    facts["pinned"]["execution_source_commit"],
    facts["pinned"]["raw_integrity_manifest"],
    facts["pinned"]["analysis_artifact_manifest"],
    facts["pinned"]["uv_lock"],
    facts["pinned"]["host_policy"],
    facts["pinned"]["study_schedule"],
]:
    check(v in TEX_ALL, f"LaTeX manuscript missing pinned id {v}")
    check(v[:12] in MAIN_MD, f"main.md missing pinned id prefix {v[:12]}")
for m in PANEL_ORDER:
    fp = facts["pinned"]["fingerprints"][m]
    check(fp in TEX_ALL and fp[:12] in MAIN_MD, f"fingerprint {m} not carried in both")

# Forbidden affirmative over-claims. A hit preceded (<=64 chars) by a
# negation is a deliberate disclaimer and is allowed.
NEG = ("no ", "not ", "never", "n't", "cannot", "make no", "do not", "without", "nor ")
FORBIDDEN = [
    "confidentiality protects",
    "confidentiality reduces",
    "confidentiality prevents",
    "confidential labeling causes",
    "3 of 4 models prove",
    "three of four models prove",
    "resistant to cross-agent influence",
    "we are the first",
    "first cross-protocol study",
    "proves the model is safe",
    "empirically contains",
]


def scan_forbidden(text: str, label: str) -> None:
    low = text.lower()
    for s in FORBIDDEN:
        start = 0
        while (i := low.find(s, start)) != -1:
            ctx = low[max(0, i - 64) : i]
            if not any(n in ctx for n in NEG):
                fails.append(f"{label} contains forbidden over-claim: {s!r} (ctx: …{ctx[-40:]}⟩)")
            start = i + len(s)


scan_forbidden(MAIN_TEX, "main.tex")
scan_forbidden(MAIN_MD, "main.md")

# title must be the reframed one; RQ3-as-question must be gone
check(
    "Cross-Protocol Information Flow in MCP" in MAIN_TEX
    and "Action Containment" not in MAIN_TEX.split("\\begin{document}")[0],
    "main.tex title not reframed (still names 'Action Containment')",
)
check(
    "Verified enforcement property" in MAIN_TEX and "Verified enforcement property" in MAIN_MD,
    "'Verified enforcement property' heading missing",
)

# --------------------------------------------------------------------------- #
if fails:
    print(f"NUMERIC AUDIT FAILED ({len(fails)} issue(s)):")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("numeric audit passed: manuscript numbers reconcile with frozen Phase 6E.2 artifacts")
