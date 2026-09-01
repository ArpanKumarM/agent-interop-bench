r"""Phase 7F numeric audit -- verify every number in the manuscript against
the frozen analysis artifacts of BOTH studies. Offline, no provider calls,
no re-analysis.

Checks:
  1. gen_tables.py fragments regenerate byte-identically.
  2. facts.json reconciles with the frozen Phase 7E analysis
     (reports/phase_7e_analysis/analysis_summary.json) -- arm rates,
     the three contrasts, scenario-level values, means, medians, signs --
     and with the frozen Phase 6E.2 analysis for the descriptive C-P
     comparison, the secondary null experiment, and the enforcement
     property.
  3. Every frozen manifest / raw hash the manuscript pins is unchanged:
     Phase 6 raw-integrity + analysis manifests, Phase 7D freeze manifest,
     Phase 7E analysis-artifact manifest, the four Phase 7 raw trials.jsonl
     hashes.
  4. The Phase 7 primary scalars and the pinned identifiers appear in the
     LaTeX manuscript (main.tex + fragments) and in main.md.
  5. Forbidden over-claims (confidential-suppression, causal
     public-permission, "first", provider ranking, RQ3-as-question,
     restored "Action Containment", and present-tense "published" /
     external-"preregistration" claims) do not appear.
  6. The Phase 7 primary contrast table and the descriptive C-P table in
     main.md match the machine-generated fragments.

Run:  uv run python paper/arxiv/audit_numbers.py
"""

from __future__ import annotations

import json
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
P7 = ROOT / "reports" / "phase_7e_analysis"
P6 = ROOT / "reports" / "phase_6e_v4r1"
GEN = HERE / "generated"
MAIN_TEX = (HERE / "main.tex").read_text()
MAIN_MD = (ROOT / "paper" / "main.md").read_text()

PANEL = ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "claude-sonnet-5"]
CONTRASTS = ["C_minus_N", "P_minus_N", "C_minus_P"]

FROZEN = {
    # p6_raw = Phase 6 raw-integrity manifest; p6_ana = Phase 6 analysis
    # manifest; p7d = Phase 7D pre-analysis freeze manifest; p7e = Phase 7E
    # analysis-artifact manifest (all self-hashes).
    "p6_raw": "8310a1f9c1c1464ad1786b832deac328b8d21bf209919f1d57ba66cc1a542695",
    "p6_ana": "db34e1bad9d770dcdf38e1d887550c2eab999ffa404c79cea936be429e540593",
    "p7d": "dad290f5b5ac460bf2d46c74facc05da7197f946ca5a0a2ed2d165c48ad1dd22",
    "p7e": "dbeb7068f1fe318862ba706a788fcc7a46107168f162e0021a04437958603b19",
}
FROZEN_P7_RAW = {
    "gpt-5.6-sol": "5227c8b1deb5562e14698aca6ef3d4f6ff3b033c589b015d7fa587e2faa10346",
    "gpt-5.6-terra": "874e364f7f85eca319634ba1d9351076965e9a51a90cae8792445a4969cab5a1",
    "gpt-5.6-luna": "e1b6736b9fbcf3690388cb7669d4fc74b592c5ebcb9001196124292a7c5bfa29",
    "claude-sonnet-5": "68e0fc5a2b50b0738a29b9d9aebaa7f2c27fb13213a7d428097726b5511e3e37",
}

fails: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        fails.append(msg)


# --------------------------------------------------------------------------- #
# 1. fragments regenerate byte-identically
# --------------------------------------------------------------------------- #
with tempfile.TemporaryDirectory():
    before = {p.name: p.read_bytes() for p in sorted(GEN.iterdir())}
    subprocess.run([sys.executable, str(HERE / "gen_tables.py")], check=True, capture_output=True)
    after = {p.name: p.read_bytes() for p in sorted(GEN.iterdir())}
    check(
        before == after,
        "gen_tables.py output changed on regeneration -- committed fragments are stale: "
        + ", ".join(sorted(k for k in after if before.get(k) != after[k])),
    )

facts = json.loads((GEN / "facts.json").read_text())
a7 = json.loads((P7 / "analysis_summary.json").read_text())
a6 = json.loads((P6 / "analysis_summary.json").read_text())

