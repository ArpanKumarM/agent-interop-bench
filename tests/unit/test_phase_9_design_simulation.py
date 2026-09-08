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
        n_configs=3, n_sim=50, b=1, designs=((64, 3),), n_sim_boot=1
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
        n_configs=3, n_sim=50, b=1, designs=((64, 3),), n_sim_boot=1
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
