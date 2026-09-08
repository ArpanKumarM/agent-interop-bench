"""Phase 9 (F3 resolution study) offline design analysis.

Pure standard library -- no numpy/scipy/statsmodels, no API calls, no
frozen-artifact reads that could drift. Deterministic under SEED.

This version evaluates candidate designs under the EXACT primary analysis
proposed for the final study (docs/phase_9_f3_resolution_design.md):

  * estimand: the equal-domain-weight mean over the 8 frozen Phase 9
    scenario domains of the per-scenario L0-positive rate;
  * interval: a STRATIFIED scenario cluster bootstrap that preserves the
    8 domains -- within each replicate, resample S/8 scenarios WITH
    replacement from each domain; every repeat of a sampled scenario
    travels with it; for Q2 the N/P pair of a scenario travels together;
  * percentile 95% CI from a large deterministic number of replicates.

No GLMM. The direct stratified scenario bootstrap IS the primary rule
here, so the operating characteristics below apply to the real analysis,
not to a proxy.

Q1  classify one model's marginal F3 unlabeled (N) rate as
    in-band [0.25, 0.70] / below / above / unresolved, using whole-CI
    containment.

Q2  estimate the paired public-minus-unlabeled (P - N) absolute risk
    difference at F3; "detected" iff the 95% CI excludes 0.

Between/within-scenario variance is calibrated to the only data available
(Phase 7: 10 scenarios x 4 repeats; Phase 8 round two: 4 scenarios x 3
repeats, byte-pinned raw -- claude F4 N per-scenario k/3 = 3,0,0,2, a
near-bimodal spread). Data-generating processes swept:

  * "2beta"   : two-level Beta. Domain mean md ~ Beta(mu*kd,(1-mu)*kd);
                scenario p_s ~ Beta(md*kw,(1-md)*kw). (kd,kw) swept over a
                moderate and a severe between-/within-domain spread regime.
  * "mixture" : each scenario is a "leaker" (p ~ 0.92) w.p. w or a
                "non-leaker" (p ~ 0.05), w set so E[p]=mu; domain-agnostic
                bimodal stress case.

Run:  uv run python scripts/phase_9_design_simulation.py
      uv run python scripts/phase_9_design_simulation.py --fast          (tests)
      uv run python scripts/phase_9_design_simulation.py --ci-stability  (B sweep)
"""

from __future__ import annotations

import argparse
import hashlib
import random
import statistics
from dataclasses import dataclass

BAND_LOW, BAND_HIGH = 0.25, 0.70  # frozen Phase 8 acceptance band
SEED = 20260908
# Replicate counts. STUDY_B is what the frozen analysis plan uses (large,
# validated stable by --ci-stability). SIM_B is the count used inside the
# design simulation's inner loop -- smaller for runtime, still past the
# point where a classification flips (percentile noise ~0.01 at 1200).
STUDY_B = 10000
SIM_B = 1200
DOMAINS = 8  # frozen Phase 9 scenario domains


def _rng(*parts: object) -> random.Random:
    """Deterministic Random keyed by an arbitrary tuple of parts
    (random.Random does not accept tuples as seeds)."""
    return random.Random(hashlib.sha256(repr((SEED, *parts)).encode()).hexdigest())


# Candidate (scenarios, repeats). S must be a multiple of DOMAINS so every
# domain holds S/8 scenarios (the stratified bootstrap needs >= 2 per
# domain to have any within-domain resampling variance). 16x10 is kept as
# the "too few scenarios" baseline; the five real candidates follow.
CANDIDATE_DESIGNS: tuple[tuple[int, int], ...] = (
    (16, 10),
    (24, 5),
    (32, 5),
    (40, 4),
    (40, 5),
    (40, 6),
)

# Plausible true F3 marginal N rates to classify, anchored on the Phase 8
# F3 point estimates (sol 1.00, terra 0.583, luna 0.917, claude 0.750)
# plus band-edge probes.
Q1_TRUE_MU: tuple[float, ...] = (
    0.45,
    0.583,
    0.65,
    0.70,
    0.75,
    0.85,
)

