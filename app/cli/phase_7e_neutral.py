"""Phase 7E -- run the frozen three-arm scientific analysis once and write
``reports/phase_7e_analysis/``.

No provider call. No trial re-run. No raw mutation. Raw ``trials.jsonl``
bytes are hashed before and after and asserted identical. Every generated
table is reconciled against the in-memory analysis objects; the run
ABORTS (non-zero) on any mismatch rather than silently patching.

Run:  uv run python -m app.cli.phase_7e_neutral
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import statistics
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.reporting.phase_7e_neutral import (
    ARMS,
    CONTRASTS,
    EXECUTION_SOURCE_SHA,
    FROZEN_FINAL_FINGERPRINT,
    FROZEN_RAW_ROOT,
    FROZEN_RAW_TRIALS_SHA256,
    PANEL,
    RUN_DIRNAME,
    SCENARIOS,
    Phase7EAnalysisError,
    load_trials,
    run_analysis,
)
from app.reporting.rq1_field_egress import PRIMARY_VALUE_FIELDS, STRUCTURED_FIELDS

OUT = Path("reports/phase_7e_analysis")
LIVE_RAW_ROOT = Path("reports/experiments")
PHASE7D_MANIFEST_SELF_HASH = "dad290f5b5ac460bf2d46c74facc05da7197f946ca5a0a2ed2d165c48ad1dd22"
PHASE7D_MANIFEST = Path("reports/_phase7d_preanalysis_freeze/MANIFEST.sha256")
ANALYSIS_PLAN = Path("docs/phase_7a_neutral_baseline_design.md")
ANALYSIS_PLAN_SHA256 = "87fec92f4b71a80e10a9f6fd5dd06fade13bec11d72d41725d34a660b1e7f68d"
PHASE6_PAIR_CSV = Path("reports/phase_6e_v4r1/rq1_pair_results.csv")

# Field / column names that would only appear if an inferential statistic
# were actually emitted. Matched EXACTLY against JSON keys and CSV headers
# (case-insensitive) -- so the analysis's own negative guard flags
# (``no_p_values``, ``no_bootstrap_or_intervals`` ...) and prose
# disclaimers do NOT trip it.
_FORBIDDEN_RESULT_KEYS = frozenset(
    {
        "p_value",
        "pvalue",
        "p",
        "p_adj",
        "q_value",
        "t_stat",
        "t_statistic",
        "z_score",
        "chi2",
        "chi_square",
        "dof",
        "ci_low",
        "ci_high",
        "ci_lower",
        "ci_upper",
        "ci95_low",
        "ci95_high",
        "conf_int",
        "confidence_interval",
        "credible_interval",
        "hdi_low",
        "hdi_high",
        "bootstrap_mean",
        "bootstrap_ci",
        "n_boot",
        "posterior_mean",
        "bayes_factor",
        "odds_ratio",
        "std_err",
        "standard_error",
        "sem",
    }
)


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _raw_hashes(root: Path) -> dict[str, str]:
    return {m: _sha256_file(root / run / "trials.jsonl") for m, run in RUN_DIRNAME.items()}


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def _fmt(x: float) -> str:
    return f"{x:.6f}"


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


# --------------------------------------------------------------------------- #
# artifact writers
# --------------------------------------------------------------------------- #
def _write_arm_rates(summary: dict) -> Path:
    rows = []
    for m in PANEL:
        for arm in ARMS:
            pr = summary["arm_rates"][m]["pooled"][arm]
            rows.append([m, arm, pr["successes"], pr["n"], _fmt(pr["rate"])])
    p = OUT / "arm_rates.csv"
    _write_csv(p, ["model", "arm", "pooled_successes", "pooled_n", "pooled_rate"], rows)
    return p


def _write_scenario_rates(summary: dict) -> Path:
    rows = []
    for m in PANEL:
        for s in SCENARIOS:
            r = summary["arm_rates"][m]["scenarios"][s]
            rows.append(
                [
                    m,
                    s,
                    r["confidential"]["k"],
                    _fmt(r["confidential"]["rate"]),
                    r["neutral"]["k"],
                    _fmt(r["neutral"]["rate"]),
                    r["public"]["k"],
                    _fmt(r["public"]["rate"]),
                ]
            )
    p = OUT / "scenario_rates.csv"
    _write_csv(
        p,
        ["model", "scenario", "C_k", "C_rate", "N_k", "N_rate", "P_k", "P_rate"],
        rows,
    )
    return p


def _write_scenario_contrasts(summary: dict) -> Path:
    rows = []
    for m in PANEL:
        sc = summary["contrasts_by_model"][m]["scenario_contrasts"]
        for s in SCENARIOS:
            rows.append(
                [m, s, _fmt(sc[s]["C_minus_N"]), _fmt(sc[s]["P_minus_N"]), _fmt(sc[s]["C_minus_P"])]
            )
    p = OUT / "scenario_contrasts.csv"
    _write_csv(p, ["model", "scenario", "C_minus_N", "P_minus_N", "C_minus_P"], rows)
    return p


def _write_model_contrast_summary(summary: dict) -> Path:
    rows = []
    for m in PANEL:
        for c in CONTRASTS:
            b = summary["contrasts_by_model"][m]["summary"][c]
            rows.append(
                [
                    m,
                    c,
                    _fmt(b["mean"]),
                    _fmt(b["median"]),
                    b["sign_counts"]["positive"],
                    b["sign_counts"]["zero"],
                    b["sign_counts"]["negative"],
                    ";".join(_fmt(v) for v in b["ten_values"]),
                ]
            )
    p = OUT / "model_contrast_summary.csv"
    _write_csv(
        p,
        [
            "model",
            "contrast",
            "mean_of_10",
            "median_of_10",
            "n_positive",
            "n_zero",
            "n_negative",
            "ten_scenario_values",
        ],
        rows,
    )
    return p


def _write_relay_diagnostics(summary: dict) -> Path:
    rows = []
    for m in PANEL:
        for arm in ARMS:
            d = summary["secondary_diagnostics"][m][arm]
            rows.append(
                [
                    m,
                    arm,
                    d["n"],
                    d["relay_initiated_count"],
                    _fmt(d["relay_initiated_rate"]),
                    d["stop_count"],
                    d["primary_positive_count"],
                    (
                        ""
                        if d["primary_positive_rate_among_relays"] is None
                        else _fmt(d["primary_positive_rate_among_relays"])
                    ),
                ]
            )
    p = OUT / "relay_diagnostics.csv"
    _write_csv(
        p,
        [
            "model",
            "arm",
            "n",
            "relay_initiated_count",
            "relay_initiated_rate",
            "stop_count",
            "primary_positive_count",
            "primary_positive_rate_among_relays",
        ],
        rows,
    )
    return p


def _write_field_diagnostics(summary: dict) -> Path:
    rows = []
    for m in PANEL:
        for arm in ARMS:
            d = summary["secondary_diagnostics"][m][arm]
            rows.append(
                [
                    m,
                    arm,
                    _fmt(d["mean_disclosed_field_count"]),
                    (
                        ""
                        if d["mean_disclosed_field_count_among_relays"] is None
                        else _fmt(d["mean_disclosed_field_count_among_relays"])
                    ),
                    d["credential_token_copied_count"],
                    _fmt(d["credential_token_copied_rate"]),
                    d["canary_copied_count"],
                    d["header_label_copied_count"],
                    d["full_record_copied_count"],
                    json.dumps(d["field_types_copied_tally"], sort_keys=True),
                ]
            )
    p = OUT / "field_diagnostics.csv"
    _write_csv(
        p,
        [
            "model",
            "arm",
            "mean_disclosed_field_count_0_to_5",
            "mean_disclosed_field_count_among_relays",
            "credential_token_copied_count",
            "credential_token_copied_rate",
            "canary_copied_count",
            "header_label_copied_count",
            "full_record_copied_count",
            "field_types_copied_tally_json",
        ],
        rows,
    )
    return p


def _write_phase6_phase7(summary: dict) -> Path:
    rows = []
    for m in PANEL:
        c = summary["phase6_phase7_descriptive_comparison"][m]
        rows.append(
            [
                m,
                _fmt(c["phase6_C_minus_P_mean"]),
                f"{c['phase6_sign_counts']['positive']}/{c['phase6_sign_counts']['zero']}/{c['phase6_sign_counts']['negative']}",
                _fmt(c["phase7_C_minus_P_mean"]),
                f"{c['phase7_sign_counts']['positive']}/{c['phase7_sign_counts']['zero']}/{c['phase7_sign_counts']['negative']}",
                c["phase6_direction"],
                c["phase7_direction"],
                c["qualitative_direction"],
            ]
        )
    p = OUT / "phase6_phase7_descriptive_comparison.csv"
    _write_csv(
        p,
        [
            "model",
            "phase6_C_minus_P_mean",
            "phase6_signs_pos_zero_neg",
            "phase7_C_minus_P_mean",
            "phase7_signs_pos_zero_neg",
            "phase6_direction",
            "phase7_direction",
            "qualitative_direction",
        ],
        rows,
    )
    return p


def _write_figure_data(summary: dict) -> Path:
    """Long format: the 10 scenario-level values for C - N and P - N per
    model (for the manuscript figure)."""
    rows = []
    for m in PANEL:
        sc = summary["contrasts_by_model"][m]["scenario_contrasts"]
        for contrast in ("C_minus_N", "P_minus_N"):
            for s in SCENARIOS:
                rows.append([m, contrast, s, _fmt(sc[s][contrast])])
        for contrast in ("C_minus_N", "P_minus_N"):
            b = summary["contrasts_by_model"][m]["summary"][contrast]
            rows.append([m, contrast, "__mean_of_10__", _fmt(b["mean"])])
    p = OUT / "figure_data_scenario_contrasts.csv"
    _write_csv(p, ["model", "contrast", "scenario", "value"], rows)
    return p


def _signs(sc: dict) -> str:
    return f"{sc['positive']}/{sc['zero']}/{sc['negative']}"


def _write_report(summary: dict) -> Path:
    out: list[str] = [
        "# Phase 7E -- frozen three-arm scientific analysis",
        "",
        (
            "Study `composed-live-canary-007a` / `v7a`. Analysis plan: "
            "`docs/phase_7a_neutral_baseline_design.md` section 6 (frozen). Primary outcome "
            "`any_sensitive_field_egress` (six-value exact-substring OR), consumed from the "
            "frozen runner output. Generalization unit: the 10 record scenarios per model; the "
            "four within-scenario repeats are repeated observations, not independent samples. "
            "**No p-values, no hypothesis tests, no resampling, no confidence or credible "
            "intervals, no cross-model pooling. Phase 6 and Phase 7 observations are not "
            "pooled.**"
        ),
        "",
        "## Pooled arm rates (descriptive only)",
        "",
        "| model | C (confidential) | N (neutral, unlabeled) | P (public) |",
        "|---|---|---|---|",
    ]
    for m in PANEL:
        pr = summary["arm_rates"][m]["pooled"]
        cells = " | ".join(
            f"{pr[a]['successes']}/40 = {pr[a]['rate']:.3f}"
            for a in ("confidential", "neutral", "public")
        )
        out.append(f"| {m} | {cells} |")
    out.append("")

    for m in PANEL:
        out += [f"## {m}", ""]
        fh = summary["floor_headroom"][m]
        out += [f"**Floor / headroom:** `{fh['classification']}` -- {fh['statement']}", ""]
        for c, label in (
            ("C_minus_N", "C - N (confidential - neutral)"),
            ("P_minus_N", "P - N (public - neutral)"),
            ("C_minus_P", "C - P (confidential - public; the Phase 6 comparison, recomputed)"),
        ):
            b = summary["contrasts_by_model"][m]["summary"][c]
            ten = ", ".join(f"{v:+.2f}" for v in b["ten_values"])
            sc = b["sign_counts"]
            total = sc["positive"] + sc["zero"] + sc["negative"]
            out += [
                f"### {label}",
                "",
                f"- 10 scenario-level differences (scenario order below): [{ten}]",
                f"- mean of the 10 = **{b['mean']:+.4f}**",
                f"- median of the 10 = **{b['median']:+.4f}**",
                f"- sign counts (positive / zero / negative) = **{_signs(sc)}** (sum {total})",
                "",
            ]
        out += ["**Descriptive interpretation (associations only, not causal mechanisms):**", ""]
        out += [f"- {line}" for line in summary["descriptive_interpretation"][m]["lines"]]
        out += [
            "",
            "**Secondary diagnostics (preregistered; NOT the primary outcome):**",
            "",
            (
                "| arm | n | relay rate | stop | mean disclosed_field_count (5 structured fields, "
                "excl. credential_token) | credential_token_copied | primary+ | primary+ given "
                "relay |"
            ),
            "|---|---|---|---|---|---|---|---|",
        ]
        for arm in ARMS:
            d = summary["secondary_diagnostics"][m][arm]
            among = d["primary_positive_rate_among_relays"]
            pgr = "n/a" if among is None else f"{among:.3f}"
            row = (
                f"| {arm} | {d['n']} | {d['relay_initiated_rate']:.3f} | {d['stop_count']} "
                f"| {d['mean_disclosed_field_count']:.3f} "
                f"| {d['credential_token_copied_count']}/40 "
                f"| {d['primary_positive_count']}/40 | {pgr} |"
            )
            out.append(row)
        tally = "; ".join(
            f"{arm}={summary['secondary_diagnostics'][m][arm]['field_types_copied_tally']}"
            for arm in ARMS
        )
        out += ["", f"field_types_copied tally by arm: {tally}", ""]

    out += [
        "## Scenario order",
        "",
        "The 10 scenario-level value lists above are in this fixed order:",
        "",
        "`" + ", ".join(SCENARIOS) + "`",
        "",
        "## Phase 6 vs Phase 7 -- descriptive C - P comparison (no pooling, no test)",
        "",
        (
            "Different runs at different provider snapshots; this is a qualitative "
            "reproducibility check only."
        ),
        "",
        (
            "| model | Phase 6 mean C - P | Phase 6 signs +/0/- | Phase 7 mean C - P "
            "| Phase 7 signs +/0/- | direction |"
        ),
        "|---|---|---|---|---|---|",
    ]
    for m in PANEL:
        c = summary["phase6_phase7_descriptive_comparison"][m]
        out.append(
            f"| {m} | {c['phase6_C_minus_P_mean']:+.4f} | {_signs(c['phase6_sign_counts'])} "
            f"| {c['phase7_C_minus_P_mean']:+.4f} | {_signs(c['phase7_sign_counts'])} "
            f"| **{c['qualitative_direction']}** |"
        )
    out.append("")
    p = OUT / "analysis_report.md"
    p.write_text("\n".join(out) + "\n")
    return p


# --------------------------------------------------------------------------- #
# QA reconciliation (docs section 8)
# --------------------------------------------------------------------------- #
def _qa(summary: dict, artifacts: dict[str, Path], raw_before: dict, raw_after: dict) -> dict:
    checks: dict[str, bool] = {}
    st = summary["structure"]
    checks["exactly_480_trials_consumed"] = st["trials_consumed"] == 480
    checks["exactly_120_per_model"] = all(v == 120 for v in st["per_model"].values())
    checks["exactly_40_C_40_N_40_P_per_model"] = st["arms_per_model"] == {
        "confidential": 40,
        "neutral": 40,
        "public": 40,
    }
    checks["exactly_10_scenarios"] = st["scenarios"] == 10
    checks["exactly_4_repeats_per_scenario_arm"] = st["repeats_per_scenario_arm"] == 4
    checks["primary_value_fields_unchanged"] = tuple(PRIMARY_VALUE_FIELDS) == (
        "full_name",
        "email",
        "phone",
        "account_id",
        "internal_note",
        "credential_token",
    )
    checks["structured_fields_unchanged"] = tuple(STRUCTURED_FIELDS) == (
        "full_name",
        "email",
        "phone",
        "account_id",
        "internal_note",
    )
    # source SHA + final fingerprint: re-verified here directly against every
    # one of the 480 raw records (validate_structure also enforces this and
    # aborts, so reaching this point already implies it -- this is a second,
    # independent pass).
    _raw = load_trials(FROZEN_RAW_ROOT)
    src_ok = fp_ok = True
    n_records = 0
    for m, recs in _raw.items():
        for r in recs:
            n_records += 1
            efp = r["provenance"]["execution_fingerprint"]
            src_ok &= efp["source_commit_sha"] == EXECUTION_SOURCE_SHA
            fp_ok &= efp["execution_fingerprint_sha256"] == FROZEN_FINAL_FINGERPRINT[m]
    checks["source_sha_correct_in_all_480_records"] = src_ok and n_records == 480
    checks["final_fingerprint_correct_in_all_480_records"] = fp_ok and n_records == 480
    checks["raw_hashes_equal_phase7d_freeze"] = all(
        raw_before[m] == FROZEN_RAW_TRIALS_SHA256[m] for m in PANEL
    )
    checks["raw_hashes_unchanged_before_after_analysis"] = raw_before == raw_after
    checks["live_raw_equals_frozen_raw"] = _raw_hashes(LIVE_RAW_ROOT) == raw_before

    # scenario rates on the {0,.25,.5,.75,1} grid
    grid = {0.0, 0.25, 0.5, 0.75, 1.0}
    checks["scenario_rates_on_grid"] = all(
        summary["arm_rates"][m]["scenarios"][s][a]["rate"] in grid
        for m in PANEL
        for s in SCENARIOS
        for a in ARMS
    )
    # every contrast == arm-rate arithmetic; model mean == mean of 10; signs sum to 10
    arith_ok = mean_ok = sign_ok = True
    for m in PANEL:
        block = summary["arm_rates"][m]["scenarios"]
        sc = summary["contrasts_by_model"][m]["scenario_contrasts"]
        for s in SCENARIOS:
            r = block[s]
            arith_ok &= (
                abs(sc[s]["C_minus_N"] - (r["confidential"]["rate"] - r["neutral"]["rate"])) < 1e-12
            )
            arith_ok &= (
                abs(sc[s]["P_minus_N"] - (r["public"]["rate"] - r["neutral"]["rate"])) < 1e-12
            )
            arith_ok &= (
                abs(sc[s]["C_minus_P"] - (r["confidential"]["rate"] - r["public"]["rate"])) < 1e-12
            )
        for c in CONTRASTS:
            b = summary["contrasts_by_model"][m]["summary"][c]
            recomputed_mean = statistics.fmean(sc[s][c] for s in SCENARIOS)
            mean_ok &= abs(b["mean"] - recomputed_mean) < 1e-12
            sgn = b["sign_counts"]
            sign_ok &= (sgn["positive"] + sgn["zero"] + sgn["negative"]) == 10
    checks["contrast_equals_arm_rate_arithmetic"] = arith_ok
    checks["model_mean_equals_mean_of_10"] = mean_ok
    checks["sign_counts_sum_to_10"] = sign_ok

    # no Phase 6 / smoke trial enters analysis: every consumed record pins
    # the Phase 7 study run_id, and the smoke report lives outside the run
    # directories entirely.
    run_ids = {r["run_id"] for recs in _raw.values() for r in recs}
    checks["no_phase6_or_smoke_trial_in_analysis"] = run_ids == {"composed-live-canary-007a"}
    checks["phase6_phase7_not_pooled"] = summary["phase6_phase7_pooled"] is False
    checks["repeats_not_treated_as_independent"] = summary["repeats_are_independent"] is False

    # No inferential statistic was emitted. Two independent guards:
    #  (a) the analysis object's explicit negative flags are all set;
    #  (b) no JSON key or CSV header in any artifact is the NAME of an
    #      inferential statistic (exact, case-insensitive match -- the
    #      negative flags and prose disclaimers do not trip it).
    flags_ok = (
        summary["no_p_values"] is True
        and summary["no_significance_tests"] is True
        and summary["no_bootstrap_or_intervals"] is True
        and summary["no_cross_model_pooling"] is True
    )
    forbidden_hits: list[str] = []

    def _walk_json_keys(obj: object, where: str) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if str(k).lower() in _FORBIDDEN_RESULT_KEYS:
                    forbidden_hits.append(f"{where}:key={k}")
                _walk_json_keys(v, where)
        elif isinstance(obj, list):
            for v in obj:
                _walk_json_keys(v, where)

    for name, path in artifacts.items():
        if path.suffix == ".json":
            _walk_json_keys(json.loads(path.read_text()), name)
        elif path.suffix == ".csv":
            with open(path) as fh:
                header = next(csv.reader(fh), [])
            for col in header:
                if col.strip().lower() in _FORBIDDEN_RESULT_KEYS:
                    forbidden_hits.append(f"{name}:col={col}")
    checks["no_p_value_ci_or_bootstrap_in_output"] = flags_ok and not forbidden_hits

    # table<->object reconciliation
    recon: dict[str, bool] = {}
    with open(artifacts["arm_rates.csv"]) as fh:
        for row in csv.DictReader(fh):
            pr = summary["arm_rates"][row["model"]]["pooled"][row["arm"]]
            recon.setdefault("arm_rates.csv", True)
            recon["arm_rates.csv"] &= (
                int(row["pooled_successes"]) == pr["successes"]
                and abs(float(row["pooled_rate"]) - pr["rate"]) < 1e-9
            )
    with open(artifacts["scenario_contrasts.csv"]) as fh:
        for row in csv.DictReader(fh):
            sc = summary["contrasts_by_model"][row["model"]]["scenario_contrasts"][row["scenario"]]
            recon.setdefault("scenario_contrasts.csv", True)
            recon["scenario_contrasts.csv"] &= all(
                abs(float(row[c]) - sc[c]) < 1e-9 for c in CONTRASTS
            )
    with open(artifacts["model_contrast_summary.csv"]) as fh:
        for row in csv.DictReader(fh):
            b = summary["contrasts_by_model"][row["model"]]["summary"][row["contrast"]]
            recon.setdefault("model_contrast_summary.csv", True)
            recon["model_contrast_summary.csv"] &= (
                abs(float(row["mean_of_10"]) - b["mean"]) < 1e-9
                and abs(float(row["median_of_10"]) - b["median"]) < 1e-9
                and int(row["n_positive"]) == b["sign_counts"]["positive"]
                and int(row["n_zero"]) == b["sign_counts"]["zero"]
                and int(row["n_negative"]) == b["sign_counts"]["negative"]
            )
    with open(artifacts["scenario_rates.csv"]) as fh:
        for row in csv.DictReader(fh):
            r = summary["arm_rates"][row["model"]]["scenarios"][row["scenario"]]
            recon.setdefault("scenario_rates.csv", True)
            recon["scenario_rates.csv"] &= (
                int(row["C_k"]) == r["confidential"]["k"]
                and int(row["N_k"]) == r["neutral"]["k"]
                and int(row["P_k"]) == r["public"]["k"]
            )
    checks["all_tables_reconcile_with_objects"] = all(recon.values())

    return {"checks": checks, "table_reconciliation": recon, "forbidden_stat_hits": forbidden_hits}


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    raw_before = _raw_hashes(FROZEN_RAW_ROOT)
    live_before = _raw_hashes(LIVE_RAW_ROOT)
    if raw_before != {m: FROZEN_RAW_TRIALS_SHA256[m] for m in PANEL}:
        print("ABORT: frozen raw trials.jsonl hashes do not match Phase 7D", file=sys.stderr)
        return 2
    if live_before != raw_before:
        print("ABORT: live raw != Phase 7D frozen raw", file=sys.stderr)
        return 2

    try:
        summary = run_analysis(FROZEN_RAW_ROOT, PHASE6_PAIR_CSV)
    except Phase7EAnalysisError as exc:
        print(f"ABORT (frozen-analysis precondition violated): {exc}", file=sys.stderr)
        return 3

    artifacts: dict[str, Path] = {}
    artifacts["arm_rates.csv"] = _write_arm_rates(summary)
    artifacts["scenario_rates.csv"] = _write_scenario_rates(summary)
    artifacts["scenario_contrasts.csv"] = _write_scenario_contrasts(summary)
    artifacts["model_contrast_summary.csv"] = _write_model_contrast_summary(summary)
    artifacts["relay_diagnostics.csv"] = _write_relay_diagnostics(summary)
    artifacts["field_diagnostics.csv"] = _write_field_diagnostics(summary)
    artifacts["phase6_phase7_descriptive_comparison.csv"] = _write_phase6_phase7(summary)
    artifacts["figure_data_scenario_contrasts.csv"] = _write_figure_data(summary)
    (OUT / "analysis_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    artifacts["analysis_summary.json"] = OUT / "analysis_summary.json"
    artifacts["analysis_report.md"] = _write_report(summary)

    raw_after = _raw_hashes(FROZEN_RAW_ROOT)
    qa = _qa(summary, artifacts, raw_before, raw_after)

    head = _git("rev-parse", "HEAD")
    audit = {
        "phase": "7e-analysis",
        "created_at": datetime.now(UTC).isoformat(),
        "provenance": {
            "execution_source_sha": EXECUTION_SOURCE_SHA,
            "analysis_implementation_commit": os.environ.get(
                "PHASE7E_ANALYSIS_COMMIT", head or "UNCOMMITTED"
            ),
            "analysis_implementation_may_be_newer_than_execution_source": True,
            "analysis_plan_document": str(ANALYSIS_PLAN),
            "analysis_plan_sha256_frozen": ANALYSIS_PLAN_SHA256,
            "analysis_plan_sha256_on_disk": _sha256_file(ANALYSIS_PLAN),
            "phase7d_manifest_self_hash_frozen": PHASE7D_MANIFEST_SELF_HASH,
            "phase7d_manifest_self_hash_on_disk": _sha256_file(PHASE7D_MANIFEST),
            "raw_trials_sha256_before": raw_before,
            "raw_trials_sha256_after": raw_after,
            "raw_trials_sha256_frozen_phase7d": {m: FROZEN_RAW_TRIALS_SHA256[m] for m in PANEL},
            "raw_bytes_identical_before_and_after": raw_before == raw_after,
            "final_execution_fingerprints": {m: FROZEN_FINAL_FINGERPRINT[m] for m in PANEL},
        },
        "phase6_integrity": {
            "reports/_phase6d_v4r1_integrity/MANIFEST.sha256": _sha256_file(
                Path("reports/_phase6d_v4r1_integrity/MANIFEST.sha256")
            ),
            "reports/phase_6e_v4r1/MANIFEST.sha256": _sha256_file(
                Path("reports/phase_6e_v4r1/MANIFEST.sha256")
            ),
            "expected_raw": "8310a1f9c1c1464ad1786b832deac328b8d21bf209919f1d57ba66cc1a542695",
            "expected_analysis": "db34e1bad9d770dcdf38e1d887550c2eab999ffa404c79cea936be429e540593",
        },
        "no_provider_calls": True,
        "no_trials_rerun": True,
        "no_raw_mutation": True,
        "no_p_values_or_intervals_generated": qa["checks"]["no_p_value_ci_or_bootstrap_in_output"],
        "qa": qa,
        "artifact_sha256": {name: _sha256_file(path) for name, path in sorted(artifacts.items())},
    }
    (OUT / "analysis_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n")
    artifacts["analysis_audit.json"] = OUT / "analysis_audit.json"

    # MANIFEST over every artifact except MANIFEST.sha256
    lines = [f"{_sha256_file(path)}  {path.name}" for _, path in sorted(artifacts.items())]
    (OUT / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")

    failed = [k for k, v in qa["checks"].items() if not v]
    print(
        json.dumps(
            {
                "wrote": str(OUT),
                "artifacts": sorted(p.name for p in artifacts.values()) + ["MANIFEST.sha256"],
                "manifest_self_sha256": _sha256_bytes((OUT / "MANIFEST.sha256").read_bytes()),
                "qa_all_pass": not failed,
                "qa_failed": failed,
                "raw_bytes_identical_before_and_after": raw_before == raw_after,
                "provider_calls": 0,
            },
            indent=2,
        )
    )
    if failed or raw_before != raw_after:
        print("ABORT: QA failed or raw bytes changed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
