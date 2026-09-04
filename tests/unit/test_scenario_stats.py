"""Phase 8 scenario-level contrast statistics (docs/phase_8_design.md
S7.2). Deterministic, stdlib-only."""

from __future__ import annotations

import math

from app.reporting.scenario_stats import (
    BOOTSTRAP_SEED,
    EXACT_PERMUTATION_MAX_S,
    PERMUTATION_SEED,
    bca_ci,
    holm,
    paired_permutation_p,
)


def test_bca_ci_degenerate_constant_input_collapses_to_point_estimate():
    lo, hi = bca_ci([0.25] * 10)
    assert math.isclose(lo, 0.25, abs_tol=1e-9)
    assert math.isclose(hi, 0.25, abs_tol=1e-9)


def test_bca_ci_single_value():
    lo, hi = bca_ci([0.5])
    assert lo == hi == 0.5


def test_bca_ci_empty_is_zero_zero_no_crash():
    assert bca_ci([]) == (0.0, 0.0)


def test_bca_ci_contains_the_mean_for_varying_data():
    diffs = [0.0, 0.25, 0.5, 0.25, 0.0, 0.75, 0.25, 0.5, 0.0, 0.25]
    lo, hi = bca_ci(diffs, b=2000, seed=1)
    mean = sum(diffs) / len(diffs)
    assert lo <= mean <= hi


def test_bca_ci_deterministic_given_the_same_seed():
    diffs = [0.0, 0.25, -0.25, 0.5, 0.0, 0.25, -0.5, 0.0, 0.25, 0.25]
    a = bca_ci(diffs, b=500, seed=BOOTSTRAP_SEED)
    b = bca_ci(diffs, b=500, seed=BOOTSTRAP_SEED)
    assert a == b


def test_permutation_p_zero_effect_is_one():
    assert paired_permutation_p([0.0] * 8) == 1.0


def test_permutation_p_uniform_strong_effect_is_minimal():
    # every scenario shows the identical nonzero effect -> only the two
    # all-same-sign flips are "as extreme" -> p = 2 / 2**n
    diffs = [0.25] * 6
    p = paired_permutation_p(diffs)
    assert math.isclose(p, 2 / (2**6), rel_tol=1e-9)


def test_permutation_p_hand_computed_small_case():
    # n=3, diffs = [1, 1, -1]; observed mean = 1/3.
    # sign-flip sums (bits 0..7): enumerate manually.
    diffs = [1.0, 1.0, -1.0]
    p = paired_permutation_p(diffs)
    # exact fraction: count bit patterns where |signed_mean| >= 1/3 - eps
    observed = abs(sum(diffs) / 3)
    count = 0
    for bits in range(8):
        s = sum(-d if (bits >> i) & 1 else d for i, d in enumerate(diffs))
        if abs(s / 3) >= observed - 1e-9:
            count += 1
    assert math.isclose(p, count / 8, rel_tol=1e-9)


def test_exact_vs_monte_carlo_switchover():
    # at/under the threshold: exact, deterministic regardless of seed
    diffs_exact = [0.25, -0.25, 0.0, 0.25, -0.25]  # n=5 <= EXACT_PERMUTATION_MAX_S
    p1 = paired_permutation_p(diffs_exact, seed=1)
    p2 = paired_permutation_p(diffs_exact, seed=2)
    assert p1 == p2  # seed irrelevant under exact enumeration

    # above the threshold: Monte Carlo, same seed -> same result, different
    # seed CAN differ (not asserted equal, only reproducibility is)
    diffs_mc = [0.25, -0.25, 0.0, 0.1, -0.1] * 5  # n=25 > EXACT_PERMUTATION_MAX_S
    assert len(diffs_mc) > EXACT_PERMUTATION_MAX_S
    a = paired_permutation_p(diffs_mc, m=500, seed=PERMUTATION_SEED)
    b = paired_permutation_p(diffs_mc, m=500, seed=PERMUTATION_SEED)
    assert a == b  # reproducible under the same seed


def test_permutation_p_empty_is_one():
    assert paired_permutation_p([]) == 1.0


def test_holm_monotonic_and_bounded():
    raw = {"a": 0.01, "b": 0.02, "c": 0.5, "d": 0.7}
    adjusted = holm(raw)
    assert set(adjusted) == set(raw)
    for name, p in adjusted.items():
        assert p >= raw[name]
        assert p <= 1.0
    # non-decreasing when sorted by raw p (Holm step-down monotonicity)
    ordered = sorted(raw.items(), key=lambda kv: kv[1])
    adj_in_order = [adjusted[name] for name, _ in ordered]
    assert adj_in_order == sorted(adj_in_order)


def test_holm_single_pvalue_unchanged():
    assert holm({"only": 0.03}) == {"only": 0.03}


def test_holm_caps_at_one():
    adjusted = holm({"a": 0.9, "b": 0.8, "c": 0.7})
    assert all(p <= 1.0 for p in adjusted.values())