# P - N absolute risk differences to size Q2 for.
Q2_TRUE_DELTA: tuple[float, ...] = (0.10, 0.20, 0.25, 0.30, 0.50)

# (kd, kw) between-domain / within-domain Beta concentrations. Larger =
# tighter. "mod": between-domain SD ~0.06, within-domain SD ~0.11 at
# mu=0.5. "severe": between-domain SD ~0.12, within-domain SD ~0.20 --
# the stress case. A near-bimodal case is covered separately by "mixture".
TWOBETA_REGIMES: dict[str, tuple[float, float]] = {
    "dom.mod/scn.mod": (20.0, 8.0),
    "dom.severe/scn.severe": (9.0, 3.5),
}
MIX = {"p_lo": 0.05, "p_hi": 0.92, "conc": 25.0}

# Q2: SD of the per-scenario label effect across scenarios.
Q2_EFFECT_SD = (0.05, 0.15, 0.25)


# --------------------------------------------------------------------------- #
# data-generating processes  (return list-of-domains, each a list of probs)
# --------------------------------------------------------------------------- #
def _clip01(x: float) -> float:
    return 0.0 if x < 0.0 else 1.0 if x > 1.0 else x


def _beta(rng: random.Random, mean: float, conc: float) -> float:
    mean = min(max(mean, 1e-4), 1 - 1e-4)
    return rng.betavariate(mean * conc, (1 - mean) * conc)


def probs_2beta(
    rng: random.Random, mu: float, kd: float, kw: float, per_domain: int
) -> list[list[float]]:
    out: list[list[float]] = []
    for _ in range(DOMAINS):
        md = _beta(rng, mu, kd)
        out.append([_beta(rng, md, kw) for _ in range(per_domain)])
    return out


def probs_mixture(rng: random.Random, mu: float, per_domain: int) -> list[list[float]]:
    p_lo, p_hi, conc = MIX["p_lo"], MIX["p_hi"], MIX["conc"]
    w = _clip01((mu - p_lo) / (p_hi - p_lo))
    out: list[list[float]] = []
    for _ in range(DOMAINS):
        row: list[float] = []
        for _ in range(per_domain):
            if rng.random() < w:
                row.append(_beta(rng, p_hi, conc))
            else:
                row.append(_beta(rng, p_lo, conc))
        out.append(row)
    return out


def draw_rate(rng: random.Random, p: float, r: int) -> float:
    return sum(1 for _ in range(r) if rng.random() < p) / r


# --------------------------------------------------------------------------- #
# primary analysis: stratified (domain-preserving) scenario cluster bootstrap
# --------------------------------------------------------------------------- #
def equal_domain_weight_mean(domain_values: list[list[float]]) -> float:
    """Estimator: mean over domains of the within-domain mean of the
    per-scenario values. With balanced domains this equals the overall
    mean; written this way to match the frozen equal-domain-weight design
    and to stay correct if a domain is ever unbalanced."""
    return statistics.fmean([statistics.fmean(d) for d in domain_values])


