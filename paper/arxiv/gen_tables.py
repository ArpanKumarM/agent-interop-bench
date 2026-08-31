r"""Phase 6F.2 -- machine-generate every numeric table body in the manuscript
from the frozen Phase 6E.2 analysis artifacts. Deterministic, offline, no
provider calls, no re-analysis.

Reads:  reports/phase_6e_v4r1/{analysis_summary.json, rq1_pair_results.csv}
        reports/_phase6d_v4r1_integrity/runs/<run>/execution_fingerprint.json
        scratch run logs for per-model wall time (optional; falls back to '--')
Writes: paper/arxiv/generated/*.tex     (\input-ed by main.tex)
        paper/arxiv/generated/facts.json (used by the numeric audit)

Run:  uv run python paper/arxiv/gen_tables.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "reports" / "phase_6e_v4r1"
INTEG = ROOT / "reports" / "_phase6d_v4r1_integrity"
OUT = Path(__file__).resolve().parent / "generated"
OUT.mkdir(exist_ok=True)

PANEL = ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "claude-sonnet-5")
RUN = {
    "gpt-5.6-sol": "phase-6b-confirmatory-v4r1-sol",
    "gpt-5.6-terra": "phase-6b-confirmatory-v4r1-terra",
    "gpt-5.6-luna": "phase-6b-confirmatory-v4r1-luna",
    "claude-sonnet-5": "phase-6b-confirmatory-v4r1-claude",
}
WALL = {"gpt-5.6-sol": 569, "gpt-5.6-terra": 559, "gpt-5.6-luna": 547, "claude-sonnet-5": 579}

a = json.loads((ANALYSIS / "analysis_summary.json").read_text())


def code(s: str) -> str:
    return r"\code{" + s + "}"


def sf3(x: float | None) -> str:
    if x is None:
        return "---"
    return f"$-{abs(x):.3f}$" if x < 0 else ("$0.000$" if x == 0 else f"$+{x:.3f}$")


def f3(x: float | None) -> str:
    return "---" if x is None else f"{x:.3f}"


def pct(x: float | None) -> str:
    return "---" if x is None else f"{100 * x:.1f}\\%"


def signstr(sg: dict) -> str:
    return (
        f"{sg['treatment_gt_control']} / {sg['treatment_eq_control']} / "
        f"{sg['treatment_lt_control']}"
    )


def _b(x: float) -> str:
    return f"{x:.3f}" if x < 0 else f"\\phantom{{-}}{x:.3f}"


def bootstr(b: dict) -> str:
    return f"$[{_b(b['ci_low'])},\\ {_b(b['ci_high'])}]$"


def write_body(name: str, lines: list[str]) -> None:
    r"""Write an \input-able tabular body.

    The final row is emitted WITHOUT a trailing ``\\`` row terminator: a
    ``\\`` at the very end of an \input-ed file corrupts TeX's optional-arg
    lookahead across the file boundary and makes the following ``\bottomrule``
    raise "Misplaced \noalign". main.tex supplies the closing ``\\`` after
    each \input.
    """
    body = "\n".join(lines)
    if body.endswith(" \\\\"):
        body = body[:-3]
    (OUT / name).write_text(body + "\n")


facts: dict = {"panel": list(PANEL)}

# --------------------------------------------------------------------------- #
# Table: RQ1 model summary (any_sensitive_field_egress)
# --------------------------------------------------------------------------- #
rows = []
facts["rq1_model"] = {}
for m in PANEL:
    e = a["rq1_primary"][m]
    pr, sg, b = e["pooled_rates"], e["sign_summary"], e["pair_bootstrap"]
    t = f"{pr['treatment']['successes']}/{pr['treatment']['n']}"
    c = f"{pr['control']['successes']}/{pr['control']['n']}"
    sign = signstr(sg)
    boot = bootstr(b)
    rows.append(
        f"{code(m)} & {t} & {c} & {sf3(e['pair_difference_mean'])} & "
        f"{sf3(e['pair_difference_median'])} & {sign} & {boot} \\\\"
    )
    facts["rq1_model"][m] = {
        "T": t,
        "C": c,
        "mean": round(e["pair_difference_mean"], 3),
        "median": round(e["pair_difference_median"], 3),
        "sign": sign,
        "boot": [round(b["ci_low"], 3), round(b["ci_high"], 3)],
    }
write_body("rq1_model.tex", rows)

# --------------------------------------------------------------------------- #
# Table: RQ1 pair-level differences (fixed pair order = design persona order)
# --------------------------------------------------------------------------- #
PAIR_ORDER = [
    "saas-support",
    "healthcare-billing",
    "finance-kyc",
    "employee-directory",
    "logistics-shipment",
    "telecom-subscriber",
    "education-learner",
    "payroll-employer",
    "gaming-player",
    "procurement-vendor",
]
by = {m: {} for m in PANEL}
with open(ANALYSIS / "rq1_pair_results.csv") as fh:
    for r in csv.DictReader(fh):
        by[r["model"]][r["pair_id"]] = float(r["paired_difference_conf_minus_public"])
assert set(PAIR_ORDER) == set(next(iter(by.values())).keys())
lines = []
facts["rq1_pairs"] = {m: {} for m in PANEL}
for p in PAIR_ORDER:
    cells = []
    for m in PANEL:
        v = by[m][p]
        cells.append("$0.00$" if v == 0 else f"$-{abs(v):.2f}$")
        facts["rq1_pairs"][m][p] = round(v, 2)
    lines.append(f"{code(p)} & " + " & ".join(cells) + " \\\\")
lines.append("\\midrule")
means = []
meds = []
for m in PANEL:
    vals = [by[m][p] for p in PAIR_ORDER]
    means.append(statistics.fmean(vals))
    meds.append(statistics.median(vals))
lines.append("mean & " + " & ".join(sf3(x) for x in means) + " \\\\")
lines.append("median & " + " & ".join(sf3(x) for x in meds) + " \\\\")
write_body("rq1_pairs.tex", lines)
# cross-check pair means == model-summary means
for m, mm in zip(PANEL, means, strict=True):
    assert abs(mm - a["rq1_primary"][m]["pair_difference_mean"]) < 1e-9, m

# --------------------------------------------------------------------------- #
# Table: RQ2 model summary (mutating_tool_requested -- all zero)
# --------------------------------------------------------------------------- #
rows = []
facts["rq2_model"] = {}
for m in PANEL:
    e = a["rq2_primary"][m]
    pr, sg = e["pooled_rates"], e["sign_summary"]
    t = f"{pr['treatment']['successes']}/{pr['treatment']['n']}"
    c = f"{pr['control']['successes']}/{pr['control']['n']}"
    sign = signstr(sg)
    rows.append(f"{code(m)} & {t} & {c} & {sf3(e['pair_difference_mean'])} & {sign} \\\\")
    facts["rq2_model"][m] = {"T": t, "C": c, "mean": round(e["pair_difference_mean"], 3)}
write_body("rq2_model.tex", rows)

# --------------------------------------------------------------------------- #
# Table: RQ2 behavioral diagnostics (pooled, exploratory)
# --------------------------------------------------------------------------- #
rows = []
facts["rq2_diag"] = {}
for m in PANEL:
    d = a["rq2_diagnostics"][m]
    facts["rq2_diag"][m] = {}
    for arm, label in (("treatment", "adversarial"), ("control", "approval-pending")):
        x = d[arm]
        rows.append(
            f"{code(m)} & {label} & {x['completed_n']} & {pct(x['stop_rate'])} & "
            f"{pct(x['read_only_tool_requested_rate'])} \\\\"
        )
        facts["rq2_diag"][m][arm] = {
            "completed_n": x["completed_n"],
            "stop_rate": round(x["stop_rate"], 4),
            "ro_rate": round(x["read_only_tool_requested_rate"], 4),
        }
write_body("rq2_diag.tex", rows)

# --------------------------------------------------------------------------- #
# Table: RQ1 relay-conditional diagnostics (A = mean count 0-5, B = rate)
# --------------------------------------------------------------------------- #
rows = []
facts["rq1_diag"] = {}
for m in PANEL:
    rd = a["rq1_diagnostics"][m]
    facts["rq1_diag"][m] = {}
    for arm, label in (("treatment", "confidential"), ("control", "public")):
        x = rd[arm]
        nrel = x["relay_trials_n"]
        bnum = x["primary_positive_relay_trials_n"]
        brate = x["primary_sensitive_egress_rate_among_relay_trials"]
        assert x["relay_initiated"] == nrel, (m, arm)
        rows.append(
            f"{code(m)} & {label} & {nrel} & "
            f"{f3(x['mean_disclosed_field_count_among_relay_trials'])} & "
            f"{bnum}/{nrel}" + ("" if nrel == 0 else f" $=$ {brate:.3f}") + " \\\\"
        )
        facts["rq1_diag"][m][arm] = {
            "relay": x["relay_initiated"],
            "relay_trials_n": nrel,
            "A_mean_dfc_relay": None
            if x["mean_disclosed_field_count_among_relay_trials"] is None
            else round(x["mean_disclosed_field_count_among_relay_trials"], 3),
            "B_primary_pos_relays": bnum,
            "B_rate": None if brate is None else round(brate, 3),
            "canary": x["canary_copied"],
            "header": x["header_label_copied"],
            "full_record": x["full_record_copied"],
            "credential_token": x["credential_token_copied"],
        }
write_body("rq1_diag.tex", rows)

# --------------------------------------------------------------------------- #
# Table: execution + integrity summary
# --------------------------------------------------------------------------- #
rows = []
facts["exec"] = {}
grand_calls = 0
grand_in = grand_out = 0
for m in PANEL:
    d = ROOT / "reports" / "experiments" / RUN[m]
    trials = [json.loads(x) for x in (d / "trials.jsonl").read_text().splitlines() if x.strip()]
    calls = sum(len(t["provenance"]["provider_calls"]) for t in trials)
    ok = sum(1 for t in trials for c in t["provenance"]["provider_calls"] if c["status"] == "ok")
    fail = len(trials) - sum(1 for t in trials if t["status"] == "completed")
    fp = json.loads((INTEG / "runs" / RUN[m] / "execution_fingerprint.json").read_text())[
        "execution_fingerprint_sha256"
    ]
    tin = sum(t["total_input_tokens"] for t in trials)
    tout = sum(t["total_output_tokens"] for t in trials)
    grand_calls += calls
    grand_in += tin
    grand_out += tout
    rows.append(
        f"{code(m)} & {len(trials)}/160 & {calls} & {ok} / {fail} & "
        f"{WALL[m]}\\,s & {code(fp[:12] + '...')} \\\\"
    )
    facts["exec"][m] = {
        "trials": len(trials),
        "calls": calls,
        "ok": ok,
        "fail": fail,
        "wall_s": WALL[m],
        "fingerprint": fp,
        "tokens_in": tin,
        "tokens_out": tout,
    }
sched = "092b638ea9dd345e7507f7f859adc9af331e8785675f6ea52ec25ee0ac21f0e0"
rows.append("\\midrule")
rows.append(
    f"study & 640/640 & {grand_calls} & {640 - 1} / 1 & --- & "
    f"schedule {code(sched[:12] + '...')} \\\\"
)
write_body("exec_integrity.tex", rows)
facts["totals"] = {
    "provider_calls": grand_calls,
    "tokens_in": grand_in,
    "tokens_out": grand_out,
    "wall_min_s": min(WALL.values()),
    "wall_max_s": max(WALL.values()),
}

# --------------------------------------------------------------------------- #
# Table: pinned identifiers
# --------------------------------------------------------------------------- #
SCHED = {
    "gpt-5.6-sol": "11f2c0780491d8048e19d502fabef25f23ef0335b118627c3cc6bea1775332b6",
    "gpt-5.6-terra": "41dbede5faa1728a8559a8324e6c3cda35cce1c6b9f0f3c740ece6d179f9920b",
    "gpt-5.6-luna": "c653e2bf8b3f2ba320dd754d12f755c2705d9ef988e8a9a469e812eaa4e6a83c",
    "claude-sonnet-5": "191c6ff890c185d933d097885f2b9bfa7899c2835373375b00729c86a1345228",
}
integ_manifest = hashlib.sha256((INTEG / "MANIFEST.sha256").read_bytes()).hexdigest()
ana_manifest = hashlib.sha256((ANALYSIS / "MANIFEST.sha256").read_bytes()).hexdigest()
EXEC_COMMIT = "23bf90bf379654f0afc2fadaa5a16ade30ae3439"
ANA_COMMIT = a["execution_commit"]  # sanity
UVLOCK = hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest()
HOSTPOL = "32e6ba77c56554de69705f85d547b3e3c48d9d2e2be35d07ed093570d893f2be"
ANALYSIS_COMMIT = "60024fcf24624fab90ac9d6a3be7c73be17acbc9"  # Phase 6E.2 (analysis frozen)
pin = [
    ("execution source commit", EXEC_COMMIT),
    ("analysis source commit", ANALYSIS_COMMIT),
    ("resolved dependency lock", UVLOCK),
    ("frozen raw-integrity manifest", integ_manifest),
    ("final analysis-artifact manifest", ana_manifest),
    ("host-policy hash", HOSTPOL),
    ("overall study-schedule hash", sched),
]
for m in PANEL:
    pin.append((f"fingerprint {code(m)}", facts["exec"][m]["fingerprint"]))
for m in PANEL:
    pin.append((f"schedule {code(m)}", SCHED[m]))
lines = []
for k, v in pin:
    lines.append(f"{k} & {'' if v is None else code(v)} \\\\")
write_body("pinned_ids.tex", lines)
facts["pinned"] = {
    "execution_source_commit": EXEC_COMMIT,
    "raw_integrity_manifest": integ_manifest,
    "analysis_artifact_manifest": ana_manifest,
    "uv_lock": UVLOCK,
    "host_policy": HOSTPOL,
    "study_schedule": sched,
    "schedule": SCHED,
    "fingerprints": {m: facts["exec"][m]["fingerprint"] for m in PANEL},
}
assert integ_manifest == "8310a1f9c1c1464ad1786b832deac328b8d21bf209919f1d57ba66cc1a542695"

# --------------------------------------------------------------------------- #
# pgfplots data for the per-model matched-pair effect plot
# --------------------------------------------------------------------------- #
plot_lines = []
X = {"gpt-5.6-sol": 1, "gpt-5.6-terra": 2, "gpt-5.6-luna": 3, "claude-sonnet-5": 4}
for m in PANEL:
    for i, p in enumerate(PAIR_ORDER):
        v = by[m][p]
        jitter = ((i % 5) - 2) * 0.06
        plot_lines.append(f"{X[m] + jitter:.3f} {v:.3f}")
(OUT / "rq1_pair_scatter.dat").write_text("\n".join(plot_lines) + "\n")
mean_lines = [f"{X[m]} {a['rq1_primary'][m]['pair_difference_mean']:.4f}" for m in PANEL]
(OUT / "rq1_pair_means.dat").write_text("\n".join(mean_lines) + "\n")

facts["rq2_denominator"] = {
    "planned": a["rq2_behavioral_denominator"]["planned_rq2_trials"],
    "analysable": a["rq2_behavioral_denominator"]["analysable_rq2_trials"],
    "attrited": a["rq2_behavioral_denominator"]["attrited_rq2_trials"],
    "whole_study": a["rq2_behavioral_denominator"]["whole_study_scheduled_trials"],
    "attrition_trial_id": a["rq2_behavioral_denominator"]["attrition_detail"][0]["trial_id"],
    "attrition_model": a["rq2_behavioral_denominator"]["attrition_detail"][0]["model"],
}
facts["rq3"] = {
    "violations": a["rq3_invariant"]["violations"],
    "mutating_tool_executed": a["rq3_invariant"]["mutating_tool_executed_events"],
    "mutating_tool_requested_total": a["rq3_invariant"]["mutating_tool_requested_total"],
    "scheduled_trials": a["rq3_invariant"]["scheduled_trials"],
}
facts["structured_fields"] = a["structured_fields"]
facts["primary_value_fields"] = a["primary_value_fields"]

(OUT / "facts.json").write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
print("wrote", sorted(p.name for p in OUT.iterdir()))
print("integrity manifest:", integ_manifest)
print("analysis manifest:", ana_manifest)
