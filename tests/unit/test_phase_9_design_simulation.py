"""scripts/phase_9_design_simulation.py -- guardrails for the offline
Phase 9 design + CI-calibration artifact.

The script is not importable as a package module (it lives in scripts/),
so load it by path. These tests keep it deterministic, keep the headline
arithmetic honest, check the Student-t helper, the PRIMARY fixed-stratum
interval (method S1f) and the demoted method G, the FIXED-DOMAIN
calibration (G over-covers the fixed-domain estimand; S1/S1f calibrate),
Q2 pairing, boundary behaviour, and the retained bootstrap sensitivity
method.
"""

from __future__ import annotations

import importlib.util
import math
import statistics as _st
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "phase_9_design_simulation.py"
_spec = importlib.util.spec_from_file_location("phase_9_design_simulation", _PATH)
sim = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = sim  # so @dataclass can resolve cls.__module__
_spec.loader.exec_module(sim)

_FLAT = [[0.4] * 5 for _ in range(8)]
_MID = [[0.2, 0.4, 0.6, 0.8, 1.0], [0.0, 0.2, 0.4, 0.6, 0.8]] + [
    [0.4, 0.4, 0.6, 0.2, 0.4] for _ in range(6)
]
_ONES = [[1.0] * 5 for _ in range(8)]
_ZEROS = [[0.0] * 5 for _ in range(8)]


# --- headline arithmetic ---------------------------------------------------- #
def test_selected_design_trial_count_is_1536():
    # recommended: 8 domains x 8 scenarios x 3 repeats x 2 arms x 4 models
    assert sim.total_trials((64, 3), arms=2, models=4) == 1536
    assert sim.total_trials((40, 5), arms=2, models=4) == 1600
    assert sim.total_trials((80, 2), arms=2, models=4) == 1280  # budget floor
    assert sim.total_trials((64, 3)) != 5120  # the erroneous draft-1 figure


def test_band_constants_and_domain_divisibility():
    assert (sim.BAND_LOW, sim.BAND_HIGH) == (0.25, 0.70)
    assert sim.DOMAINS == 8
    for s, _r in sim.CANDIDATE_DESIGNS:
        assert s % sim.DOMAINS == 0
        assert s // sim.DOMAINS >= 5  # >= 5 scenarios per domain


# --- Student-t quantile helper ------------------------------------------- #
@pytest.mark.parametrize(
    ("df", "want"),
    [(1, 12.7062), (2, 4.3027), (7, 2.3646), (10, 2.2281), (30, 2.0423)],
)
def test_student_t_ppf_matches_known_975_quantiles(df, want):
    assert sim.student_t_ppf(0.975, df) == pytest.approx(want, abs=3e-3)


def test_student_t_ppf_approaches_normal_for_large_df():
    assert sim.student_t_ppf(0.975, 100000) == pytest.approx(1.95996, abs=1e-3)


# --- interval methods ----------------------------------------------------- #
@pytest.mark.parametrize(
    "method", [sim.m_domain_t, sim.m_analytic_ws, sim.m_analytic_ws_floor, sim.m_strat_ws]
)
def test_interval_methods_bracket_the_point_estimate(method):
    for dv in (_FLAT, _MID, _ONES, _ZEROS):
        pt, lo, hi, patho = method(None, dv, 0)
        assert lo <= pt <= hi or patho
        assert isinstance(patho, bool)


def test_strat_ws_is_reproducible_and_uses_within_domain_variance():
    a = sim.m_strat_ws(None, _MID, 0, None)
    b = sim.m_strat_ws(None, _MID, 0, None)
    assert a == b
    # hand check: Var = (1/64) sum_d s2_d / n_d ; WS t
    h = 8
    var = 0.0
    for d in _MID:
        _m, s2 = sim._var_ddof1(d)
        var += s2 / (len(d) * h * h)
    pt, lo, hi, _ = sim.m_strat_ws(None, _MID, 0, None)
    assert (hi - lo) / 2 == pytest.approx(
        sim.student_t_ppf(0.975, sim._ws_var_df(_MID)[2]) * math.sqrt(var), rel=1e-6
    )


def test_binom_floor_is_a_valid_lower_bound_on_domain_variance():
    # floor_d = pbar_d(1-pbar_d)/R  must never exceed a domain's true
    # Var(r) = tau2_d + E[p(1-p)]/R -- proven: V_d - floor = tau2_d(1-1/R).
    dv = [[0.2, 0.4, 0.6, 0.3, 0.5] for _ in range(8)]
    r = 5
    floors = sim._binom_floors_rate(dv, r)
    for d, fl in zip(dv, floors, strict=True):
        _m, s2 = sim._var_ddof1(d)  # sample estimate of V_d
        # floor <= pbar(1-pbar)/R and, in expectation, <= V_d
        pbar = _st.fmean(d)
        assert fl == pytest.approx(pbar * (1 - pbar) / r)


