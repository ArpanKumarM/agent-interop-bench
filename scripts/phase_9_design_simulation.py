"""Phase 9 (F3 resolution study) offline design + CI-calibration analysis.

Pure standard library -- no numpy/scipy/statsmodels, no API calls, no
frozen-artifact reads that could drift. Deterministic under SEED.

Estimand (both questions, per model, over the 8 frozen scenario domains):
the EQUAL-DOMAIN-WEIGHT mean -- (1/8) * sum_d mean_{s in domain d}(...).
  Q1:  ... of the per-scenario unlabeled (N) L0-positive rate.
  Q2:  ... of the per-scenario paired difference r_{s,P} - r_{s,N}.

PRIMARY interval procedures, chosen by the `--calibrate` pass below on
empirical coverage (not on detection power):
  Q1 -> method G: a plain Student-t interval on the 8 domain means
        (df = 7).  Captures the between-domain heterogeneity in the level,
        which dominates Q1's uncertainty.  Reviewer-reproducible in one
        line.
  Q2 -> method E: a stratified two-stage Welch-Satterthwaite t interval on
        the per-domain mean paired difference, with a within-domain
        binomial variance floor.  Pairing removes the level heterogeneity,
        so the residual variance is within-domain effect variation, which
        this formula targets.
Neither is a bootstrap; neither is a GLMM.  The percentile / BCa /
bootstrap-t / raw-analytic / logit / inflated / atanh variants are
retained as labelled SENSITIVITY analyses and are compared head-to-head
in `--calibrate`.

Data-generating processes (calibrated to Phase 7: 10 scenarios x 4
repeats; Phase 8 round two: 4 scenarios x 3 repeats, byte-pinned raw --
claude F4 N per-scenario k/3 = 3,0,0,2, near-bimodal):
  * "2beta"   : two-level Beta.  Domain mean md ~ Beta(mu*kd,(1-mu)*kd);
                scenario p_s ~ Beta(md*kw,(1-md)*kw).  Moderate + severe
                between-/within-domain spread regimes.
  * "mixture" : each scenario is a "leaker" (p ~ 0.92) w.p. w or a
                "non-leaker" (p ~ 0.05), w set so E[p]=mu; bimodal stress.

Run:  uv run python scripts/phase_9_design_simulation.py                    (design OCs)
      uv run python scripts/phase_9_design_simulation.py --calibrate        (CI calibration)
      uv run python scripts/phase_9_design_simulation.py --calibrate-designs (S x R spot-check)
      uv run python scripts/phase_9_design_simulation.py --ci-stability      (bootstrap B sweep)
      uv run python scripts/phase_9_design_simulation.py --fast             (small; tests)
"""

from __future__ import annotations

import argparse
import hashlib
import math
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
# domain holds S/8 scenarios (>= 2 needed for a within-domain variance;
# the primary Q1/Q2 intervals want >= ~4). 16x10 is the "too few
# scenarios" baseline; the five real candidates follow.
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

# --- CI-calibration pass (`--calibrate`) grids ---------------------------- #
CALIB_DESIGN = (40, 5)  # the selected design; 40x4 is spot-checked separately
CALIB_Q1_MU = (0.20, 0.25, 0.30, 0.45, 0.583, 0.65, 0.70, 0.75, 0.85, 0.95)
CALIB_Q2_DELTA = (0.0, 0.10, 0.20, 0.25, 0.30, 0.50)
CALIB_Q2_EFFECT_SD = (0.15, 0.25)
# "central plausible operating region" over which the 0.93-0.97 coverage
# target is judged (band edges and extreme rates are allowed to be
# imperfect, provided they are conservative).
CALIB_Q1_CENTRAL = (0.30, 0.45, 0.583, 0.65, 0.85)
CALIB_Q2_CENTRAL = (0.0, 0.10, 0.20, 0.25, 0.30)
COVERAGE_TARGET_LO, COVERAGE_TARGET_HI = 0.93, 0.97


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
# point estimator + the stratified bootstrap (retained as a SENSITIVITY
# interval and used by --ci-stability; the PRIMARY intervals are the
# analytic methods G (Q1) and E (Q2) defined further down)
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
    """Operating characteristics of the Q1 whole-CI classification rule
    under the PRIMARY Q1 interval (method G: domain-level t on the 8
    domain means; chosen by the --calibrate pass)."""
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
                    _pt, lo, hi, _pa = m_domain_t(None, dv, b)
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
    """Operating characteristics of the Q2 paired contrast under the
    PRIMARY Q2 interval (method E: stratified Welch t on the per-domain
    mean paired difference, with the within-domain binomial variance
    floor; chosen by the --calibrate pass)."""
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
                    nr: list[float] = []
                    pr: list[float] = []
                    for row in p_n:
                        drow: list[float] = []
                        for p in row:
                            p_p = _clip01(p + rng.gauss(delta, esd))
                            kn = draw_rate(rng, p, r)
                            kp = draw_rate(rng, p_p, r)
                            drow.append(kp - kn)
                            nr.append(kn)
                            pr.append(kp)
                        diffs.append(drow)
                    mn = statistics.fmean(nr)
                    mp = statistics.fmean(pr)
                    s2_floor = (mn * (1.0 - mn) + mp * (1.0 - mp)) / r
                    _pt, lo, hi, _pa = m_analytic_ws_floor(None, diffs, b, s2_floor)
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
# CI-calibration pass: candidate scenario-aware interval procedures
# --------------------------------------------------------------------------- #
# All methods take domain_values = list of DOMAINS lists of per-scenario
# rates (Q1) or per-scenario paired P-N differences (Q2), and return
# (point, lo, hi, pathology: bool). rng / b are used only by the bootstrap
# methods. Point estimate is always the equal-domain-weight mean.
#
# Student-t cdf / ppf for arbitrary (Welch-Satterthwaite) df, via the
# regularized incomplete beta function -- stdlib only, reviewer-checkable.
_NORM = statistics.NormalDist()


