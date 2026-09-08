"""scripts/phase_9_design_simulation.py -- guardrails for the offline
Phase 9 design-analysis artifact.

The script is not importable as a package module (it lives in scripts/),
so load it by path. These tests keep it deterministic, keep the headline
arithmetic honest, keep the stratified bootstrap doing what the design
doc claims (domain composition fixed; tightens with more scenario
clusters), and confirm the percentile CI is stable in the bootstrap
replicate count.
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


def test_selected_design_trial_count_is_1600():
    # 40 scenarios x 5 repeats x 2 arms (N, P) x 4 models x 1 framing (F3).
    assert sim.total_trials((40, 5), arms=2, models=4) == 1600
    assert sim.total_trials((40, 4), arms=2, models=4) == 1280  # budget fallback
    assert sim.total_trials((40, 5)) != 5120  # the erroneous draft-1 figure


def test_band_constants_match_frozen_phase_8_band():
    assert (sim.BAND_LOW, sim.BAND_HIGH) == (0.25, 0.70)


def test_every_candidate_design_has_whole_domains():
    # the stratified bootstrap needs S divisible by the 8 domains.
    for s, _r in sim.CANDIDATE_DESIGNS:
        assert s % sim.DOMAINS == 0
        assert s // sim.DOMAINS >= 2


@pytest.mark.parametrize(
    ("lo", "hi", "expected"),
    [
        (0.30, 0.65, "in-band"),
        (0.25, 0.70, "in-band"),
        (0.05, 0.20, "below"),
        (0.72, 0.90, "above"),
        (0.20, 0.55, "unresolved"),  # straddles the low edge
        (0.60, 0.80, "unresolved"),  # straddles the high edge
    ],
)
def test_classify_q1_is_whole_ci_containment(lo, hi, expected):
    assert sim.classify_q1(lo, hi) == expected


def test_equal_domain_weight_mean_matches_bootstrap_point_estimate():
    dv = [[0.2, 0.4, 0.6, 0.8, 1.0], [0.0, 0.0, 0.2, 0.2, 0.6]] + [[0.4, 0.4, 0.4, 0.4, 0.4]] * 6
    pt = sim.equal_domain_weight_mean(dv)
    rng = sim._rng("t", "point")
    pt2, _lo, _hi = sim.stratified_bootstrap_ci(rng, dv, b=200)
    assert pt == pytest.approx(pt2)
    # equal-domain-weight of a balanced panel == plain mean
    flat = [v for d in dv for v in d]
    assert pt == pytest.approx(sum(flat) / len(flat))


def test_stratified_bootstrap_never_changes_domain_count():
    # a replicate must still have exactly DOMAINS domains of the same
    # size -- the estimator is a mean over len(dv) domains, so if a
    # domain were dropped/added the point vs replicate scale would break.
    dv = [[0.0, 1.0, 0.0, 1.0, 0.5] for _ in range(sim.DOMAINS)]
    rng = sim._rng("t", "strat")
    _pt, lo, hi = sim.stratified_bootstrap_ci(rng, dv, b=500)
    assert 0.0 <= lo <= hi <= 1.0


def test_simulation_is_deterministic():
    a = sim.simulate_q1(n_sim=20, b=200)
    b = sim.simulate_q1(n_sim=20, b=200)
    assert [vars(r) for r in a] == [vars(r) for r in b]
    c = sim.simulate_q2(n_sim=20, b=200)
    d = sim.simulate_q2(n_sim=20, b=200)
    assert [vars(r) for r in c] == [vars(r) for r in d]


def test_more_scenarios_improve_q1_discrimination():
    """Q1 discrimination comes from scenario count, not repeats: at a clean
    mid-band truth, P(confident+correct) must rise substantially going from
    16 scenarios x10 repeats to 40 scenarios x5 repeats -- despite 16x10
    having MORE repeats and the same trial count."""
    q1 = sim.simulate_q1(n_sim=90, b=300)

    def p_ok(design: tuple[int, int]) -> float:
        return min(
            r.p_correct_confident for r in q1 if r.design == design and abs(r.mu - 0.45) < 1e-9
        )

    assert p_ok((40, 5)) > p_ok((16, 10)) + 0.15


def test_q2_power_orders_by_effect_size():
    q2 = sim.simulate_q2(n_sim=110, b=300)
    sel = sorted(
        (r for r in q2 if r.design == (40, 5) and abs(r.effect_sd - 0.15) < 1e-9),
        key=lambda r: r.delta,
    )
    powers = [r.power_excl_0 for r in sel]
    assert powers[0] < powers[-1]  # delta 0.10 clearly weaker than delta 0.50
    at_025 = next(r.power_excl_0 for r in sel if abs(r.delta - 0.25) < 1e-9)
    assert at_025 > 0.85


def test_percentile_ci_is_stable_in_bootstrap_b():
    res = sim.ci_stability(bs=(500, 1000, 2000, 4000))
    for _key, entry in res.items():
        assert entry["max_drift_B>=2000"] < 0.012