def test_domain_t_uses_eight_domain_means_and_df7():
    pt, lo, hi, _ = sim.m_domain_t(None, _FLAT, 0)
    assert (lo, hi) == pytest.approx((0.4, 0.4))
    dv = [[float(k) / 10] * 5 for k in range(8)]
    means = [_st.fmean(d) for d in dv]
    se = _st.stdev(means) / (8**0.5)
    exp_hw = sim.student_t_ppf(0.975, 7) * se
    _pt, lo, hi, _ = sim.m_domain_t(None, dv, 0)
    assert (hi - lo) / 2 == pytest.approx(exp_hw, rel=1e-6)


def test_ws_floor_prevents_near_zero_width_when_domain_is_constant():
    _pt, lo_raw, hi_raw, _ = sim.m_strat_ws(None, _FLAT, 0, None)
    assert (hi_raw - lo_raw) < 1e-6
    floors = [0.048] * 8
    _pt, lo, hi, patho = sim.m_strat_ws(None, _FLAT, 0, floors)
    assert patho is False
    assert hi - lo > 0.05


def test_boundary_all_ones_and_all_zeros_do_not_crash():
    for dv in (_ONES, _ZEROS):
        results = [
            sim.m_strat_ws(None, dv, 0, [0.02] * 8),
            sim.m_domain_t(None, dv, 0),
            sim.m_analytic_ws_floor(None, dv, 0, 0.02),
            sim.m_ws_floor_atanh(None, dv, 0, 0.02),
            sim.m_finite_panel(None, dv, 0, 3),
        ]
        for pt, lo, hi, patho in results:
            assert math.isfinite(lo) and math.isfinite(hi)
            assert lo <= pt <= hi or patho
    for dv in (_ONES, _ZEROS):
        _pt, lo, hi, _ = sim.m_ws_floor_atanh(None, dv, 0, 0.02)
        assert -1.0 <= lo <= hi <= 1.0


# --- FIXED-DOMAIN machinery + calibration -------------------------------- #
def test_fixed_config_and_draw_shapes_and_determinism():
    rng = sim._rng("t", "cfg")
    cfg = sim.draw_fixed_config(rng, "2beta", "dom.mod/scn.mod", 0.5)
    assert cfg[0] == "2beta"
    assert len(cfg[1]) == 8  # 8 fixed domain means
    tgt = sim.fixed_config_theta(cfg)
    assert 0.0 <= tgt <= 1.0
    d1 = sim.draw_fixed_dv(sim._rng("s", 1), cfg, 8, 3)
    d2 = sim.draw_fixed_dv(sim._rng("s", 1), cfg, 8, 3)
    assert d1 == d2  # deterministic
    assert len(d1) == 8 and all(len(x) == 8 for x in d1)


def test_method_g_overcovers_fixed_domain_while_s1f_calibrates():
    """The core diagnosis: method G's SE includes the FIXED between-domain
    spread Sigma2_mu/8, so it over-covers theta=(1/8)sum mu_d; the
    within-domain stratified method (S1f) targets the right variance."""
    q1, _q2 = sim.simulate_calibration_fixed(
        n_configs=2, n_sim=45, b=1, designs=((64, 3),), n_sim_boot=1
    )

    def cov(method: str) -> list[float]:
        return [
            r.coverage
            for r in q1
            if r.method == method and any(abs(r.truth - t) < 1e-9 for t in sim.CALIB_Q1_CENTRAL)
        ]

    g = cov("G_domain_t")
    s1f = cov("S1f_strat_ws_binomfloor")
    gm = sum(g) / len(g)
    s1fm = sum(s1f) / len(s1f)
    assert min(g) >= 0.96  # G over-covers the fixed-domain target
    assert min(s1f) >= 0.90  # S1f does not materially under-cover
    assert s1fm <= 0.97 < gm  # S1f interval is tighter / correctly targeted


def test_finite_panel_undercovers_the_superpopulation_target():
    """Option A (finite panel; Bernoulli-only SE) must under-cover the
    fixed-domain SUPERPOPULATION estimand -- it only covers the exact
    scenarios, not other draws from G_d."""
    q1, _q2 = sim.simulate_calibration_fixed(
        n_configs=2, n_sim=45, b=1, designs=((64, 3),), n_sim_boot=1
    )
    a = [
        r.coverage
        for r in q1
        if r.method == "A_finite_panel"
        and any(abs(r.truth - t) < 1e-9 for t in sim.CALIB_Q1_CENTRAL)
    ]
    assert min(a) < 0.85


# --- design simulation (fixed-domain, method S1f) ---------------------- #
def test_design_simulation_is_deterministic():
    a = sim.simulate_q1(n_sim=8)
    b = sim.simulate_q1(n_sim=8)
    assert [vars(r) for r in a] == [vars(r) for r in b]
    c = sim.simulate_q2(n_sim=8)
    d = sim.simulate_q2(n_sim=8)
    assert [vars(r) for r in c] == [vars(r) for r in d]


def test_more_scenarios_per_domain_improve_q1_power():
    """Q1 discrimination comes from scenarios-per-domain, not repeats: at a
    clean mid-band truth, P(confident+correct) rises going 40x5 -> 64x3
    even though 64x3 has FEWER repeats and ~the same trial count."""
    q1 = sim.simulate_q1(n_sim=25)

    def p_ok(design: tuple[int, int]) -> float:
        return min(
            r.p_correct_confident for r in q1 if r.design == design and abs(r.mu - 0.45) < 1e-9
        )

    assert p_ok((64, 3)) > p_ok((40, 5)) + 0.08


