"""scripts/phase_9_design_simulation.py -- guardrails for the offline
Phase 9 design + CI-calibration artifact.

The script is not importable as a package module (it lives in scripts/),
so load it by path. These tests keep it deterministic, keep the headline
arithmetic honest, check the Student-t helper and the two PRIMARY analytic
interval procedures (method G for Q1, method E for Q2), the domain-
preserving resampling of the retained bootstrap sensitivity method, Q2
pair preservation, boundary cases near 0/1, and the calibration
recommendation.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "phase_9_design_simulation.py"
_spec = importlib.util.spec_from_file_location("phase_9_design_simulation", _PATH)
sim = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules[_spec.name] = sim  # so @dataclass can resolve cls.__module__
_spec.loader.exec_module(sim)

_FLAT = [[0.4, 0.4, 0.4, 0.4, 0.4] for _ in range(8)]
_MID = [[0.2, 0.4, 0.6, 0.8, 1.0], [0.0, 0.2, 0.4, 0.6, 0.8]] + [
    [0.4, 0.4, 0.6, 0.2, 0.4] for _ in range(6)
]
_ONES = [[1.0] * 5 for _ in range(8)]
_ZEROS = [[0.0] * 5 for _ in range(8)]


def test_selected_design_trial_count_is_1600():
    assert sim.total_trials((40, 5), arms=2, models=4) == 1600
    assert sim.total_trials((40, 4), arms=2, models=4) == 1280  # budget fallback
    assert sim.total_trials((40, 5)) != 5120  # the erroneous draft-1 figure


def test_band_constants_and_domains():
    assert (sim.BAND_LOW, sim.BAND_HIGH) == (0.25, 0.70)
    assert sim.DOMAINS == 8
    for s, _r in sim.CANDIDATE_DESIGNS:
        assert s % sim.DOMAINS == 0


# --- Student-t quantile helper ------------------------------------------- #
@pytest.mark.parametrize(
    ("df", "want"),
    [(1, 12.7062), (2, 4.3027), (7, 2.3646), (10, 2.2281), (30, 2.0423)],
)
def test_student_t_ppf_matches_known_975_quantiles(df, want):
    assert sim.student_t_ppf(0.975, df) == pytest.approx(want, abs=2e-3)


def test_student_t_ppf_approaches_normal_for_large_df():
    assert sim.student_t_ppf(0.975, 100000) == pytest.approx(1.95996, abs=1e-3)


# --- primary interval methods ----------------------------------------------- #
@pytest.mark.parametrize("method", [sim.m_domain_t, sim.m_analytic_ws, sim.m_analytic_ws_floor])
def test_interval_methods_bracket_the_point_estimate(method):
    for dv in (_FLAT, _MID, _ONES, _ZEROS):
        pt, lo, hi, patho = method(None, dv, 0)
        assert lo <= pt <= hi or patho
        assert isinstance(patho, bool)


def test_interval_methods_are_reproducible():
    a = sim.m_analytic_ws_floor(None, _MID, 0, 0.01)
    b = sim.m_analytic_ws_floor(None, _MID, 0, 0.01)
    assert a == b
    c = sim.m_domain_t(None, _MID, 0)
    d = sim.m_domain_t(None, _MID, 0)
    assert c == d


def test_domain_t_uses_eight_domain_means_and_df7():
    # a hand check: domain means all equal -> zero width; spread -> t_7 * se
    pt, lo, hi, _ = sim.m_domain_t(None, _FLAT, 0)
    assert (lo, hi) == pytest.approx((0.4, 0.4))
    # domain means 0.0..0.7 step 0.1  -> sd, se, half = t_7 * se
    dv = [[float(k) / 10] * 5 for k in range(8)]
    import statistics as _st

    means = [_st.fmean(d) for d in dv]
    se = _st.stdev(means) / (8**0.5)
    exp_hw = sim.student_t_ppf(0.975, 7) * se
    pt, lo, hi, _ = sim.m_domain_t(None, dv, 0)
    assert (hi - lo) / 2 == pytest.approx(exp_hw, rel=1e-6)


def test_ws_floor_prevents_near_zero_width_when_domain_is_constant():
    # every domain's 5 values identical -> raw WS half-width ~ 0;
    # the floored method must still produce a usably-wide interval.
    _pt, lo_raw, hi_raw, _ = sim.m_analytic_ws(None, _FLAT, 0, 0.0)
    assert (hi_raw - lo_raw) < 1e-6
    _pt, lo, hi, patho_floor = sim.m_analytic_ws_floor(None, _FLAT, 0, s2_floor=0.048)
    assert patho_floor is False
    assert hi - lo > 0.05


def test_boundary_all_ones_and_all_zeros_do_not_crash():
    import math

    for dv in (_ONES, _ZEROS):
        for method in (
            sim.m_domain_t,
            sim.m_analytic_ws,
            sim.m_analytic_ws_floor,
            sim.m_ws_floor_inflated,
            sim.m_ws_floor_atanh,
        ):
            pt, lo, hi, patho = method(None, dv, 0, 0.02)
            assert math.isfinite(lo) and math.isfinite(hi)
            assert lo <= pt <= hi or patho
    # the atanh Q2 variant is the one that must respect the +/-1 support;
    # on an all-boundary dataset it may saturate to the closed endpoint.
    for dv in (_ONES, _ZEROS):
        _pt, lo, hi, _ = sim.m_ws_floor_atanh(None, dv, 0, 0.02)
        assert -1.0 <= lo <= hi <= 1.0


def test_atanh_variant_stays_inside_open_interval():
    dv = [[0.8, 1.0, 0.9, 1.0, 0.7] for _ in range(8)]  # large positive Delta
    _pt, lo, hi, _ = sim.m_ws_floor_atanh(None, dv, 0, 0.02)
    assert -1.0 < lo < hi < 1.0


# --- retained bootstrap sensitivity method: domain-preserving -------------- #
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


# --- Q2 pairing ---------------------------------------------------------- #
def test_q2_pair_preservation_recovers_a_constant_effect():
    # every scenario has delta = +0.4 exactly -> CI tight around 0.4, excl 0
    dv_diff = [[0.4, 0.4, 0.4, 0.4, 0.4] for _ in range(8)]
    _pt, lo, hi, _ = sim.m_analytic_ws_floor(None, dv_diff, 0, s2_floor=0.02)
    assert lo > 0.0
    assert lo <= 0.4 <= hi


# --- simulation determinism + recommendation --------------------------- #
def test_design_simulation_is_deterministic():
    a = sim.simulate_q1(n_sim=20)
    b = sim.simulate_q1(n_sim=20)
    assert [vars(r) for r in a] == [vars(r) for r in b]
    c = sim.simulate_q2(n_sim=20)
    d = sim.simulate_q2(n_sim=20)
    assert [vars(r) for r in c] == [vars(r) for r in d]


def test_more_scenarios_improve_q1_discrimination():
    """Q1 discrimination comes from scenario count, not repeats: at a clean
    mid-band truth, P(confident+correct) rises going 16x10 -> 40x5 despite
    16x10 having MORE repeats and the same trial count."""
    q1 = sim.simulate_q1(n_sim=90)

    def p_ok(design: tuple[int, int]) -> float:
        return min(
            r.p_correct_confident for r in q1 if r.design == design and abs(r.mu - 0.45) < 1e-9
        )

    assert p_ok((40, 5)) > p_ok((16, 10)) + 0.10


def test_calibration_prefers_analytic_over_bootstrap_and_recommends_g_for_q1():
    q1c = sim.simulate_calibration_q1(n_sim=90, b=300)
    q2c = sim.simulate_calibration_q2(n_sim=90, b=300)
    report = sim.print_calibration(q1c, q2c)

    # Q1 recommendation is method G (robust across DGPs). Q2 recommendation
    # is always an ANALYTIC method, never a bootstrap variant.
    assert "Q1 -> G_domain_t" in report
    q2_rec_line = next(ln for ln in report.splitlines() if ln.strip().startswith("Q2 ->"))
    assert not any(b in q2_rec_line for b in ("A_percentile", "B_boot_t", "C_BCa"))

    def cmin(rows, method, central):
        vals = [
            r.coverage
            for r in rows
            if r.method == method and any(abs(r.truth - t) < 1e-9 for t in central)
        ]
        return min(vals)

    # method G central-region Q1 coverage clears ~0.90; the draft-3
    # percentile bootstrap materially undercovers.
    assert cmin(q1c, "G_domain_t", sim.CALIB_Q1_CENTRAL) >= 0.88
    assert cmin(q1c, "A_percentile", sim.CALIB_Q1_CENTRAL) < 0.88
    # method E central-region Q2 coverage clears ~0.90; percentile bootstrap does not.
    assert cmin(q2c, "E_analytic_WS_floor", sim.CALIB_Q2_CENTRAL) >= 0.88
    assert cmin(q2c, "A_percentile", sim.CALIB_Q2_CENTRAL) < 0.90