# --------------------------------------------------------------------------- #
# 2a. facts.json Phase 7 primary vs frozen Phase 7E analysis
# --------------------------------------------------------------------------- #
for m in PANEL:
    fa = facts["p7_arms"][m]
    pr = a7["arm_rates"][m]["pooled"]
    check(
        fa["C"] == [pr["confidential"]["successes"], round(pr["confidential"]["rate"], 3)],
        f"p7 arm C mismatch {m}",
    )
    check(fa["N"] == [pr["neutral"]["successes"], round(pr["neutral"]["rate"], 3)], f"p7 arm N {m}")
    check(fa["P"] == [pr["public"]["successes"], round(pr["public"]["rate"], 3)], f"p7 arm P {m}")
    for k in CONTRASTS:
        s = a7["contrasts_by_model"][m]["summary"][k]
        sc = a7["contrasts_by_model"][m]["scenario_contrasts"]
        ten = [sc[x][k] for x in a7["contrasts"] and s["scenario_order"]]
        fc = facts["p7_contrasts"][m][k]
        check(fc["mean"] == round(s["mean"], 3), f"p7 {k} mean {m}: {fc['mean']} vs {s['mean']}")
        check(fc["median"] == round(s["median"], 3), f"p7 {k} median {m}")
        check(
            fc["signs"]
            == [
                s["sign_counts"]["positive"],
                s["sign_counts"]["zero"],
                s["sign_counts"]["negative"],
            ],
            f"p7 {k} signs {m}",
        )
        check(sum(fc["signs"]) == 10, f"p7 {k} signs do not sum to 10 for {m}")
        check(fc["ten"] == [round(v, 3) for v in ten], f"p7 {k} ten-values {m}")
        # contrast == arm-rate arithmetic, per scenario
        for x in s["scenario_order"]:
            r = a7["arm_rates"][m]["scenarios"][x]
            am = {
                "C_minus_N": ("confidential", "neutral"),
                "P_minus_N": ("public", "neutral"),
                "C_minus_P": ("confidential", "public"),
            }[k]
            want = r[am[0]]["rate"] - r[am[1]]["rate"]
            check(abs(sc[x][k] - want) < 1e-12, f"p7 {k} {m}/{x} != arm-rate arithmetic")
        # mean == mean of the 10 scenario values
        check(abs(s["mean"] - statistics.fmean(ten)) < 1e-12, f"p7 {k} mean != mean(10) {m}")

# Phase 7 structural invariants surfaced into facts
st = facts["p7_structure"]
check(st["trials_consumed"] == 480, "p7 trials_consumed != 480")
check(all(v == 120 for v in st["per_model"].values()), "p7 per-model != 120")
check(
    st["arms_per_model"] == {"confidential": 40, "neutral": 40, "public": 40}, "p7 arms != 40/40/40"
)
check(st["scenarios"] == 10 and st["repeats_per_scenario_arm"] == 4, "p7 scenarios/repeats wrong")
check(
    facts["generalization_unit"] == "scenario" and facts["n_scenarios"] == 10,
    "gen unit not scenario/10",
)
check(facts["repeats_are_independent"] is False, "repeats flagged independent")
check(facts["phase6_phase7_pooled"] is False, "phase6+phase7 pooled")
check(
    facts["no_p_values"]
    and facts["no_significance_tests"]
    and facts["no_bootstrap_or_intervals_phase7"]
    and facts["no_cross_model_pooling_phase7"],
    "a Phase 7 no-inferential-stats flag is unset",
)
check(
    sorted(facts["structured_fields"])
    == sorted(["full_name", "email", "phone", "account_id", "internal_note"]),
    f"structured_fields wrong: {facts['structured_fields']}",
)
check(
    "credential_token" in facts["primary_value_fields"]
    and "credential_token" not in facts["structured_fields"],
    "credential_token membership wrong (in primary six, not in structured five)",
)
# the interpretation clarification is surfaced, not hidden
ic = facts["interp_clarification"]
check(ic["impl_classifier_not_in_frozen_plan"] is True, "interp clarification not recorded")
check(ic["claude_cn_mean"] == -0.1 and ic["claude_cn_signs"] == [0, 7, 3], "claude C-N facts wrong")

# --------------------------------------------------------------------------- #
# 2b. facts.json vs frozen Phase 6 analysis (comparison / RQ2 / enforcement)
# --------------------------------------------------------------------------- #
for m in PANEL:
    c = a7["phase6_phase7_descriptive_comparison"][m]
    fc = facts["p6p7_cp"][m]
    check(fc["p6_mean"] == round(c["phase6_C_minus_P_mean"], 3), f"p6p7 p6 mean {m}")
    check(fc["p7_mean"] == round(c["phase7_C_minus_P_mean"], 3), f"p6p7 p7 mean {m}")
    check(fc["direction"] == c["qualitative_direction"], f"p6p7 direction {m}")
    r2 = a6["rq2_primary"][m]
    check(
        facts["rq2_model"][m]["mean"] == round(r2["pair_difference_mean"], 3) == 0.0,
        f"rq2 mean not zero {m}",
    )