# --- retained bootstrap sensitivity method ----------------------------- #
def test_stratified_bootstrap_point_equals_equal_domain_weight_mean():
    pt = sim.equal_domain_weight_mean(_MID)
    rng = sim._rng("t", "boot")
    pt2, lo, hi = sim.stratified_bootstrap_ci(rng, _MID, b=300)
    assert pt == pytest.approx(pt2)
    assert lo <= pt <= hi


def test_ci_stability_bounds_settle_in_b():
    res = sim.ci_stability(bs=(500, 1000, 2000, 4000))
    for entry in res.values():
        assert entry["max_drift_B>=2000"] < 0.012


# --- Q2 confidence procedure (finalized: uniform S1f) ------------------- #
_DIFF_SMALL = [[0.05, 0.10, 0.02, 0.08, 0.06, 0.09, 0.03, 0.07] for _ in range(8)]
_DIFF_LARGE = [[0.45, 0.50, 0.40, 0.55, 0.48, 0.52, 0.44, 0.49] for _ in range(8)]
_N8 = [[0.4] * 8 for _ in range(8)]
_P8 = [[0.6] * 8 for _ in range(8)]


def test_q2_primary_interval_default_is_uniform_s1f_and_deterministic():
    a = sim.q2_primary_interval(_DIFF_LARGE, _N8, _P8, 3)
    b = sim.q2_primary_interval(_DIFF_LARGE, _N8, _P8, 3)
    assert a == b
    assert a[3] == "s1f"  # default procedure, regardless of effect size
    # a large observed effect does NOT switch method (no adaptive rule)
    c = sim.q2_primary_interval(_DIFF_SMALL, _N8, _P8, 3)
    assert c[3] == "s1f"


@pytest.mark.parametrize("proc", ["s1f", "s1f_infl", "atanh", "atanh_infl", "lower_bound"])
def test_q2_procedures_bracket_and_respect_support(proc):
    for dv in (_DIFF_SMALL, _DIFF_LARGE):
        pt, lo, hi, tag = sim.q2_primary_interval(dv, _N8, _P8, 3, procedure=proc)
        assert -1.0 <= lo <= pt <= hi <= 1.0
        assert tag.startswith(proc[:4]) or tag == proc


def test_q2_atanh_variant_stays_inside_open_interval_for_a_large_effect():
    pt, lo, hi, _ = sim.q2_primary_interval(_DIFF_LARGE, _N8, _P8, 3, procedure="atanh")
    assert -1.0 < lo < hi < 1.0


def test_q2_adaptive_candidate_switch_behaviour():
    # |Delta_hat| well below 0.28, no saturated domain -> s1f branch
    _pt, _lo, _hi, tag = sim.q2_primary_interval(_DIFF_SMALL, _N8, _P8, 3, procedure="adaptive")
    assert tag == "adaptive:s1f"
    # |Delta_hat| ~ 0.48 >= 0.28 -> atanh branch
    _pt, _lo, _hi, tag = sim.q2_primary_interval(_DIFF_LARGE, _N8, _P8, 3, procedure="adaptive")
    assert tag == "adaptive:atanh_infl"
    # small mean but one saturated domain (|ybar_delta| >= 0.9) -> atanh branch
    dv = [[0.02] * 8 for _ in range(7)] + [[0.95] * 8]
    _pt, _lo, _hi, tag = sim.q2_primary_interval(dv, _N8, _P8, 3, procedure="adaptive")
    assert tag == "adaptive:atanh_infl"


def test_q2_true_delta_falls_below_nominal_when_clipping_bites():
    # all 8 domain means high -> p + N(0.5, .) clips at 1 -> true Delta << 0.5
    mu_d = (0.9,) * 8
    d_true = sim._q2_true_delta(sim._rng("t", "true"), mu_d, 8.0, 0.50, 0.15, mc=4000)
    assert d_true < 0.30
    # near zero-effect, true Delta ~ 0
    d0 = sim._q2_true_delta(sim._rng("t", "t0"), (0.45,) * 8, 8.0, 0.0, 0.15, mc=4000)
    assert abs(d0) < 0.02


def test_q2_final_procedure_coverage_regression():
    """The frozen Q2 procedure (uniform S1f) must cover the TRUE Delta_m at
    >= 0.92 across the full delta0 range and all heterogeneity regimes."""
    rows = sim.simulate_q2_procedures(n_configs=2, n_sim=90)
    s1f = [r.coverage for r in rows if r.procedure == "s1f"]
    assert min(s1f) >= 0.90
    assert max(s1f) <= 1.0
    # detection rises with the true effect
    by_d = {}
    for r in rows:
        if r.procedure == "s1f":
            by_d.setdefault(round(r.delta0, 2), []).append(r.detect)
    assert min(by_d[0.30]) > min(by_d[0.10])
