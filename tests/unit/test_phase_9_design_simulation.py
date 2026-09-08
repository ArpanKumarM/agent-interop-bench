"""scripts/phase_9_design_simulation.py -- guardrails for the offline
Phase 9 design-analysis artifact.

The script is deliberately not importable as a package module (it lives in
scripts/), so load it by path. These tests keep it deterministic, keep the
headline arithmetic honest, and keep the scenario-level interval behaving
the way the design doc claims (tightens with more scenario clusters).
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
# register before exec so @dataclass can resolve cls.__module__ in sys.modules
sys.modules[_spec.name] = sim
_spec.loader.exec_module(sim)


def test_selected_design_trial_count_is_1600():
    # 40 scenarios x 5 repeats x 2 arms (N, P) x 4 models x 1 framing (F3).
    assert sim.total_trials((40, 5), arms=2, models=4) == 1600
    assert sim.total_trials((40, 4), arms=2, models=4) == 1280  # budget fallback
    # the erroneous first-draft figure (5,120) must not be reproducible from
    # the real confirmatory allocation.
    assert sim.total_trials((40, 5)) != 5120


def test_band_constants_match_frozen_phase_8_band():
    assert (sim.BAND_LOW, sim.BAND_HIGH) == (0.25, 0.70)


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


def test_simulation_is_deterministic():
    a = sim.simulate_q1(n_sim=40)
    b = sim.simulate_q1(n_sim=40)
    assert [vars(r) for r in a] == [vars(r) for r in b]
    c = sim.simulate_q2(n_sim=40)
    d = sim.simulate_q2(n_sim=40)
    assert [vars(r) for r in c] == [vars(r) for r in d]


def test_more_scenarios_tighten_the_interval():
    """The core design claim: Q1 discrimination comes from scenario count,
    not repeats. Mean half-width at a fixed mid-band truth must shrink
    materially from 8 to 40 scenarios."""
    q1 = sim.simulate_q1(n_sim=120)

    def hw(design: tuple[int, int]) -> float:
        return next(
            r.mean_halfwidth
            for r in q1
            if r.design == design and r.dgp == "beta/moderate" and abs(r.mu - 0.45) < 1e-9
        )

    assert hw((40, 5)) < 0.6 * hw((8, 20))


def test_q2_power_orders_by_effect_size():
    """P(CI excludes 0) must be monotone-ish in the true delta at a fixed
    design and effect-spread regime."""
    q2 = sim.simulate_q2(n_sim=200)
    sel = sorted(
        (r for r in q2 if r.design == (40, 5) and r.regime == "effect-sd 0.15"),
        key=lambda r: r.delta,
    )
    powers = [r.power_excl_0 for r in sel]
    assert powers == sorted(powers)
    assert powers[0] < powers[-1]  # delta 0.10 clearly weaker than delta 0.50
    # delta = 0.25 should be well powered at the selected design
    at_025 = next(r.power_excl_0 for r in sel if abs(r.delta - 0.25) < 1e-9)
    assert at_025 > 0.85


def test_t_interval_proxy_agrees_with_cluster_bootstrap():
    d = sim.boot_check(n_sim=120, b=400)
    assert d < 0.09