check(facts["enforcement"]["violations"] == 0, "enforcement violations != 0")
check(facts["enforcement"]["mutating_tool_executed"] == 0, "mutating_tool_executed != 0")
check(
    facts["enforcement"]["mutating_tool_requested_total"] == 0, "mutating_tool_requested_total != 0"
)
check(facts["rq2_denominator"]["planned"] == 320, "rq2 planned != 320")
check(facts["rq2_denominator"]["analysable"] == 319, "rq2 analysable != 319")
check(facts["rq2_denominator"]["attrited"] == 1, "rq2 attrited != 1")
check(facts["totals"]["phase7"]["provider_calls"] == 480, "phase7 provider_calls != 480")
check(facts["totals"]["phase6"]["provider_calls"] == 640, "phase6 provider_calls != 640")

# --------------------------------------------------------------------------- #
# 3. frozen manifests / raw hashes are unchanged
# --------------------------------------------------------------------------- #
p = facts["pinned"]
check(p["p6_raw_integrity_manifest"] == FROZEN["p6_raw"], "p6 raw-integrity manifest changed")
check(p["p6_analysis_artifact_manifest"] == FROZEN["p6_ana"], "p6 analysis manifest changed")
check(p["p7d_manifest_self_hash"] == FROZEN["p7d"], "p7d freeze manifest changed")
check(p["p7_analysis_artifact_manifest"] == FROZEN["p7e"], "p7e analysis manifest changed")
check(p["p7_raw_trials"] == FROZEN_P7_RAW, "a Phase 7 raw trials.jsonl hash changed")
check(
    a6["integrity_manifest_sha256"] == FROZEN["p6_raw"],
    "phase6 summary integrity hash drift",
)

# --------------------------------------------------------------------------- #
# 4. required scalars + pinned ids appear in BOTH manuscripts
# --------------------------------------------------------------------------- #
TEX_ALL = MAIN_TEX + "\n" + "\n".join(x.read_text() for x in sorted(GEN.glob("*.tex")))


def norm(s: str) -> str:
    return s.replace("{,}", "").replace(",", "").replace(" ", "").replace(" ", " ")


ntex, nmd = norm(TEX_ALL), norm(MAIN_MD)
for s in [
    "480",
    "120",
    "10 scenarios",
    "0.800",
    "0.250",
    "0.125",
    "0.100",
    "5/40",
    "37/40",
    "10/40",
    "20260831",
    "319",
    "640",
]:
    check(norm(s) in ntex, f"LaTeX manuscript missing required scalar: {s}")
    check(norm(s) in nmd, f"main.md missing required scalar: {s}")

for v in [
    p["p7_execution_source_commit"],
    p["p7_analysis_impl_commit"],
    p["p7_analysis_plan_hash"],
    p["p7d_manifest_self_hash"],
    p["p7_analysis_artifact_manifest"],
    p["p7_study_schedule"],
    p["p6_execution_source_commit"],
    p["p6_raw_integrity_manifest"],
    p["p6_analysis_artifact_manifest"],
    p["host_policy"],
    p["uv_lock"],
]:
    check(v in TEX_ALL, f"LaTeX manuscript missing pinned id {v}")
    check(v[:12] in MAIN_MD, f"main.md missing pinned id prefix {v[:12]}")
for m in PANEL:
    check(
        FROZEN_P7_RAW[m] in TEX_ALL and FROZEN_P7_RAW[m][:12] in MAIN_MD,
        f"Phase 7 raw hash for {m} not carried in both",
    )
    fp7 = p["p7_fingerprints"][m]
    check(fp7 in TEX_ALL and fp7[:12] in MAIN_MD, f"Phase 7 fingerprint {m} not in both")

# --------------------------------------------------------------------------- #
# 5. forbidden over-claims absent; title reframed; no RQ3-as-question
# --------------------------------------------------------------------------- #
NEG = (
    "no ",
    "not ",
    "never",
    "n't",
    "cannot",
    "make no",
    "do not",
    "without",
    "nor ",
    "no convincing",
    "does not",
    "did not",
)
FORBIDDEN = [
    "public label causes disclosure",
    "the public label causes",
    "permission mechanism proved",
    "permission mechanism is proved",
    "confidential label protects data",
    "confidentiality protects",
    "confidentiality suppresses disclosure",
    "confidentiality suppresses",
    "confidential labeling causes",
    "confidentiality reduces",
    "confidentiality prevents",
    "resistant to cross-agent influence",
    "resistance to adversarial cross-agent influence is shown",
    "we are the first",
    "first cross-protocol study",
    "first composition study",
    "proves the model is safe",
    "empirically contains",
    "empirical action containment",
]


def _flat(text: str) -> str:
    t = text.lower()
    # unwrap LaTeX / markdown emphasis so negations like "\emph{not} show"
    # and "*not* show" read as plain "not show" for context matching.
    t = re.sub(r"\\(?:emph|textbf|textit|texttt|code|mbox)\{([^{}]*)\}", r"\1", t)
    t = t.replace("*", "").replace("{", " ").replace("}", " ")
    return re.sub(r"\s+", " ", t)


