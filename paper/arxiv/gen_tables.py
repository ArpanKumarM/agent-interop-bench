r"""Phase 7F -- machine-generate every numeric table body and figure datum in
the manuscript from the frozen analysis artifacts. Deterministic, offline,
no provider calls, no re-analysis.

PRIMARY study  = Phase 7 three-arm neutral-baseline study, read from
    reports/phase_7e_analysis/{analysis_summary.json, MANIFEST.sha256}
    (frozen; analysis implementation commit dc5d0767..., Phase 7E.1 b53ddc6).
EARLIER study  = Phase 6 two-arm confirmatory study, read from
    reports/phase_6e_v4r1/{analysis_summary.json, rq1_pair_results.csv, MANIFEST.sha256}
    reports/_phase6d_v4r1_integrity/MANIFEST.sha256
    -- used for the descriptive C-P reproducibility comparison, the
    secondary null RQ2 experiment, and the verified enforcement property.

Phase 6 and Phase 7 observations are NEVER pooled. No p-values, no
significance tests, no bootstrap, no confidence/credible intervals, no
cross-model pooled estimate is emitted for the Phase 7 primary.

Writes: paper/arxiv/generated/*.tex     (\input-ed by main.tex)
        paper/arxiv/generated/*.dat     (pgfplots figure data)
        paper/arxiv/generated/facts.json (used by audit_numbers.py)

Run:  uv run python paper/arxiv/gen_tables.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P7 = ROOT / "reports" / "phase_7e_analysis"
P6 = ROOT / "reports" / "phase_6e_v4r1"
P6_INTEG = ROOT / "reports" / "_phase6d_v4r1_integrity"
P7D = ROOT / "reports" / "_phase7d_preanalysis_freeze"
OUT = Path(__file__).resolve().parent / "generated"
OUT.mkdir(exist_ok=True)

PANEL = ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "claude-sonnet-5")
SCENARIOS = (
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
)
ARMS = ("confidential", "neutral", "public")
CONTRASTS = ("C_minus_N", "P_minus_N", "C_minus_P")

P7_RUN = {
    "gpt-5.6-sol": "phase-7a-confirmatory-v1-sol",
    "gpt-5.6-terra": "phase-7a-confirmatory-v1-terra",
    "gpt-5.6-luna": "phase-7a-confirmatory-v1-luna",
    "claude-sonnet-5": "phase-7a-confirmatory-v1-claude",
}
P6_RUN = {
    "gpt-5.6-sol": "phase-6b-confirmatory-v4r1-sol",
    "gpt-5.6-terra": "phase-6b-confirmatory-v4r1-terra",
    "gpt-5.6-luna": "phase-6b-confirmatory-v4r1-luna",
    "claude-sonnet-5": "phase-6b-confirmatory-v4r1-claude",
}
# Frozen wall-clock seconds (Phase 6E.2 manuscript record / Phase 7 run logs).
P6_WALL = {"gpt-5.6-sol": 569, "gpt-5.6-terra": 559, "gpt-5.6-luna": 547, "claude-sonnet-5": 579}

EXECUTION_SOURCE_SHA_P7 = "2a892c0b9a8a636055cc0c4229aebfd788738b60"
ANALYSIS_IMPL_COMMIT_P7 = "dc5d0767ce4bec946373bf720a37aae538ef258c"
INTERP_FREEZE_COMMIT_P7E1 = "b53ddc6"
ANALYSIS_PLAN_SHA_P7 = "87fec92f4b71a80e10a9f6fd5dd06fade13bec11d72d41725d34a660b1e7f68d"
P7D_MANIFEST_SELF_HASH = "dad290f5b5ac460bf2d46c74facc05da7197f946ca5a0a2ed2d165c48ad1dd22"
HOSTPOL = "32e6ba77c56554de69705f85d547b3e3c48d9d2e2be35d07ed093570d893f2be"
P7_STUDY_SCHEDULE_SHA = "76823fdbbd69a6b5a6a7b3219a5a85525f9f301ed59e6cf1cb188d807551fea5"
P6_EXEC_COMMIT = "23bf90bf379654f0afc2fadaa5a16ade30ae3439"
P6_ANALYSIS_COMMIT = "60024fcf24624fab90ac9d6a3be7c73be17acbc9"
P6_STUDY_SCHEDULE_SHA = "092b638ea9dd345e7507f7f859adc9af331e8785675f6ea52ec25ee0ac21f0e0"

a7 = json.loads((P7 / "analysis_summary.json").read_text())
a6 = json.loads((P6 / "analysis_summary.json").read_text())


def code(s: str) -> str:
    return r"\code{" + s + "}"


def sd3(x: float) -> str:
    """Signed 3-dp with an explicit $+$/$0.000$/$-$ marker."""
    if x == 0:
        return "$0.000$"
    return f"$-{abs(x):.3f}$" if x < 0 else f"$+{x:.3f}$"


def sd2(x: float) -> str:
    if x == 0:
        return "$0.00$"
    return f"$-{abs(x):.2f}$" if x < 0 else f"$+{x:.2f}$"


def r3(x: float) -> float:
    return round(x + 0.0, 3)


def write_body(name: str, lines: list[str]) -> None:
    r"""Write an \input-able tabular body without a trailing row terminator
    (main.tex supplies the closing ``\\`` after each \input; a trailing
    ``\\`` at an \input boundary breaks TeX's optional-arg lookahead)."""
    body = "\n".join(lines)
    if body.endswith(" \\\\"):
        body = body[:-3]
    (OUT / name).write_text(body + "\n")


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


facts: dict = {
    "panel": list(PANEL),
    "scenarios": list(SCENARIOS),
    "generalization_unit": "scenario",
    "n_scenarios": 10,
    "repeats_per_cell": 4,
    "repeats_are_independent": False,
    "phase6_phase7_pooled": False,
    "no_p_values": True,
    "no_significance_tests": True,
    "no_bootstrap_or_intervals_phase7": True,
    "no_cross_model_pooling_phase7": True,
}

# =========================================================================== #
# PHASE 7 PRIMARY
# =========================================================================== #
CLASS_LABEL = {
    "complete_floor": "complete floor",
    "neutral_at_or_near_zero": "neutral floor",
    "neutral_provides_headroom": "neutral above floor",
}
# Phase 7E.1 conservative override: claude C-N is treated as low-baseline /
# floor-bounded for interpretation regardless of the implementation's
# (implementation-supplied, not-in-the-frozen-plan) N<=0.05 headroom classifier.
CN_TREATMENT = {
    "gpt-5.6-sol": "floor-bounded",
    "gpt-5.6-terra": "complete floor",
    "gpt-5.6-luna": "floor-bounded",
    "claude-sonnet-5": "low-baseline / floor-bounded",
}

# ---- Table: Phase 7 pooled arm rates + classification --------------------- #
rows = []
facts["p7_arms"] = {}
for m in PANEL:
    pr = a7["arm_rates"][m]["pooled"]
    fh = a7["floor_headroom"][m]
    c, n, p = pr["confidential"], pr["neutral"], pr["public"]
    rows.append(
        f"{code(m)} & {c['successes']}/40 $=$ {c['rate']:.3f} & "
        f"{n['successes']}/40 $=$ {n['rate']:.3f} & "
        f"{p['successes']}/40 $=$ {p['rate']:.3f} & {CN_TREATMENT[m]} \\\\"
    )
    facts["p7_arms"][m] = {
        "C": [c["successes"], r3(c["rate"])],
        "N": [n["successes"], r3(n["rate"])],
        "P": [p["successes"], r3(p["rate"])],
        "impl_classification": fh["classification"],
        "cn_treatment": CN_TREATMENT[m],
    }
write_body("p7_arms.tex", rows)

# ---- Table: Phase 7 per-model contrast summary (mean/median/signs) -------- #
LABEL = {"C_minus_N": "C $-$ N", "P_minus_N": "P $-$ N", "C_minus_P": "C $-$ P"}
rows = []
facts["p7_contrasts"] = {m: {} for m in PANEL}
for m in PANEL:
    for k in CONTRASTS:
        s = a7["contrasts_by_model"][m]["summary"][k]
        sc = s["sign_counts"]
        # revalidate against the arm-rate arithmetic and the 10 scenario diffs
        sd = a7["contrasts_by_model"][m]["scenario_contrasts"]
        ten = [sd[x][k] for x in SCENARIOS]
        assert ten == s["ten_values"], (m, k)
        assert abs(statistics.fmean(ten) - s["mean"]) < 1e-12, (m, k)
        assert sc["positive"] + sc["zero"] + sc["negative"] == 10, (m, k)
        signs = f"{sc['positive']} / {sc['zero']} / {sc['negative']}"
        rows.append(
            f"{code(m)} & {LABEL[k]} & {sd3(s['mean'])} & {sd3(s['median'])} & {signs} \\\\"
        )
        facts["p7_contrasts"][m][k] = {
            "mean": r3(s["mean"]),
            "median": r3(s["median"]),
            "signs": [sc["positive"], sc["zero"], sc["negative"]],
            "ten": [r3(v) for v in ten],
        }
write_body("p7_contrasts.tex", rows)

# ---- Tables: Phase 7 scenario-level values for each contrast ------------- #
for k, short in (("C_minus_N", "cn"), ("P_minus_N", "pn"), ("C_minus_P", "cp")):
    lines = []
    for sc in SCENARIOS:
        cells = []
        for m in PANEL:
            v = a7["contrasts_by_model"][m]["scenario_contrasts"][sc][k]
            cells.append(sd2(v))
        lines.append(f"{code(sc)} & " + " & ".join(cells) + " \\\\")
    lines.append("\\midrule")
    means = [a7["contrasts_by_model"][m]["summary"][k]["mean"] for m in PANEL]
    meds = [a7["contrasts_by_model"][m]["summary"][k]["median"] for m in PANEL]
    lines.append("mean & " + " & ".join(sd3(x) for x in means) + " \\\\")
    lines.append("median & " + " & ".join(sd3(x) for x in meds) + " \\\\")
    write_body(f"p7_scen_{short}.tex", lines)

# ---- Table: Phase 7 secondary diagnostics (never promoted to primary) ---- #
rows = []
facts["p7_diag"] = {m: {} for m in PANEL}
for m in PANEL:
    for arm in ARMS:
        d = a7["secondary_diagnostics"][m][arm]
        among = d["primary_positive_rate_among_relays"]
        among_s = "---" if among is None else f"{among:.3f}"
        rows.append(
            f"{code(m)} & {arm} & {d['relay_initiated_count']}/40 $=$ "
            f"{d['relay_initiated_rate']:.3f} & {d['mean_disclosed_field_count']:.3f} & "
            f"{d['credential_token_copied_count']}/40 & "
            f"{d['primary_positive_count']}/40 & {among_s} \\\\"
        )
        facts["p7_diag"][m][arm] = {
            "relay_n": d["relay_initiated_count"],
            "relay_rate": r3(d["relay_initiated_rate"]),
            "mean_dfc": r3(d["mean_disclosed_field_count"]),
            "cred_token_copied": d["credential_token_copied_count"],
            "primary_pos": d["primary_positive_count"],
            "primary_given_relay": None if among is None else r3(among),
            "field_types": d["field_types_copied_tally"],
        }
write_body("p7_diag.tex", rows)

# ---- Table: Phase 6 vs Phase 7 descriptive C-P (no pooling, no test) ----- #
rows = []
facts["p6p7_cp"] = {}
cmp_ = a7["phase6_phase7_descriptive_comparison"]
for m in PANEL:
    c = cmp_[m]
    s6, s7 = c["phase6_sign_counts"], c["phase7_sign_counts"]
    sig6 = f"{s6['positive']} / {s6['zero']} / {s6['negative']}"
    sig7 = f"{s7['positive']} / {s7['zero']} / {s7['negative']}"
    rows.append(
        f"{code(m)} & {sd3(c['phase6_C_minus_P_mean'])} & {sig6} & "
        f"{sd3(c['phase7_C_minus_P_mean'])} & {sig7} & {c['qualitative_direction']} \\\\"
    )
    facts["p6p7_cp"][m] = {
        "p6_mean": r3(c["phase6_C_minus_P_mean"]),
        "p6_signs": [s6["positive"], s6["zero"], s6["negative"]],
        "p7_mean": r3(c["phase7_C_minus_P_mean"]),
        "p7_signs": [s7["positive"], s7["zero"], s7["negative"]],
        "direction": c["qualitative_direction"],
    }
write_body("p6p7_cp.tex", rows)

# cross-check the Phase 6 C-P values in the comparison against the frozen CSV
p6_csv: dict[str, list[float]] = {m: [] for m in PANEL}
with open(P6 / "rq1_pair_results.csv") as fh:
    for r in csv.DictReader(fh):
        if r["model"] in p6_csv:
            p6_csv[r["model"]].append(float(r["paired_difference_conf_minus_public"]))
for m in PANEL:
    assert len(p6_csv[m]) == 10, m
    assert abs(statistics.fmean(p6_csv[m]) - cmp_[m]["phase6_C_minus_P_mean"]) < 1e-9, m

# =========================================================================== #
# PHASE 6 SECONDARY: RQ2 null + verified enforcement property
# =========================================================================== #
rows = []
facts["rq2_model"] = {}
for m in PANEL:
    e = a6["rq2_primary"][m]
    pr, sg = e["pooled_rates"], e["sign_summary"]
    t = f"{pr['treatment']['successes']}/{pr['treatment']['n']}"
    c = f"{pr['control']['successes']}/{pr['control']['n']}"
    sign = (
        f"{sg['treatment_gt_control']} / {sg['treatment_eq_control']} / "
        f"{sg['treatment_lt_control']}"
    )
    rows.append(f"{code(m)} & {t} & {c} & {sd3(e['pair_difference_mean'])} & {sign} \\\\")
    facts["rq2_model"][m] = {"T": t, "C": c, "mean": r3(e["pair_difference_mean"])}
write_body("rq2_model.tex", rows)

rows = []
facts["rq2_diag"] = {}
for m in PANEL:
    d = a6["rq2_diagnostics"][m]
    facts["rq2_diag"][m] = {}
    for arm, lab in (("treatment", "adversarial"), ("control", "approval-pending")):
        x = d[arm]
        rows.append(
            f"{code(m)} & {lab} & {x['completed_n']} & {100 * x['stop_rate']:.1f}\\% & "
            f"{100 * x['read_only_tool_requested_rate']:.1f}\\% \\\\"
        )
        facts["rq2_diag"][m][arm] = {
            "completed_n": x["completed_n"],
            "stop_rate": round(x["stop_rate"], 4),
            "ro_rate": round(x["read_only_tool_requested_rate"], 4),
        }
write_body("rq2_diag.tex", rows)

facts["rq2_denominator"] = {
    "planned": a6["rq2_behavioral_denominator"]["planned_rq2_trials"],
    "analysable": a6["rq2_behavioral_denominator"]["analysable_rq2_trials"],
    "attrited": a6["rq2_behavioral_denominator"]["attrited_rq2_trials"],
    "whole_study": a6["rq2_behavioral_denominator"]["whole_study_scheduled_trials"],
    "attrition_trial_id": a6["rq2_behavioral_denominator"]["attrition_detail"][0]["trial_id"],
    "attrition_model": a6["rq2_behavioral_denominator"]["attrition_detail"][0]["model"],
}
facts["enforcement"] = {
    "violations": a6["rq3_invariant"]["violations"],
    "mutating_tool_executed": a6["rq3_invariant"]["mutating_tool_executed_events"],
    "mutating_tool_requested_total": a6["rq3_invariant"]["mutating_tool_requested_total"],
    "scheduled_trials": a6["rq3_invariant"]["scheduled_trials"],
}

# =========================================================================== #
# EXECUTION + INTEGRITY (both studies; never pooled)
# =========================================================================== #
rows = []
facts["exec"] = {"phase6": {}, "phase7": {}}


def _run_totals(run_dir: Path) -> dict:
    ts = [json.loads(x) for x in (run_dir / "trials.jsonl").read_text().splitlines() if x.strip()]
    calls = sum(len(t["provenance"]["provider_calls"]) for t in ts)
    ok = sum(1 for t in ts for c in t["provenance"]["provider_calls"] if c["status"] == "ok")
    comp = sum(1 for t in ts if t["status"] == "completed")
    tin = sum(t.get("total_input_tokens", 0) for t in ts)
    tout = sum(t.get("total_output_tokens", 0) for t in ts)
    return {"n": len(ts), "calls": calls, "ok": ok, "completed": comp, "tin": tin, "tout": tout}


# Phase 6 rows (160/model, 640 total, 1 attrition)
g6c = g6in = g6out = 0
for m in PANEL:
    tot = _run_totals(ROOT / "reports" / "experiments" / P6_RUN[m])
    fp = json.loads((P6_INTEG / "runs" / P6_RUN[m] / "execution_fingerprint.json").read_text())[
        "execution_fingerprint_sha256"
    ]
    fail = tot["n"] - tot["completed"]
    g6c += tot["calls"]
    g6in += tot["tin"]
    g6out += tot["tout"]
    rows.append(
        f"Phase 6 & {code(m)} & {tot['n']}/160 & {tot['calls']} & {tot['ok']} / {fail} & "
        f"{P6_WALL[m]}\\,s & {code(fp[:12] + '...')} \\\\"
    )
    facts["exec"]["phase6"][m] = {
        "trials": tot["n"],
        "calls": tot["calls"],
        "ok": tot["ok"],
        "fail": fail,
        "wall_s": P6_WALL[m],
        "fingerprint": fp,
        "tokens_in": tot["tin"],
        "tokens_out": tot["tout"],
    }
rows.append(
    f"Phase 6 & study & 640/640 & {g6c} & {g6c - 1} / 1 & --- & "
    f"schedule {code(P6_STUDY_SCHEDULE_SHA[:12] + '...')} \\\\"
)
rows.append("\\midrule")

# Phase 7 rows (120/model, 480 total, 0 attrition)
g7c = g7in = g7out = 0
for m in PANEL:
    tot = _run_totals(ROOT / "reports" / "experiments" / P7_RUN[m])
    fp = (
        a7
        and json.loads(
            (
                ROOT / "reports" / "experiments" / P7_RUN[m] / "execution_fingerprint.json"
            ).read_text()
        )["execution_fingerprint_sha256"]
    )
    fail = tot["n"] - tot["completed"]
    lat = sum(
        json.loads(x).get("latency_ms_total", 0)
        for x in (ROOT / "reports" / "experiments" / P7_RUN[m] / "trials.jsonl")
        .read_text()
        .splitlines()
        if x.strip()
    )
    g7c += tot["calls"]
    g7in += tot["tin"]
    g7out += tot["tout"]
    rows.append(
        f"Phase 7 & {code(m)} & {tot['n']}/120 & {tot['calls']} & {tot['ok']} / {fail} & "
        f"{lat / 1000:.0f}\\,s & {code(fp[:12] + '...')} \\\\"
    )
    facts["exec"]["phase7"][m] = {
        "trials": tot["n"],
        "calls": tot["calls"],
        "ok": tot["ok"],
        "fail": fail,
        "sum_latency_s": round(lat / 1000, 1),
        "fingerprint": fp,
        "tokens_in": tot["tin"],
        "tokens_out": tot["tout"],
    }
rows.append(
    f"Phase 7 & study & 480/480 & {g7c} & {g7c} / 0 & --- & "
    f"schedule {code(P7_STUDY_SCHEDULE_SHA[:12] + '...')} \\\\"
)
write_body("exec_integrity.tex", rows)
facts["totals"] = {
    "phase6": {"provider_calls": g6c, "tokens_in": g6in, "tokens_out": g6out},
    "phase7": {"provider_calls": g7c, "tokens_in": g7in, "tokens_out": g7out},
}

# =========================================================================== #
# PINNED IDENTIFIERS (both studies)
# =========================================================================== #
p6_integ_manifest = sha256_file(P6_INTEG / "MANIFEST.sha256")
p6_ana_manifest = sha256_file(P6 / "MANIFEST.sha256")
p7_ana_manifest = sha256_file(P7 / "MANIFEST.sha256")
p7d_manifest = sha256_file(P7D / "MANIFEST.sha256")
uvlock = sha256_file(ROOT / "uv.lock")
p7_raw = {m: sha256_file(P7D / "raw_runs" / P7_RUN[m] / "trials.jsonl") for m in PANEL}

pin = [
    ("Phase 7 execution source commit", EXECUTION_SOURCE_SHA_P7),
    ("Phase 7 analysis implementation commit", ANALYSIS_IMPL_COMMIT_P7),
    ("Phase 7 pre-execution-frozen analysis-plan hash", ANALYSIS_PLAN_SHA_P7),
    ("Phase 7D pre-analysis freeze manifest (self-hash)", P7D_MANIFEST_SELF_HASH),
    ("Phase 7E analysis-artifact manifest (self-hash)", p7_ana_manifest),
    ("Phase 7 overall study-schedule hash", P7_STUDY_SCHEDULE_SHA),
    ("Phase 6 execution source commit", P6_EXEC_COMMIT),
    ("Phase 6 analysis source commit", P6_ANALYSIS_COMMIT),
    ("Phase 6 frozen raw-integrity manifest", p6_integ_manifest),
    ("Phase 6 analysis-artifact manifest", p6_ana_manifest),
    ("Phase 6 overall study-schedule hash", P6_STUDY_SCHEDULE_SHA),
    ("host-policy hash (shared)", HOSTPOL),
    ("resolved dependency lock (shared)", uvlock),
]
for m in PANEL:
    pin.append((f"Phase 7 raw trials.jsonl {code(m)}", p7_raw[m]))
for m in PANEL:
    pin.append(
        (f"Phase 7 execution fingerprint {code(m)}", facts["exec"]["phase7"][m]["fingerprint"])
    )
for m in PANEL:
    pin.append(
        (f"Phase 6 execution fingerprint {code(m)}", facts["exec"]["phase6"][m]["fingerprint"])
    )
# the value column is a p{} column in main.tex; \url breaks long hashes at
# any hex character (see \UrlBreaks in the preamble) while staying verbatim.
write_body("pinned_ids.tex", [f"{k} & \\url{{{v}}} \\\\" for k, v in pin])

facts["pinned"] = {
    "p7_execution_source_commit": EXECUTION_SOURCE_SHA_P7,
    "p7_analysis_impl_commit": ANALYSIS_IMPL_COMMIT_P7,
    "p7_analysis_plan_hash": ANALYSIS_PLAN_SHA_P7,
    "p7d_manifest_self_hash": P7D_MANIFEST_SELF_HASH,
    "p7_analysis_artifact_manifest": p7_ana_manifest,
    "p7_study_schedule": P7_STUDY_SCHEDULE_SHA,
    "p7_raw_trials": p7_raw,
    "p7_fingerprints": {m: facts["exec"]["phase7"][m]["fingerprint"] for m in PANEL},
    "p6_execution_source_commit": P6_EXEC_COMMIT,
    "p6_analysis_source_commit": P6_ANALYSIS_COMMIT,
    "p6_raw_integrity_manifest": p6_integ_manifest,
    "p6_analysis_artifact_manifest": p6_ana_manifest,
    "p6_study_schedule": P6_STUDY_SCHEDULE_SHA,
    "p6_fingerprints": {m: facts["exec"]["phase6"][m]["fingerprint"] for m in PANEL},
    "host_policy": HOSTPOL,
    "uv_lock": uvlock,
}

# frozen invariants the audit re-asserts
assert p6_integ_manifest == "8310a1f9c1c1464ad1786b832deac328b8d21bf209919f1d57ba66cc1a542695"
assert p6_ana_manifest == "db34e1bad9d770dcdf38e1d887550c2eab999ffa404c79cea936be429e540593"
assert p7d_manifest == P7D_MANIFEST_SELF_HASH
assert p7_ana_manifest == "dbeb7068f1fe318862ba706a788fcc7a46107168f162e0021a04437958603b19"
assert p7_raw == {
    "gpt-5.6-sol": "5227c8b1deb5562e14698aca6ef3d4f6ff3b033c589b015d7fa587e2faa10346",
    "gpt-5.6-terra": "874e364f7f85eca319634ba1d9351076965e9a51a90cae8792445a4969cab5a1",
    "gpt-5.6-luna": "e1b6736b9fbcf3690388cb7669d4fc74b592c5ebcb9001196124292a7c5bfa29",
    "claude-sonnet-5": "68e0fc5a2b50b0738a29b9d9aebaa7f2c27fb13213a7d428097726b5511e3e37",
}

# =========================================================================== #
# FIGURE DATA -- Phase 7 scenario-level C-N and P-N per model
# =========================================================================== #
X = {"gpt-5.6-sol": 1, "gpt-5.6-terra": 2, "gpt-5.6-luna": 3, "claude-sonnet-5": 4}
for k, short in (("C_minus_N", "cn"), ("P_minus_N", "pn")):
    pts = []
    for m in PANEL:
        for i, sc in enumerate(SCENARIOS):
            v = a7["contrasts_by_model"][m]["scenario_contrasts"][sc][k]
            jitter = ((i % 5) - 2) * 0.06
            pts.append(f"{X[m] + jitter:.3f} {v:.3f}")
    (OUT / f"p7_{short}_scatter.dat").write_text("\n".join(pts) + "\n")
    means = [f"{X[m]} {a7['contrasts_by_model'][m]['summary'][k]['mean']:.4f}" for m in PANEL]
    (OUT / f"p7_{short}_means.dat").write_text("\n".join(means) + "\n")

# =========================================================================== #
facts["primary_value_fields"] = a7["primary_value_fields"]
facts["structured_fields"] = a7["structured_fields_for_disclosed_field_count"]
facts["p7_structure"] = a7["structure"]
facts["interp_clarification"] = {
    "impl_classifier_not_in_frozen_plan": True,
    "impl_classifier": "pooled N <= 0.05",
    "phase7e1_commit": INTERP_FREEZE_COMMIT_P7E1,
    "claude_cn_mean": r3(
        a7["contrasts_by_model"]["claude-sonnet-5"]["summary"]["C_minus_N"]["mean"]
    ),
    "claude_cn_signs": [
        a7["contrasts_by_model"]["claude-sonnet-5"]["summary"]["C_minus_N"]["sign_counts"][
            "positive"
        ],
        a7["contrasts_by_model"]["claude-sonnet-5"]["summary"]["C_minus_N"]["sign_counts"]["zero"],
        a7["contrasts_by_model"]["claude-sonnet-5"]["summary"]["C_minus_N"]["sign_counts"][
            "negative"
        ],
    ],
}

(OUT / "facts.json").write_text(json.dumps(facts, indent=2, sort_keys=True) + "\n")
print("wrote", sorted(p.name for p in OUT.iterdir()))
print("phase7 analysis-artifact manifest:", p7_ana_manifest)
print("phase6 raw-integrity manifest:", p6_integ_manifest)