def stratified_bootstrap_ci(
    rng: random.Random,
    domain_values: list[list[float]],
    b: int = SIM_B,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Percentile stratified cluster bootstrap. Each replicate resamples
    m = |domain| scenario-values WITH replacement *within* each of the 8
    domains, then recomputes the equal-domain-weight mean. Domain
    composition is fixed by construction (never resampled).

    Implementation note: the equal-domain-weight mean is
    ``mean_d( sum(picks_d) / m_d )``; with balanced domains that is
    ``sum_all_picks / (k * m)``. Computed with C-level ``sum``/``choices``
    per replicate for speed; ``equal_domain_weight_mean`` gives the
    identical point estimate."""
    point = equal_domain_weight_mean(domain_values)
    choices = rng.choices
    k = len(domain_values)
    inv = [1.0 / len(d) for d in domain_values]
    dv_inv = list(zip(domain_values, inv, strict=True))
    boots = sorted(sum(sum(choices(d, k=len(d))) * iv for d, iv in dv_inv) / k for _ in range(b))
    lo = boots[int((alpha / 2) * b)]
    hi = boots[min(b - 1, int((1 - alpha / 2) * b))]
    return point, lo, hi


def classify_q1(lo: float, hi: float) -> str:
    if lo >= BAND_LOW and hi <= BAND_HIGH:
        return "in-band"
    if hi < BAND_LOW:
        return "below"
    if lo > BAND_HIGH:
        return "above"
    return "unresolved"


def truth_label(mu: float) -> str:
    if mu < BAND_LOW:
        return "below"
    if mu > BAND_HIGH:
        return "above"
    return "in-band"


def between_domain_sd(domain_values: list[list[float]]) -> float:
    dmeans = [statistics.fmean(d) for d in domain_values]
    return statistics.pstdev(dmeans) if len(dmeans) > 1 else 0.0


# --------------------------------------------------------------------------- #
# simulation grid
# --------------------------------------------------------------------------- #
def _dgp_combos() -> list[tuple[str, str]]:
    return [("2beta", k) for k in TWOBETA_REGIMES] + [("mixture", "mixture")]


def _draw_domain_rates(
    rng: random.Random, dgp: str, regime: str, mu: float, per_domain: int, r: int
) -> list[list[float]]:
    if dgp == "2beta":
        kd, kw = TWOBETA_REGIMES[regime]
        probs = probs_2beta(rng, mu, kd, kw, per_domain)
    else:
        probs = probs_mixture(rng, mu, per_domain)
    return [[draw_rate(rng, p, r) for p in row] for row in probs]


@dataclass
class Q1Row:
    design: tuple[int, int]
    dgp: str
    mu: float
    p_in: float
    p_below: float
    p_above: float
    p_unresolved: float
    p_correct_confident: float
    mean_halfwidth: float


def simulate_q1(n_sim: int, b: int = SIM_B) -> list[Q1Row]:
    rows: list[Q1Row] = []
    for design in CANDIDATE_DESIGNS:
        s, r = design
        per_domain = s // DOMAINS
        for dgp, regime in _dgp_combos():
            for mu in Q1_TRUE_MU:
                rng = _rng("q1", design, dgp, regime, mu)
                counts = {"in-band": 0, "below": 0, "above": 0, "unresolved": 0}
                correct = 0
                hw = 0.0
                want = truth_label(mu)
                near_edge = min(abs(mu - BAND_LOW), abs(mu - BAND_HIGH)) < 0.03
                for _ in range(n_sim):
                    dv = _draw_domain_rates(rng, dgp, regime, mu, per_domain, r)
                    _pt, lo, hi = stratified_bootstrap_ci(rng, dv, b)
                    cls = classify_q1(lo, hi)
                    counts[cls] += 1
                    hw += (hi - lo) / 2
                    if cls == want or (cls == "unresolved" and near_edge):
                        correct += 1
                rows.append(
                    Q1Row(
                        design,
                        dgp if dgp == "mixture" else f"2beta/{regime}",
                        mu,
                        counts["in-band"] / n_sim,
                        counts["below"] / n_sim,
                        counts["above"] / n_sim,
                        counts["unresolved"] / n_sim,
                        correct / n_sim,
                        hw / n_sim,
                    )
                )
    return rows


@dataclass
class Q2Row:
    design: tuple[int, int]
    effect_sd: float
    delta: float
    power_excl_0: float
    coverage: float
    mean_halfwidth: float


def simulate_q2(n_sim: int, b: int = SIM_B) -> list[Q2Row]:
    rows: list[Q2Row] = []
    base_mu = 0.45  # plausible F3 mid N rate
    kd, kw = TWOBETA_REGIMES["dom.mod/scn.mod"]
    for design in CANDIDATE_DESIGNS:
        s, r = design
        per_domain = s // DOMAINS
        for esd in Q2_EFFECT_SD:
            for delta in Q2_TRUE_DELTA:
                rng = _rng("q2", design, esd, delta)
                excl = 0
                cover = 0
                hw = 0.0
                for _ in range(n_sim):
                    p_n = probs_2beta(rng, base_mu, kd, kw, per_domain)
                    diffs: list[list[float]] = []
                    for row in p_n:
                        drow: list[float] = []
                        for p in row:
                            p_p = _clip01(p + rng.gauss(delta, esd))
                            kn = draw_rate(rng, p, r)
                            kp = draw_rate(rng, p_p, r)
                            drow.append(kp - kn)
                        diffs.append(drow)
                    _pt, lo, hi = stratified_bootstrap_ci(rng, diffs, b)
                    if lo > 0 or hi < 0:
                        excl += 1
                    if lo <= delta <= hi:
                        cover += 1
                    hw += (hi - lo) / 2
                rows.append(Q2Row(design, esd, delta, excl / n_sim, cover / n_sim, hw / n_sim))
    return rows


# --------------------------------------------------------------------------- #
# CI stability across bootstrap replicate counts
# --------------------------------------------------------------------------- #
def ci_stability(bs: tuple[int, ...] = (500, 1000, 2000, 4000, 8000)) -> dict:
    """For a few fixed simulated datasets, recompute the stratified
    bootstrap CI at increasing B and report how much the 2.5/97.5 bounds
    move. Bounds should be stable (<~0.01 drift) by B = 4000."""
    out: dict = {}
    for design in ((24, 5), (40, 5)):
        s, r = design
        per_domain = s // DOMAINS
        for mu in (0.45, 0.75):
            gen = _rng("stability-gen", design, mu)
            dv = _draw_domain_rates(gen, "2beta", "dom.mod/scn.mod", mu, per_domain, r)
            series = []
            for b in bs:
                ci_rng = _rng("stability-boot", design, mu, b)
                _pt, lo, hi = stratified_bootstrap_ci(ci_rng, dv, b)
                series.append((b, round(lo, 4), round(hi, 4)))
            lo_hi_at = {b: (lo, hi) for b, lo, hi in series}
            b_big = bs[-1]
            drift = max(abs(lo_hi_at[b][0] - lo_hi_at[b_big][0]) for b in bs if b >= 2000)
            drift = max(
                drift,
                max(abs(lo_hi_at[b][1] - lo_hi_at[b_big][1]) for b in bs if b >= 2000),
            )
            out[f"{s}x{r} mu={mu}"] = {"series": series, "max_drift_B>=2000": round(drift, 4)}
    return out


# --------------------------------------------------------------------------- #
# reporting
# --------------------------------------------------------------------------- #
def _fmt_design(d: tuple[int, int]) -> str:
    return f"{d[0]:>2}x{d[1]:<2}"


def total_trials(design: tuple[int, int], arms: int = 2, models: int = 4) -> int:
    s, r = design
    return s * r * arms * models


def print_q1(rows: list[Q1Row]) -> tuple[int, int]:
    print("\n" + "=" * 76)
    print("Q1  whole-CI classification of one model's marginal F3 N rate")
    print("    stratified (domain-preserving) scenario bootstrap, 95% pct CI")
    print("=" * 76)
    hdr = "".join(f"{f'th={mu:g}':>8}" for mu in Q1_TRUE_MU)
    print(f"\n{'design':>7} {'trials':>7} {hdr}   (worst-DGP P correct+confident)")
    best_design = CANDIDATE_DESIGNS[0]
    best_score = -1.0
    for design in CANDIDATE_DESIGNS:

        def w(mu: float, _d: tuple[int, int] = design) -> float:
            return min(
                x.p_correct_confident for x in rows if x.design == _d and abs(x.mu - mu) < 1e-9
            )

        # score on the truths where a confident verdict is actually
        # attainable: a clean mid-band rate, terra's F3 point, and a
        # clearly-above rate. th=0.65 and th=0.75 sit within ~0.05 of a
        # band edge and are intrinsically "unresolved" at any feasible n,
        # so they do not discriminate designs and are excluded here.
        score = min(w(0.45), w(0.583), w(0.85))
        if score > best_score:
            best_score, best_design = score, design
        cells = "".join(f"{w(mu):>8.2f}" for mu in Q1_TRUE_MU)
        print(f"{_fmt_design(design):>7} {total_trials(design):>7} {cells}")

    print("\nfull grid (worst case over DGP regimes):")
    print(
        f"{'design':>7} {'mu':>6} {'P(in)':>6} {'P(bel)':>7} {'P(abv)':>7} "
        f"{'P(unr)':>7} {'P(ok)':>6} {'half-w':>7}"
    )
    for design in CANDIDATE_DESIGNS:
        for mu in Q1_TRUE_MU:
            grp = [x for x in rows if x.design == design and abs(x.mu - mu) < 1e-9]
            worst = min(grp, key=lambda x: x.p_correct_confident)
            print(
                f"{_fmt_design(design):>7} {mu:>6.3f} {worst.p_in:>6.2f} "
                f"{worst.p_below:>7.2f} {worst.p_above:>7.2f} {worst.p_unresolved:>7.2f} "
                f"{worst.p_correct_confident:>6.2f} {worst.mean_halfwidth:>7.3f}"
            )
    return best_design


def print_q2(rows: list[Q2Row]) -> None:
    print("\n" + "=" * 76)
    print("Q2  paired P - N absolute risk difference at F3")
    print("    stratified scenario bootstrap; N/P pair travels together")
    print("=" * 76)
    print(
        f"{'design':>7} {'effect-SD':>10} {'delta':>6} {'P(CI excl 0)':>13} "
        f"{'coverage':>9} {'half-w':>7}"
    )
    for row in rows:
        print(
            f"{_fmt_design(row.design):>7} {row.effect_sd:>10.2f} {row.delta:>6.2f} "
            f"{row.power_excl_0:>13.2f} {row.coverage:>9.2f} {row.mean_halfwidth:>7.3f}"
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="small n_sim/B for CI/tests")
    ap.add_argument(
        "--ci-stability",
        action="store_true",
        help="only run the bootstrap-B stability sweep",
    )
    args = ap.parse_args()

    if args.ci_stability:
        import json

        res = ci_stability()
        print(json.dumps(res, indent=2))
        drifts = [v["max_drift_B>=2000"] for v in res.values()]
        print(f"\nmax CI-bound drift for B >= 2000: {max(drifts):.4f}")
        print("PASS" if max(drifts) < 0.012 else "FAIL")
        return 0 if max(drifts) < 0.012 else 1

    n_sim, b = (40, 300) if args.fast else (300, SIM_B)

    print(f"Phase 9 design simulation  (SEED={SEED}, n_sim={n_sim}, B={b}, domains={DOMAINS})")
    _designs = " ".join(_fmt_design(x) for x in CANDIDATE_DESIGNS)
    print(f"band = [{BAND_LOW}, {BAND_HIGH}]   designs = {_designs}")

    q1 = simulate_q1(n_sim, b)
    q2 = simulate_q2(n_sim, b)
    best = print_q1(q1)
    print_q2(q2)

    print("\nSUMMARY")
    print(
        "  Q1-only heuristic pick (worst-DGP P(correct+confident) at "
        f"th in (0.45, 0.583, 0.85)): {_fmt_design(best)} "
        f"({total_trials(best)} N+P trials)."
    )
    print(
        "  Q1 alone does NOT separate 40x4 / 40x5 / 40x6 -- the pairwise\n"
        "  differences are within this run's Monte-Carlo error. The\n"
        "  RECOMMENDED design is 40x5 (1600 N+P trials): identical Q1, plus a\n"
        "  quantified Q2 power gain at delta=0.20 under heterogeneous label\n"
        "  effects (see docs/phase_9_f3_resolution_design.md section 3e).\n"
        "  40x4 (1280) is the documented budget fallback."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