def _betacf(a: float, b: float, x: float) -> float:
    maxit, eps, fpmin = 300, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, maxit + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def _betai(a: float, b: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log1p(-x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def student_t_cdf(t: float, df: float) -> float:
    x = df / (df + t * t)
    ib = 0.5 * _betai(df / 2.0, 0.5, x)
    return 1.0 - ib if t > 0.0 else ib


def student_t_ppf(p: float, df: float) -> float:
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    lo, hi = -200.0, 200.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if student_t_cdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _var_ddof1(d: list[float]) -> tuple[float, float]:
    """(mean, ddof=1 sample variance) of a short list, inline for speed."""
    n = len(d)
    s = 0.0
    ss = 0.0
    for x in d:
        s += x
        ss += x * x
    mean = s / n
    if n < 2:
        return mean, 0.0
    v = (ss - s * s / n) / (n - 1)
    return mean, (v if v > 0.0 else 0.0)


def _ws_var_df(dv: list[list[float]], s2_floor: float = 0.0) -> tuple[float, float, float]:
    """Two-stage stratified mean: theta = mean over H domains of the
    within-domain scenario-rate mean. Var(theta) = (1/H^2) * sum_h
    s_h^2 / n_h, with s_h^2 the ddof=1 within-domain variance (optionally
    floored). Welch-Satterthwaite df from the per-domain variance
    contributions."""
    h_ = len(dv)
    h2 = h_ * h_
    sum_ybar = 0.0
    var = 0.0
    dfden = 0.0
    for d in dv:
        n = len(d)
        mean, s2 = _var_ddof1(d)
        sum_ybar += mean
        if s2 < s2_floor:
            s2 = s2_floor
        u = s2 / (n * h2)
        var += u
        if n > 1:
            dfden += (u * u) / (n - 1)
    theta = sum_ybar / h_
    df = (var * var) / dfden if (dfden > 0.0 and var > 0.0) else float(h_ - 1)
    return theta, var, max(df, 1.0)


def m_analytic_ws(
    rng: random.Random | None, dv: list[list[float]], b: int, s2_floor: float = 0.0
) -> tuple[float, float, float, bool]:
    """D: raw analytic stratified Welch-Satterthwaite t interval."""
    theta, var, df = _ws_var_df(dv, s2_floor)
    if var <= 0.0:
        return theta, theta, theta, True
    hw = student_t_ppf(0.975, df) * math.sqrt(var)
    return theta, theta - hw, theta + hw, False


def m_analytic_ws_floor(
    rng: random.Random | None, dv: list[list[float]], b: int, s2_floor: float = 0.0
) -> tuple[float, float, float, bool]:
    """E: analytic stratified WS t with a within-domain variance FLOOR.
    The caller passes s2_floor = (binomial sampling variance of a single
    scenario rate) so that a domain whose 5 scenarios happen to be equal
    still contributes non-zero uncertainty."""
    theta, var, df = _ws_var_df(dv, s2_floor)
    if var <= 0.0:
        return theta, theta, theta, True
    hw = student_t_ppf(0.975, df) * math.sqrt(var)
    return theta, theta - hw, theta + hw, False


def m_analytic_ws_logit(
    rng: random.Random | None, dv: list[list[float]], b: int, s2_floor: float = 0.0
) -> tuple[float, float, float, bool]:
    """F (Q1 only): analytic stratified WS t on the logit scale, back-
    transformed -- respects [0,1] and gives asymmetric intervals near a
    boundary. Falls back to the floored raw-scale interval when theta is
    at 0/1."""
    theta, var, df = _ws_var_df(dv, 0.0)
    eps = 1e-6
    if theta <= eps or theta >= 1.0 - eps or var <= 0.0:
        return m_analytic_ws_floor(rng, dv, b, s2_floor)
    g = math.log(theta / (1.0 - theta))
    se_g = math.sqrt(var) / (theta * (1.0 - theta))
    t = student_t_ppf(0.975, df)
    lo = 1.0 / (1.0 + math.exp(-(g - t * se_g)))
    hi = 1.0 / (1.0 + math.exp(-(g + t * se_g)))
    return theta, lo, hi, False


def m_domain_t(
    rng: random.Random | None, dv: list[list[float]], b: int, s2_floor: float = 0.0
) -> tuple[float, float, float, bool]:
    """G: plain t interval on the H=8 domain means (df = H-1 = 7).
    Conservative; ignores that each domain mean is itself estimated from
    only 5 scenarios. Reviewer-reproducible in one line."""
    ybar = [statistics.fmean(d) for d in dv]
    h_ = len(ybar)
    theta = statistics.fmean(ybar)
    if h_ < 2:
        return theta, 0.0, 1.0, True
    se = statistics.stdev(ybar) / math.sqrt(h_)
    hw = student_t_ppf(0.975, h_ - 1) * se
    return theta, theta - hw, theta + hw, False


# Pre-registered small-sample calibration inflation on the analytic
# half-width. Chosen offline (this script's --calibrate pass) as the
# smallest factor that lifts empirical nominal-95% coverage to >= 0.93
# across the central operating region under the moderate, severe AND
# bimodal DGP families with 8 domains x 5 scenarios. Frozen with the
# analysis plan. See docs/phase_9_f3_resolution_design.md section 4.
PHASE9_CI_INFLATION = 1.30


def m_ws_floor_inflated(
    rng: random.Random | None, dv: list[list[float]], b: int, s2_floor: float = 0.0
) -> tuple[float, float, float, bool]:
    """H (recommended primary): analytic stratified WS t with the
    within-domain variance floor AND the pre-registered calibration
    inflation PHASE9_CI_INFLATION on the half-width."""
    theta, var, df = _ws_var_df(dv, s2_floor)
    if var <= 0.0:
        return theta, theta, theta, True
    hw = PHASE9_CI_INFLATION * student_t_ppf(0.975, df) * math.sqrt(var)
    return theta, theta - hw, theta + hw, False


def m_ws_floor_atanh(
    rng: random.Random | None, dv: list[list[float]], b: int, s2_floor: float = 0.0
) -> tuple[float, float, float, bool]:
    """J (Q2 large-effect variant): analytic stratified WS t with the
    variance floor and calibration inflation, computed on the atanh
    (Fisher) scale so the interval stays inside (-1, 1) and widens
    appropriately as |Delta| approaches the +/-1 ceiling. For Q2 only
    (Delta in [-1, 1]); for Q1 use H."""
    theta, var, df = _ws_var_df(dv, s2_floor)
    if var <= 0.0:
        return theta, theta, theta, True
    th = min(max(theta, -0.999999), 0.999999)
    g = math.atanh(th)
    se_g = math.sqrt(var) / (1.0 - th * th)  # delta method for atanh
    hw = PHASE9_CI_INFLATION * student_t_ppf(0.975, df) * se_g
    return theta, math.tanh(g - hw), math.tanh(g + hw), False


def _jackknife_theta(dv: list[list[float]]) -> list[float]:
    """Stratified leave-one-scenario-out equal-domain-weight means."""
    h_ = len(dv)
    ybar = [statistics.fmean(d) for d in dv]
    base = sum(ybar)
    out: list[float] = []
    for hi_, d in enumerate(dv):
        n = len(d)
        tot = sum(d)
        for j in range(n):
            new_mean = (tot - d[j]) / (n - 1)
            out.append((base - ybar[hi_] + new_mean) / h_)
    return out


def _bootstrap_pass(
    rng: random.Random, dv: list[list[float]], b: int, s2_floor: float
) -> tuple[list[float], list[float]]:
    """b domain-preserving resamples -> (theta* list, se* list). se* is the
    floored analytic stratified SE of the resample (used by bootstrap-t).
    Hot loop: no statistics.* calls, inline mean/variance."""
    choices = rng.choices
    h_ = len(dv)
    h2 = h_ * h_
    sizes = [len(d) for d in dv]
    sqrt = math.sqrt
    thetas: list[float] = []
    ses: list[float] = []
    for _ in range(b):
        sum_ybar = 0.0
        var = 0.0
        for k in range(h_):
            x = choices(dv[k], k=sizes[k])
            n = sizes[k]
            s = 0.0
            ss = 0.0
            for v in x:
                s += v
                ss += v * v
            sum_ybar += s / n
            s2 = (ss - s * s / n) / (n - 1) if n > 1 else 0.0
            if s2 < s2_floor:
                s2 = s2_floor
            var += s2 / (n * h2)
        thetas.append(sum_ybar / h_)
        ses.append(sqrt(var) if var > 0.0 else 0.0)
    return thetas, ses


def _pct(sorted_vals: list[float], q: float) -> float:
    n = len(sorted_vals)
    return sorted_vals[min(n - 1, max(0, int(q * n)))]


def bootstrap_intervals(
    rng: random.Random,
    dv: list[list[float]],
    b: int,
    s2_floor: float,
) -> dict[str, tuple[float, float, float, bool]]:
    """A / B / C from a single shared stratified-bootstrap pass."""
    theta_hat = statistics.fmean([statistics.fmean(d) for d in dv])
    thetas, ses = _bootstrap_pass(rng, dv, b, s2_floor)
    st = sorted(thetas)

    # A: percentile
    a = (theta_hat, _pct(st, 0.025), _pct(st, 0.975), False)

    # C: BCa (bias-correction z0 from boots, acceleration from stratified
    # leave-one-scenario-out jackknife)
    n_less = sum(1 for x in thetas if x < theta_hat)
    prop = min(max(n_less / b, 1.0 / b), 1.0 - 1.0 / b)
    z0 = _NORM.inv_cdf(prop)
    jack = _jackknife_theta(dv)
    jbar = statistics.fmean(jack)
    d2 = sum((jbar - x) ** 2 for x in jack)
    d3 = sum((jbar - x) ** 3 for x in jack)
    acc = d3 / (6.0 * d2**1.5) if d2 > 0.0 else 0.0

    def _bca_end(zq: float) -> float:
        num = z0 + zq
        return _NORM.cdf(z0 + num / (1.0 - acc * num))

    pl = _bca_end(_NORM.inv_cdf(0.025))
    pu = _bca_end(_NORM.inv_cdf(0.975))
    c = (theta_hat, _pct(st, pl), _pct(st, pu), not math.isfinite(acc))

    # B: studentized bootstrap-t (se_hat = floored analytic SE on the data)
    _, var_hat, _ = _ws_var_df(dv, s2_floor)
    se_hat = math.sqrt(var_hat) if var_hat > 0.0 else 0.0
    tstars = sorted((t - theta_hat) / s for t, s in zip(thetas, ses, strict=True) if s > 0.0)
    patho_b = (se_hat <= 0.0) or (len(tstars) < 0.5 * b)
    if patho_b or not tstars:
        bt = (theta_hat, theta_hat, theta_hat, True)
    else:
        q_lo = _pct(tstars, 0.025)
        q_hi = _pct(tstars, 0.975)
        bt = (theta_hat, theta_hat - q_hi * se_hat, theta_hat - q_lo * se_hat, False)

    return {"A_percentile": a, "B_boot_t": bt, "C_BCa": c}


def q1_methods(
    rng: random.Random, dv: list[list[float]], b: int
) -> dict[str, tuple[float, float, float, bool]]:
    theta_hat = statistics.fmean([statistics.fmean(d) for d in dv])
    r_eff = len(dv[0])
    s2_floor = max(theta_hat * (1.0 - theta_hat), 1e-6) / r_eff
    out = bootstrap_intervals(rng, dv, b, s2_floor)
    out["D_analytic_WS"] = m_analytic_ws(None, dv, b, 0.0)
    out["E_analytic_WS_floor"] = m_analytic_ws_floor(None, dv, b, s2_floor)
    out["F_analytic_logit"] = m_analytic_ws_logit(None, dv, b, s2_floor)
    out["G_domain_t"] = m_domain_t(None, dv, b, 0.0)
    out["H_WS_floor_inflated"] = m_ws_floor_inflated(None, dv, b, s2_floor)
    return out


def q2_methods(
    rng: random.Random,
    dv_diff: list[list[float]],
    b: int,
    mean_n: float,
    mean_p: float,
) -> dict[str, tuple[float, float, float, bool]]:
    r_eff = len(dv_diff[0])
    s2_floor = (mean_n * (1.0 - mean_n) + mean_p * (1.0 - mean_p)) / r_eff
    out = bootstrap_intervals(rng, dv_diff, b, s2_floor)
    out["D_analytic_WS"] = m_analytic_ws(None, dv_diff, b, 0.0)
    out["E_analytic_WS_floor"] = m_analytic_ws_floor(None, dv_diff, b, s2_floor)
    out["G_domain_t"] = m_domain_t(None, dv_diff, b, 0.0)
    out["H_WS_floor_inflated"] = m_ws_floor_inflated(None, dv_diff, b, s2_floor)
    out["J_WS_floor_atanh"] = m_ws_floor_atanh(None, dv_diff, b, s2_floor)
    return out


@dataclass
class CalibRow:
    quantity: str
    method: str
    dgp: str
    truth: float
    coverage: float
    mean_width: float
    op_char: float  # Q1: P(correct+confident); Q2: P(CI excludes 0)
    p_unresolved: float  # Q1 only
    pathology: float


def simulate_calibration_q1(
    n_sim: int, b: int, design: tuple[int, int] = CALIB_DESIGN
) -> list[CalibRow]:
    s, r = design
    per_domain = s // DOMAINS
    rows: list[CalibRow] = []
    method_names = list(q1_methods(_rng("probe"), [[0.4] * per_domain for _ in range(DOMAINS)], 8))
    for dgp, regime in _dgp_combos():
        label = "mixture" if dgp == "mixture" else f"2beta/{regime}"
        for mu in CALIB_Q1_MU:
            want = truth_label(mu)
            near_edge = min(abs(mu - BAND_LOW), abs(mu - BAND_HIGH)) < 0.03
            agg: dict[str, list[float]] = {m: [0.0, 0.0, 0.0, 0.0, 0.0] for m in method_names}
            # [cover, width, correct+confident, unresolved, pathology]
            gen = _rng("calib-q1-gen", design, dgp, regime, mu)
            for i in range(n_sim):
                dv = _draw_domain_rates(gen, dgp, regime, mu, per_domain, r)
                mrng = _rng("calib-q1-boot", design, dgp, regime, mu, i)
                res = q1_methods(mrng, dv, b)
                for name, (_pt, lo, hi, patho) in res.items():
                    a = agg[name]
                    a[0] += 1.0 if (lo <= mu <= hi) else 0.0
                    a[1] += hi - lo
                    cls = classify_q1(lo, hi)
                    if cls == want or (cls == "unresolved" and near_edge):
                        a[2] += 1.0
                    if cls == "unresolved":
                        a[3] += 1.0
                    a[4] += 1.0 if patho else 0.0
            for name in method_names:
                cov, wid, ok, unr, pat = (v / n_sim for v in agg[name])
                rows.append(CalibRow("Q1", name, label, mu, cov, wid, ok, unr, pat))
    return rows


def simulate_calibration_q2(
    n_sim: int, b: int, design: tuple[int, int] = CALIB_DESIGN
) -> list[CalibRow]:
    s, r = design
    per_domain = s // DOMAINS
    base_mu = 0.45
    kd, kw = TWOBETA_REGIMES["dom.mod/scn.mod"]
    rows: list[CalibRow] = []
    probe = q2_methods(
        _rng("probe2"),
        [[0.0] * per_domain for _ in range(DOMAINS)],
        8,
        0.4,
        0.4,
    )
    method_names = list(probe)
    for esd in CALIB_Q2_EFFECT_SD:
        for delta in CALIB_Q2_DELTA:
            agg: dict[str, list[float]] = {m: [0.0, 0.0, 0.0, 0.0, 0.0] for m in method_names}
            # [cover, width, detect, 0, pathology]
            gen = _rng("calib-q2-gen", design, esd, delta)
            for i in range(n_sim):
                p_n = probs_2beta(gen, base_mu, kd, kw, per_domain)
                dv_diff: list[list[float]] = []
                n_rates: list[float] = []
                p_rates: list[float] = []
                for row in p_n:
                    drow: list[float] = []
                    for p in row:
                        p_p = _clip01(p + gen.gauss(delta, esd))
                        kn = draw_rate(gen, p, r)
                        kp = draw_rate(gen, p_p, r)
                        drow.append(kp - kn)
                        n_rates.append(kn)
                        p_rates.append(kp)
                    dv_diff.append(drow)
                mean_n = statistics.fmean(n_rates)
                mean_p = statistics.fmean(p_rates)
                mrng = _rng("calib-q2-boot", design, esd, delta, i)
                res = q2_methods(mrng, dv_diff, b, mean_n, mean_p)
                for name, (_pt, lo, hi, patho) in res.items():
                    a = agg[name]
                    a[0] += 1.0 if (lo <= delta <= hi) else 0.0
                    a[1] += hi - lo
                    a[2] += 1.0 if (lo > 0.0 or hi < 0.0) else 0.0
                    a[4] += 1.0 if patho else 0.0
            for name in method_names:
                cov, wid, det, _z, pat = (v / n_sim for v in agg[name])
                rows.append(
                    CalibRow("Q2", name, f"effect-SD {esd}", delta, cov, wid, det, 0.0, pat)
                )
    return rows


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
    print("    PRIMARY Q1 interval = method G: t on the 8 domain means (df=7)")
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
    print("    PRIMARY Q2 interval = method E: stratified WS-t on per-domain")
    print("    mean paired diff + within-domain binomial variance floor")
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


def _cov_flag(c: float) -> str:
    if c < 0.90:
        return "!!"  # material undercoverage
    if c < COVERAGE_TARGET_LO:
        return "!"  # mild undercoverage
    if c > 0.99:
        return "++"  # heavy overcoverage
    if c > COVERAGE_TARGET_HI:
        return "+"  # mild overcoverage
    return ""  # in target [0.93, 0.97]


def _short(method: str) -> str:
    return method.split("_")[0]


def print_calibration(q1: list[CalibRow], q2: list[CalibRow]) -> str:
    methods_q1 = list(dict.fromkeys(r.method for r in q1))
    methods_q2 = list(dict.fromkeys(r.method for r in q2))
    dgps_q1 = list(dict.fromkeys(r.dgp for r in q1))
    q1x = {(r.dgp, r.method, round(r.truth, 4)): r for r in q1}
    q2x = {(r.dgp, r.method, round(r.truth, 4)): r for r in q2}
    rep: list[str] = []

    def _tbl(title: str, hdr: str) -> None:
        rep.append("\n" + title)
        rep.append(hdr)

    rep.append("=" * 96)
    rep.append("Q1 CI CALIBRATION -- empirical coverage of the nominal-95% interval for theta")
    rep.append(
        f"  central region {CALIB_Q1_CENTRAL}; target {COVERAGE_TARGET_LO:.2f}-"
        f"{COVERAGE_TARGET_HI:.2f}.  flags: ! <0.93  !! <0.90  + >0.97  ++ >0.99"
    )
    rep.append("=" * 96)
    h1 = f"{'dgp':>22} {'theta':>6} " + "".join(f"{_short(m):>9}" for m in methods_q1)

    _tbl("-- coverage --", h1)
    for dgp in dgps_q1:
        for mu in CALIB_Q1_MU:
            cells = "".join(
                f"{q1x[dgp, m, round(mu, 4)].coverage:>6.2f}"
                f"{_cov_flag(q1x[dgp, m, round(mu, 4)].coverage):<3}"
                for m in methods_q1
            )
            rep.append(f"{dgp:>22} {mu:>6.3f} {cells}")

    _tbl("-- mean interval width --", h1)
    for dgp in dgps_q1:
        for mu in CALIB_Q1_MU:
            cells = "".join(f"{q1x[dgp, m, round(mu, 4)].mean_width:>9.3f}" for m in methods_q1)
            rep.append(f"{dgp:>22} {mu:>6.3f} {cells}")

    _tbl(
        "-- Q1 classification: P(correct + confident verdict), worst over DGP --",
        f"{'theta':>10} " + "".join(f"{_short(m):>9}" for m in methods_q1),
    )
    for mu in CALIB_Q1_MU:
        cells = "".join(
            f"{min(q1x[d, m, round(mu, 4)].op_char for d in dgps_q1):>9.2f}" for m in methods_q1
        )
        rep.append(f"{mu:>10.3f} {cells}")

    rep.append("\n-- Q1 pathology rate (degenerate / no interval), worst over cells --")
    for m in methods_q1:
        rep.append(f"  {m:<22} {max(r.pathology for r in q1 if r.method == m):>6.3f}")

    rep.append("\n" + "=" * 96)
    rep.append(
        "Q2 CI CALIBRATION -- empirical coverage of the nominal-95% interval for Delta = P-N"
    )
    rep.append(
        f"  central region {CALIB_Q2_CENTRAL}; target {COVERAGE_TARGET_LO:.2f}-"
        f"{COVERAGE_TARGET_HI:.2f}"
    )
    rep.append("=" * 96)
    dgps_q2 = [f"effect-SD {e}" for e in CALIB_Q2_EFFECT_SD]
    h2 = f"{'effect-SD':>12} {'delta':>6} " + "".join(f"{_short(m):>9}" for m in methods_q2)

    _tbl("-- coverage --", h2)
    for e in CALIB_Q2_EFFECT_SD:
        for delta in CALIB_Q2_DELTA:
            key = f"effect-SD {e}"
            cells = "".join(
                f"{q2x[key, m, round(delta, 4)].coverage:>6.2f}"
                f"{_cov_flag(q2x[key, m, round(delta, 4)].coverage):<3}"
                for m in methods_q2
            )
            rep.append(f"{'effect-SD ' + str(e):>12} {delta:>6.2f} {cells}")

    _tbl("-- mean interval width --", h2)
    for e in CALIB_Q2_EFFECT_SD:
        for delta in CALIB_Q2_DELTA:
            key = f"effect-SD {e}"
            cells = "".join(f"{q2x[key, m, round(delta, 4)].mean_width:>9.3f}" for m in methods_q2)
            rep.append(f"{'effect-SD ' + str(e):>12} {delta:>6.2f} {cells}")

    _tbl("-- Q2 detection: P(95% CI excludes 0) --", h2)
    for e in CALIB_Q2_EFFECT_SD:
        for delta in CALIB_Q2_DELTA:
            key = f"effect-SD {e}"
            cells = "".join(f"{q2x[key, m, round(delta, 4)].op_char:>9.2f}" for m in methods_q2)
            rep.append(f"{'effect-SD ' + str(e):>12} {delta:>6.2f} {cells}")

    rep.append("\n-- Q2 pathology rate, worst over cells --")
    for m in methods_q2:
        rep.append(f"  {m:<22} {max(r.pathology for r in q2 if r.method == m):>6.3f}")
    _ = dgps_q2

    rep.append("\n" + "=" * 96)
    rep.append(
        "CENTRAL-REGION CALIBRATION VERDICT (coverage over the central truth grid, all DGPs)"
    )
    rep.append("=" * 96)
    rep.append(
        f"{'method':>22} {'Q1 min':>8} {'Q1 mean':>9} {'Q2 min':>8} {'Q2 mean':>9}  assessment"
    )
    for m in methods_q1:
        q1c = [
            r.coverage
            for r in q1
            if r.method == m and any(abs(r.truth - t) < 1e-9 for t in CALIB_Q1_CENTRAL)
        ]
        q2c = [
            r.coverage
            for r in q2
            if r.method == m and any(abs(r.truth - t) < 1e-9 for t in CALIB_Q2_CENTRAL)
        ]
        q1min, q1mean = min(q1c), sum(q1c) / len(q1c)
        has_q2 = bool(q2c)
        q2min = min(q2c) if has_q2 else float("nan")
        q2mean = (sum(q2c) / len(q2c)) if has_q2 else float("nan")
        lo_ok = q1min >= COVERAGE_TARGET_LO and (not has_q2 or q2min >= COVERAGE_TARGET_LO)
        if q1min < 0.90 or (has_q2 and q2min < 0.90):
            note = "MATERIAL UNDERCOVERAGE -> reject"
        elif lo_ok:
            note = "meets >= 0.93 across the central region"
        elif q1min >= 0.915 and (not has_q2 or q2min >= 0.915):
            note = "borderline (0.92-0.93) -- conservative elsewhere?"
        else:
            note = "mild undercoverage"
        q2min_s = "     n/a" if not has_q2 else f"{q2min:>8.2f}"
        q2mean_s = "      n/a" if not has_q2 else f"{q2mean:>9.2f}"
        rep.append(f"{m:>22} {q1min:>8.2f} {q1mean:>9.2f} {q2min_s} {q2mean_s}  {note}")

    # per-quantity recommendation: highest central-region min coverage that
    # does not overcover on average past ~0.98 (prefer mild overcoverage to
    # undercoverage, but not a wildly wide interval).
    def _q_central_min(rows: list[CalibRow], method: str, central: tuple[float, ...]) -> float:
        vals = [
            r.coverage
            for r in rows
            if r.method == method and any(abs(r.truth - t) < 1e-9 for t in central)
        ]
        return min(vals) if vals else 0.0

    def _q_central_mean(rows: list[CalibRow], method: str, central: tuple[float, ...]) -> float:
        vals = [
            r.coverage
            for r in rows
            if r.method == method and any(abs(r.truth - t) < 1e-9 for t in central)
        ]
        return sum(vals) / len(vals) if vals else 0.0

    def _rank_key(rows: list[CalibRow], m: str, central: tuple[float, ...]) -> tuple[int, float]:
        """Primary: does the method meet BOTH central-region criteria --
        min coverage >= target-lo (0.93) AND mean coverage not past ~0.975
        (i.e. not needlessly wide)?  Among methods that do, prefer the one
        whose mean sits closest to 0.95.  Among methods that do not, fall
        back to the least-bad central min.  Prefer mild overcoverage to
        undercoverage."""
        cmin = _q_central_min(rows, m, central)
        cmean = _q_central_mean(rows, m, central)
        meets = 1 if (cmin >= COVERAGE_TARGET_LO and cmean <= 0.978) else 0
        return (meets, -abs(cmean - 0.95) if meets else cmin)

    q1_rank = sorted(methods_q1, key=lambda m: _rank_key(q1, m, CALIB_Q1_CENTRAL), reverse=True)
    q2_rank = sorted(methods_q2, key=lambda m: _rank_key(q2, m, CALIB_Q2_CENTRAL), reverse=True)
    rep.append("\n" + "=" * 96)
    rep.append("PER-QUANTITY RECOMMENDATION (best central-region calibration)")
    rep.append("=" * 96)
    rep.append(
        f"  Q1 -> {q1_rank[0]}   central min "
        f"{_q_central_min(q1, q1_rank[0], CALIB_Q1_CENTRAL):.2f}, mean "
        f"{_q_central_mean(q1, q1_rank[0], CALIB_Q1_CENTRAL):.2f}"
    )
    rep.append(
        f"  Q2 -> {q2_rank[0]}   central min "
        f"{_q_central_min(q2, q2_rank[0], CALIB_Q2_CENTRAL):.2f}, mean "
        f"{_q_central_mean(q2, q2_rank[0], CALIB_Q2_CENTRAL):.2f}"
    )
    rep.append(
        "  (delta = 0.50 near the +/-1 ceiling is outside the central region;\n"
        "   NO method reaches 0.90 coverage there -- see the delta=0.50 rows.)"
    )
    return "\n".join(rep)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="small n_sim/B for CI/tests")
    ap.add_argument(
        "--ci-stability",
        action="store_true",
        help="only run the bootstrap-B stability sweep",
    )
    ap.add_argument(
        "--calibrate",
        action="store_true",
        help="only run the interval-method calibration comparison",
    )
    ap.add_argument(
        "--calibrate-designs",
        action="store_true",
        help="spot-check the chosen-method coverage across 32x5/40x4/40x5/40x6",
    )
    args = ap.parse_args()

    if args.calibrate:
        n_sim, b = (40, 250) if args.fast else (400, 1200)
        print(
            f"Phase 9 CI calibration  (SEED={SEED}, design={_fmt_design(CALIB_DESIGN)}, "
            f"n_sim={n_sim}, B={b}, domains={DOMAINS})"
        )
        q1c = simulate_calibration_q1(n_sim, b)
        q2c = simulate_calibration_q2(n_sim, b)
        print(print_calibration(q1c, q2c))
        return 0

    if args.calibrate_designs:
        n_sim = 250 if args.fast else 1500
        print(
            f"Phase 9 chosen-method coverage vs design  (SEED={SEED}, n_sim={n_sim})\n"
            "  Q1 method G (domain-level t);  Q2 method E (stratified WS-t + floor).\n"
            "  Coverage of the nominal-95% interval, worst over the 3 DGP regimes,\n"
            "  at the central truth grid.  target 0.93-0.97.\n"
        )
        designs = ((32, 5), (40, 4), (40, 5), (40, 6))
        print(f"{'quantity':>9} {'truth':>7} " + "".join(f"{_fmt_design(d):>8}" for d in designs))
        for mu in CALIB_Q1_CENTRAL:
            cells = ""
            for d in designs:
                s, r = d
                pd = s // DOMAINS
                worst = 1.0
                for dgp, regime in _dgp_combos():
                    gen = _rng("cd-q1", d, dgp, regime, mu)
                    cov = 0
                    for _ in range(n_sim):
                        dv = _draw_domain_rates(gen, dgp, regime, mu, pd, r)
                        _p, lo, hi, _pa = m_domain_t(None, dv, 0)
                        cov += 1 if lo <= mu <= hi else 0
                    worst = min(worst, cov / n_sim)
                cells += f"{worst:>8.2f}"
            print(f"{'Q1':>9} {mu:>7.3f} {cells}")
        kd, kw = TWOBETA_REGIMES["dom.mod/scn.mod"]
        for delta in CALIB_Q2_CENTRAL:
            cells = ""
            for d in designs:
                s, r = d
                pd = s // DOMAINS
                worst = 1.0
                for esd in CALIB_Q2_EFFECT_SD:
                    gen = _rng("cd-q2", d, esd, delta)
                    cov = 0
                    for _ in range(n_sim):
                        p_n = probs_2beta(gen, 0.45, kd, kw, pd)
                        diffs: list[list[float]] = []
                        nr: list[float] = []
                        pr: list[float] = []
                        for rowp in p_n:
                            drow: list[float] = []
                            for p in rowp:
                                pp = _clip01(p + gen.gauss(delta, esd))
                                kn = draw_rate(gen, p, r)
                                kp = draw_rate(gen, pp, r)
                                drow.append(kp - kn)
                                nr.append(kn)
                                pr.append(kp)
                            diffs.append(drow)
                        mn = statistics.fmean(nr)
                        mp = statistics.fmean(pr)
                        fl = (mn * (1 - mn) + mp * (1 - mp)) / r
                        _p, lo, hi, _pa = m_analytic_ws_floor(None, diffs, 0, fl)
                        cov += 1 if lo <= delta <= hi else 0
                    worst = min(worst, cov / n_sim)
                cells += f"{worst:>8.2f}"
            print(f"{'Q2':>9} {delta:>7.3f} {cells}")
        return 0

    if args.ci_stability:
        import json

        res = ci_stability()
        print(json.dumps(res, indent=2))
        drifts = [v["max_drift_B>=2000"] for v in res.values()]
        print(f"\nmax CI-bound drift for B >= 2000: {max(drifts):.4f}")
        print("PASS" if max(drifts) < 0.012 else "FAIL")
        return 0 if max(drifts) < 0.012 else 1

    n_sim = 40 if args.fast else 300

    print(
        f"Phase 9 design simulation  (SEED={SEED}, n_sim={n_sim}, domains={DOMAINS}; "
        "Q1 interval=method G, Q2 interval=method E -- both analytic)"
    )
    _designs = " ".join(_fmt_design(x) for x in CANDIDATE_DESIGNS)
    print(f"band = [{BAND_LOW}, {BAND_HIGH}]   designs = {_designs}")

    q1 = simulate_q1(n_sim)
    q2 = simulate_q2(n_sim)
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
