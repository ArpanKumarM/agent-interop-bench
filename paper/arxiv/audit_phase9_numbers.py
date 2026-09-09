r"""Phase 9 numeric audit -- extends the audit discipline
(audit_numbers.py, audit_phase8_numbers.py) to the Phase 9 F3 resolution
study as integrated into paper/main_v2.md and paper/arxiv/main_v2.tex.
Offline, no provider calls. Fails the build on any mismatch.

Checks:
  1. The frozen analysis output
     (docs/phase_9_design/phase_9_results_attempt_002.json) is internally
     consistent: RAW_EGRESS_COUNTS reconcile with the CONFIRMATORY_primary
     per-model theta_hat / Delta_hat (equal scenarios-per-domain + equal
     repeats => fixed-domain equal-weight mean == pooled mean); every Q1
     classification is ABOVE; the panel verdict is FAILS; the Q2
     detected-label-effect flags are terra/claude True, sol/luna False.
  2. Every load-bearing Phase 9 number the manuscript states -- raw N/P
     egress counts, N rates, theta_hat, Q1 CIs (incl. the degenerate
     [1.000, 1.000] and the non-degenerate Wilson [0.980, 1.000]),
     Delta_hat, Q2 CIs, the panel verdict, the 1,536 trial total, and the
     zero-attrition claim -- appears verbatim in BOTH main_v2.md and the
     flattened main_v2.tex, and matches the frozen JSON when re-rounded
     from it.
  3. The Claude Q2 multiplicity wording is present in both renderings:
     detected under the primary CI criterion, Holm-adjusted p ~ 0.09 not
     below 0.05 familywise, Holm pre-registered as supplementary only.
  4. The audited provider-drift limitation sentence is present in both
     renderings and makes no drift claim (mentions "provider-endpoint
     drift" only as one of several undistinguished sources).
  5. Stale pre-Phase-9 language fails the build: any wording that still
     frames F3's classification as unresolved / a candidate for a future
     higher-n follow-up, that says the resolution study was never run,
     the "512 unlabeled trials" typo, or a "40 x 5" scenario/repeat
     reference.

Run:  uv run python paper/arxiv/audit_phase9_numbers.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAIN_V2 = (ROOT / "paper" / "main_v2.md").read_text()
MAIN_V2_TEX = (ROOT / "paper" / "arxiv" / "main_v2.tex").read_text()
RESULTS = json.loads(
    (ROOT / "docs" / "phase_9_design" / "phase_9_results_attempt_002.json").read_text()
)

PANEL = ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "claude-sonnet-5")

_failures: list[str] = []


def check(cond: bool, msg: str) -> None:
    if not cond:
        _failures.append(msg)


def _norm(s: str) -> str:
    """Normalise a document to plain text for 'does this token appear'
    checks: strip TeX comments/macros/math punctuation, unify the minus
    sign and dashes, collapse whitespace."""
    s = re.sub(r"(?m)^\s*%.*$", "", s)
    s = re.sub(r"\\code\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\(?:textbf|emph|texttt|mbox|hat)\{([^{}]*)\}", r"\1", s)
    s = s.replace("{,}", ",").replace(r"\,", "").replace("~", " ").replace(r"\ ", " ")
    s = s.replace("\\$", "\x00")
    s = re.sub(r"\\[a-zA-Z]+", " ", s)  # remaining control words
    s = s.replace("$", "").replace("{", "").replace("}", "").replace("\x00", "$")
    s = s.replace("\u2212", "-").replace("\u2013", "-").replace("\u2014", " -- ")
    s = s.replace("\u00d7", "x").replace("\u2264", "<=").replace("\u2265", ">=")
    # superscript minus-six (10^{-6} in tex, 10-6 after macro strip; 10⁻⁶ in md)
    s = s.replace("\u2070", "0").replace("\u00b9", "1").replace("\u2076", "6")
    s = s.replace("\u207b", "-")
    return re.sub(r"[ \t\n]+", " ", s)


MD = _norm(MAIN_V2)
TEX = _norm(MAIN_V2_TEX)
DOCS = (("main_v2.md", MD), ("main_v2.tex", TEX))


# --------------------------------------------------------------------------- #
# 1. Frozen analysis output: internal consistency
# --------------------------------------------------------------------------- #
def audit_frozen_results_self_consistency() -> None:
    raw = RESULTS["RAW_EGRESS_COUNTS"]
    per_model = RESULTS["CONFIRMATORY_primary"]["per_model"]

    expected_counts = {
        "gpt-5.6-sol": (192, 192),
        "gpt-5.6-terra": (158, 190),
        "gpt-5.6-luna": (192, 190),
        "claude-sonnet-5": (162, 182),
    }
    for m, (n_eg, p_eg) in expected_counts.items():
        check(
            raw[m]["N_egress"] == n_eg and raw[m]["N_planned"] == 192,
            f"frozen JSON: {m} N egress {raw[m]['N_egress']}/{raw[m]['N_planned']} "
            f"!= expected {n_eg}/192",
        )
        check(
            raw[m]["P_egress"] == p_eg and raw[m]["P_planned"] == 192,
            f"frozen JSON: {m} P egress {raw[m]['P_egress']}/{raw[m]['P_planned']} "
            f"!= expected {p_eg}/192",
        )
        # equal domains/repeats => pooled mean == fixed-domain equal-weight mean
        check(
            abs(per_model[m]["Q1"]["theta_hat"] - raw[m]["N_egress"] / 192) < 1e-9,
            f"frozen JSON: {m} Q1 theta_hat {per_model[m]['Q1']['theta_hat']} "
            f"!= pooled N rate {raw[m]['N_egress'] / 192}",
        )
        check(
            abs(per_model[m]["Q2"]["Delta_hat"] - (raw[m]["P_egress"] - raw[m]["N_egress"]) / 192)
            < 1e-9,
            f"frozen JSON: {m} Q2 Delta_hat {per_model[m]['Q2']['Delta_hat']} "
            f"!= pooled (P-N) {(raw[m]['P_egress'] - raw[m]['N_egress']) / 192}",
        )
        check(
            per_model[m]["Q1"]["classification"] == "ABOVE",
            f"frozen JSON: {m} Q1 classification {per_model[m]['Q1']['classification']} != ABOVE",
        )

    check(
        RESULTS["CONFIRMATORY_primary"]["panel_Q1_verdict"] == "FAILS",
        f"frozen JSON: panel Q1 verdict {RESULTS['CONFIRMATORY_primary']['panel_Q1_verdict']} "
        "!= FAILS",
    )
    detected = {m: per_model[m]["Q2"]["detected_label_effect"] for m in PANEL}
    check(
        detected
        == {
            "gpt-5.6-sol": False,
            "gpt-5.6-terra": True,
            "gpt-5.6-luna": False,
            "claude-sonnet-5": True,
        },
        f"frozen JSON: Q2 detected flags changed: {detected}",
    )
    check(
        per_model["gpt-5.6-sol"]["Q1"]["pathological"] is True
        and per_model["gpt-5.6-luna"]["Q1"]["pathological"] is True
        and per_model["gpt-5.6-terra"]["Q1"]["pathological"] is False
        and per_model["claude-sonnet-5"]["Q1"]["pathological"] is False,
        "frozen JSON: Q1 pathological (boundary-degenerate) flags changed",
    )


# --------------------------------------------------------------------------- #
# 2. Manuscript numbers vs the frozen output, in BOTH renderings
# --------------------------------------------------------------------------- #
def _both(token: str, label: str) -> None:
    for doc_name, doc in DOCS:
        check(token in doc, f"{doc_name}: Phase 9 {label} token {token!r} not found")


def audit_manuscript_numbers() -> None:
    per_model = RESULTS["CONFIRMATORY_primary"]["per_model"]

    # raw egress counts
    for frac in ("192/192", "158/192", "162/192", "190/192", "182/192"):
        _both(frac, "raw egress count")

    # N rate / theta_hat point estimates (terra, claude, and the ceiling)
    check(
        round(per_model["gpt-5.6-terra"]["Q1"]["theta_hat"], 3) == 0.823,
        "frozen terra theta_hat no longer rounds to 0.823",
    )
    check(
        round(per_model["claude-sonnet-5"]["Q1"]["theta_hat"], 3) == 0.844,
        "frozen claude theta_hat no longer rounds to 0.844",
    )
    for tok in ("0.823", "0.844", "1.000"):
        _both(tok, "Q1 point estimate")

    # Q1 CIs, including the degenerate and the non-degenerate Wilson interval
    for ci in ("[0.759, 0.887]", "[0.762, 0.926]", "[1.000, 1.000]", "[0.980, 1.000]"):
        _both(ci, "Q1 95% CI")

    # Q2 Delta_hat
    for tok in ("+0.167", "+0.104", "+0.000", "-0.010"):
        _both(tok, "Q2 Delta_hat")

    # Q2 CIs
    for ci in ("[+0.105, +0.228]", "[+0.011, +0.198]", "[-0.026, +0.005]"):
        _both(ci, "Q2 95% CI")

    # verify those renderings against the frozen JSON (4-dp re-round)
    def _r(x: float) -> str:
        return f"{x:+.3f}"

    check(
        _r(per_model["gpt-5.6-terra"]["Q2"]["Delta_hat"]) == "+0.167",
        "frozen terra Delta_hat no longer +0.167 at 3 dp",
    )
    check(
        _r(per_model["claude-sonnet-5"]["Q2"]["Delta_hat"]) == "+0.104",
        "frozen claude Delta_hat no longer +0.104 at 3 dp",
    )
    lo, hi = per_model["gpt-5.6-terra"]["Q2"]["ci95"]
    check(
        (round(lo, 3), round(hi, 3)) == (0.105, 0.228),
        f"frozen terra Q2 CI {(lo, hi)} no longer rounds to [+0.105, +0.228]",
    )
    lo, hi = per_model["claude-sonnet-5"]["Q2"]["ci95"]
    check(
        (round(lo, 3), round(hi, 3)) == (0.011, 0.198),
        f"frozen claude Q2 CI {(lo, hi)} no longer rounds to [+0.011, +0.198]",
    )

    # structural claims
    for tok in ("1,536", "FAILS", "ABOVE"):
        _both(tok, "structural")
    for doc_name, doc in DOCS:
        check(
            "no attrition" in doc or "zero attrition" in doc or "0 attrition" in doc,
            f"{doc_name}: Phase 9 zero-attrition claim not found",
        )
        check(
            "64 scenarios" in doc or "64 generator-drawn scenarios" in doc,
            f"{doc_name}: Phase 9 '64 scenarios' not found",
        )
        check(
            "192 trials per model" in doc or "/ 192" in doc or "out of 192" in doc,
            f"{doc_name}: Phase 9 per-model 192 not found",
        )


# --------------------------------------------------------------------------- #
# 3. Claude Q2 multiplicity wording
# --------------------------------------------------------------------------- #
def audit_claude_multiplicity_wording() -> None:
    for doc_name, doc in DOCS:
        low = doc.lower()
        check("holm" in low, f"{doc_name}: Phase 9 Q2 wording must name the Holm adjustment")
        check(
            "familywise" in low,
            f"{doc_name}: Phase 9 Q2 wording must say the Holm-adjusted p was not below 0.05 "
            "familywise",
        )
        check(
            "0.09" in doc,
            f"{doc_name}: Phase 9 Q2 wording must give the Holm-adjusted p (0.09) for claude",
        )
        check(
            "primary criterion" in low or "primary rule" in low or "primary ci" in low,
            f"{doc_name}: Phase 9 Q2 wording must contrast the primary CI criterion with Holm",
        )
        check(
            "supplementary" in low or "robustness" in low,
            f"{doc_name}: Phase 9 must state Holm was pre-registered as supplementary/robustness "
            "only",
        )


# --------------------------------------------------------------------------- #
# 4. Provider-drift limitation sentence (audited wording, no drift claim)
# --------------------------------------------------------------------------- #
def audit_provider_drift_sentence() -> None:
    for doc_name, doc in DOCS:
        low = doc.lower()
        check(
            "provider-endpoint drift" in low or "provider endpoint drift" in low,
            f"{doc_name}: the audited provider-drift limitation sentence is missing",
        )
        # it must be framed as one of several sources that cannot be separated,
        # never as an established finding.
        window = ""
        idx = low.find("provider-endpoint drift")
        if idx == -1:
            idx = low.find("provider endpoint drift")
        if idx != -1:
            window = low[max(0, idx - 400) : idx + 200]
        check(
            "cannot separate" in window or "cannot be attributed" in window,
            f"{doc_name}: provider-drift sentence must say the sources cannot be separated",
        )
        check(
            "sampling variability" in window and "scenario distribution" in window,
            f"{doc_name}: provider-drift sentence must list sampling variability and the "
            "scenario-distribution change alongside endpoint drift",
        )


# --------------------------------------------------------------------------- #
# 5. Stale pre-Phase-9 language must fail the build
# --------------------------------------------------------------------------- #
_STALE = [
    (r"F3['\u2019]s rejection cannot be distinguished", "F3-rejection-not-distinguishable"),
    (r"F3['\u2019]s rejection is not distinguishable", "F3-rejection-not-distinguishable"),
    (
        r"rejection (?:is not|cannot be) distinguish\w+ from an acceptance",
        "present-tense F3 ambiguity",
    ),
    (r"F3 is the concrete candidate for a follow-up", "F3-still-a-candidate"),
    (r"candidate for a follow-up at higher", "F3-still-a-candidate"),
    (r"F3 in particular invites a\s+higher-.{0,3}n.{0,3} follow-up", "F3-invites-followup"),
    (r"follow-up that this pilot could not settle", "F3-unsettled-followup"),
    (r"that follow-up would have to re-collect", "F3-followup-must-recollect"),
    (r"512 unlabeled", "512-unlabeled-trials typo"),
    (r"\b40\s*[x\u00d7]\s*5\b", "40x5 scenario/repeat reference"),
    (
        r"resolution study[^.]{0,60}(?:never|not)\s+(?:run|executed)",
        "resolution-study-not-run",
    ),
    (
        r"Phase 9[^.]{0,40}(?:never run|not run|never executed|not executed|was not run)",
        "Phase-9-not-run",
    ),
]


def audit_no_stale_language() -> None:
    for doc_name, raw in (("main_v2.md", MAIN_V2), ("main_v2.tex", MAIN_V2_TEX)):
        flat = " ".join(raw.split())
        for pat, tag in _STALE:
            m = re.search(pat, flat, re.IGNORECASE)
            ctx = "" if m is None else flat[max(0, m.start() - 40) : m.end() + 40]
            check(
                m is None,
                f"{doc_name}: stale pre-Phase-9 language [{tag}]: ...{ctx}...",
            )


def main() -> int:
    audit_frozen_results_self_consistency()
    audit_manuscript_numbers()
    audit_claude_multiplicity_wording()
    audit_provider_drift_sentence()
    audit_no_stale_language()

    if _failures:
        print(f"=== {len(_failures)} PHASE 9 AUDIT FAILURE(S) ===", file=sys.stderr)
        for f in _failures:
            print(f"  FAIL: {f}", file=sys.stderr)
        return 1

    print("All Phase 9 numeric checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
