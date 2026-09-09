r"""Prove that redacting repository-identifying git commit SHAs from the
anonymous supplementary raw traces changed **no** scientific value.

Self-contained: run from the extracted supplementary package
(`uv run python paper/tmlr/verify_anon_equivalence.py`, or plain
`python3 paper/tmlr/verify_anon_equivalence.py`).

The redaction touches exactly one raw-record field --
`provenance.execution_fingerprint.source_commit_sha` -- and the same
value inside a few `summary.json` / `execution_fingerprint.json`
provenance blocks. It never touches a model output, stimulus, action,
score, trial id, arm, scenario, repeat, or any analysis input. This
script re-derives the frozen Phase 9 analysis from the sanitized traces
by calling the pinned analysis functions directly (the canonical
byte-for-byte freeze gates are intentionally not shipped -- integrity of
this package is its own `MANIFEST.sha256`), and checks:

  * per-model raw N / P egress counts and rates;
  * Q1 theta, 95% CI, classification (4/4 ABOVE) and the panel verdict
    (FAILS);
  * Q2 Delta, 95% CI, detected / not-detected ({terra, claude} detected)
    and the Holm-adjusted p-values;
  * the boundary-degeneracy note and every pre-registered Q1/Q2
    sensitivity result;
  * that the regenerated result equals the copy shipped in this package.

Prints ``ANON_RAW_SCIENTIFIC_EQUIVALENCE: PASS``.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_HEX40 = re.compile(r"^[0-9a-f]{40}$")

PKG = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PKG))

from scripts import phase_9_analyze as pa  # noqa: E402

RESULTS = PKG / "docs" / "phase_9_design" / "phase_9_results_attempt_002.json"
MARK = "[redacted-for-double-blind]"

EXPECT_RAW = {
    "gpt-5.6-sol": (192, 192),
    "gpt-5.6-terra": (158, 190),
    "gpt-5.6-luna": (192, 190),
    "claude-sonnet-5": (162, 182),
}
EXPECT_Q1_THETA = {"gpt-5.6-sol": 1.000, "gpt-5.6-terra": 0.823,
                   "gpt-5.6-luna": 1.000, "claude-sonnet-5": 0.844}
EXPECT_Q2_DELTA = {"gpt-5.6-sol": 0.000, "gpt-5.6-terra": 0.167,
                   "gpt-5.6-luna": -0.010, "claude-sonnet-5": 0.104}
EXPECT_Q2_DETECTED = {"gpt-5.6-sol": False, "gpt-5.6-terra": True,
                      "gpt-5.6-luna": False, "claude-sonnet-5": True}


def _fail(msg: str) -> None:
    print(f"ANON_RAW_SCIENTIFIC_EQUIVALENCE: FAIL -- {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> int:
    # 0. confirm the sanitized traces really are sanitized: every trial's
    #    provenance commit field must be the redaction marker, never a raw
    #    40-hex git SHA.
    lines = (PKG / "reports" / "experiments" / "phase-9-f3-sol" / "trials.jsonl"
             ).read_text().splitlines()
    seen_mark = False
    for ln in lines:
        rec = json.loads(ln)
        sha = ((rec.get("provenance") or {}).get("execution_fingerprint") or {}
               ).get("source_commit_sha")
        if sha == MARK:
            seen_mark = True
        elif sha and _HEX40.match(str(sha)):
            _fail(f"un-redacted 40-hex commit SHA still in trials.jsonl: {str(sha)[:12]}...")
    if not seen_mark:
        _fail("redaction marker not found in trials.jsonl -- run against the ANON package")

    # 1. re-derive the analysis from the sanitized traces (pinned functions)
    primary = pa._analyze_variant(exclude_protocol_errors=False)
    raw = pa._raw_egress_counts()
    sens = pa._sensitivity()
    desc = pa._descriptive()

    pm = primary["per_model"]
    for m, (n_eg, p_eg) in EXPECT_RAW.items():
        if (raw[m]["N_egress"], raw[m]["P_egress"]) != (n_eg, p_eg):
            _fail(f"{m} raw N/P {raw[m]['N_egress']}/{raw[m]['P_egress']} != {n_eg}/{p_eg}")
        if round(pm[m]["Q1"]["theta_hat"], 3) != EXPECT_Q1_THETA[m]:
            _fail(f"{m} Q1 theta {pm[m]['Q1']['theta_hat']}")
        if pm[m]["Q1"]["classification"] != "ABOVE":
            _fail(f"{m} Q1 class {pm[m]['Q1']['classification']} != ABOVE")
        if round(pm[m]["Q2"]["Delta_hat"], 3) != EXPECT_Q2_DELTA[m]:
            _fail(f"{m} Q2 Delta {pm[m]['Q2']['Delta_hat']}")
        if bool(pm[m]["Q2"]["detected_label_effect"]) != EXPECT_Q2_DETECTED[m]:
            _fail(f"{m} Q2 detected {pm[m]['Q2']['detected_label_effect']}")
    if primary["panel_Q1_verdict"] != "FAILS":
        _fail(f"panel verdict {primary['panel_Q1_verdict']} != FAILS")

    for m in ("gpt-5.6-sol", "gpt-5.6-luna"):
        w = sens[m]["Q1_trial_level_wilson_pooled_N"]["ci95"]
        if not (round(w[0], 3) == 0.980 and w[1] >= 0.999):
            _fail(f"{m} pooled-Wilson CI {w} != [0.980, 1.000]")

    # 2. the freshly derived blocks must equal what this package ships
    shipped = json.loads(RESULTS.read_text())
    checks = [
        ("RAW_EGRESS_COUNTS", raw, shipped["RAW_EGRESS_COUNTS"]),
        ("CONFIRMATORY_primary", primary, shipped["CONFIRMATORY_primary"]),
        ("SENSITIVITY_other", sens, shipped["SENSITIVITY_other"]),
        ("DESCRIPTIVE", desc, shipped["DESCRIPTIVE"]),
    ]
    for name, got, want in checks:
        if json.dumps(got, sort_keys=True) != json.dumps(want, sort_keys=True):
            _fail(f"regenerated {name} differs from the shipped copy")

    redacted = [k for k in ("scientific_freeze_commit",
                            "execution_implementation_freeze_commit",
                            "attempt_002_freeze_commit")
                if str(shipped.get(k, "")) == MARK]

    print("ANON_RAW_SCIENTIFIC_EQUIVALENCE: PASS")
    print("  N/P counts, Q1 theta + CI + class (4/4 ABOVE), panel verdict FAILS,")
    print("  Q2 Delta + CI + detected ({terra, claude}), Holm p, and every")
    print("  pre-registered Q1/Q2 sensitivity result: identical to the canonical analysis.")
    print("  Regenerated RAW_EGRESS_COUNTS / CONFIRMATORY_primary / SENSITIVITY_other /")
    print("  DESCRIPTIVE: byte-identical to the copy shipped in this package.")
    print(f"  Redacted provenance fields (not analysis inputs/outputs): {redacted}")
    print("  Only sanitized raw-record field: provenance.execution_fingerprint.source_commit_sha")
    return 0


if __name__ == "__main__":
    sys.exit(main())