def scan_forbidden(text: str, label: str) -> None:
    low = _flat(text)
    for s in FORBIDDEN:
        start = 0
        while (i := low.find(s, start)) != -1:
            ctx = low[max(0, i - 130) : i]
            if not any(n in ctx for n in NEG):
                fails.append(f"{label} contains forbidden over-claim: {s!r} (ctx: ...{ctx[-56:]})")
            start = i + len(s)


scan_forbidden(MAIN_TEX, "main.tex")
scan_forbidden(MAIN_MD, "main.md")

tex_head = MAIN_TEX.split("\\begin{document}")[0]
check(
    "Public-Sharing Labels and Verbatim Field Egress at the MCP" in MAIN_TEX,
    "main.tex title is not the reframed Phase 7F title",
)
check("Public-Sharing Labels and Verbatim Field Egress" in MAIN_MD, "main.md title not reframed")
check(
    "Action Containment" not in MAIN_TEX and "Action Containment" not in MAIN_MD,
    "'Action Containment' framing reappeared",
)
check(
    "Cross-Protocol Information Flow in MCP" not in tex_head,
    "old title 'Cross-Protocol Information Flow in MCP' still in the title block",
)
# the enforcement property must not be numbered as a research question
for bad in ["RQ3:", "\\textbf{RQ3}", "Research Question 3", "**RQ3**"]:
    check(bad not in MAIN_TEX and bad not in MAIN_MD, f"RQ3-as-question marker present: {bad}")
check(
    "verified property" in MAIN_TEX.lower() and "verified property" in MAIN_MD.lower(),
    "'verified property' framing for the enforcement result missing",
)
# RQ2 must be secondary, not co-headline
check(
    "secondary null experiment" in MAIN_TEX.lower()
    and "secondary null experiment" in MAIN_MD.lower(),
    "RQ2 not framed as a secondary null experiment",
)


# --------------------------------------------------------------------------- #
# 6. main.md primary tables reconcile with the machine-generated fragments
# --------------------------------------------------------------------------- #
# per-model contrast summary
def sd3(x: float) -> str:
    if x == 0:
        return "0.000"
    return f"−{abs(x):.3f}" if x < 0 else f"+{x:.3f}"


LAB = {"C_minus_N": "C − N", "P_minus_N": "P − N", "C_minus_P": "C − P"}
for m in PANEL:
    for k in CONTRASTS:
        fc = facts["p7_contrasts"][m][k]
        row = (
            f"| {m} | {LAB[k]} | {sd3(fc['mean'])} | {sd3(fc['median'])} | "
            f"{fc['signs'][0]} / {fc['signs'][1]} / {fc['signs'][2]} |"
        )
        check(row in MAIN_MD, f"main.md contrast-summary row missing/stale: {row}")


# descriptive C-P comparison
def _sig(t: list[int]) -> str:
    return f"{t[0]} / {t[1]} / {t[2]}"


for m in PANEL:
    fc = facts["p6p7_cp"][m]
    row = (
        f"| {m} | {sd3(fc['p6_mean'])} | {_sig(fc['p6_signs'])} "
        f"| {sd3(fc['p7_mean'])} | {_sig(fc['p7_signs'])} | {fc['direction']} |"
    )
    check(row in MAIN_MD, f"main.md C-P comparison row missing/stale: {row}")

# pooled arm rates
for m in PANEL:
    fa = facts["p7_arms"][m]
    row = (
        f"| {m} | {fa['C'][0]}/40 = {fa['C'][1]:.3f} | {fa['N'][0]}/40 = {fa['N'][1]:.3f} "
        f"| {fa['P'][0]}/40 = {fa['P'][1]:.3f} | {fa['cn_treatment']} |"
    )
    check(row in MAIN_MD, f"main.md arm-rate row missing/stale: {row}")

# no bootstrap/CI/p-value language attached to the Phase 7 primary
for banned in [
    "bootstrap",
    "confidence interval",
    "credible interval",
    "p-value",
    "p value",
    "significance test",
    "significant at",
]:
    # allowed only inside an explicit negation ("no bootstrap", "no p-values", ...)
    for label, text in (("main.tex", _flat(MAIN_TEX)), ("main.md", _flat(MAIN_MD))):
        start = 0
        while (i := text.find(banned, start)) != -1:
            ctx = text[max(0, i - 60) : i]
            if not any(n in ctx for n in ("no ", "not ", "without", "never")):
                fails.append(
                    f"{label} attaches inferential-stat term to results: "
                    f"{banned!r} (...{ctx[-40:]})"
                )
            start = i + len(banned)

# --------------------------------------------------------------------------- #
if fails:
    print(f"NUMERIC AUDIT FAILED ({len(fails)} issue(s)):")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print(
    "numeric audit passed: manuscript reconciles with the frozen Phase 7E and Phase 6E.2 artifacts"
)
