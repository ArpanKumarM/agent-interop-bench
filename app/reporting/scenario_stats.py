"""Phase 8 scenario-level contrast statistics: BCa bootstrap confidence
intervals, paired permutation tests, Holm-Bonferroni correction --
docs/phase_8_design.md S7.2; constants from docs/phase_8a_parameters.md
S4.

Pure stdlib (``random`` + ``statistics.NormalDist``, available since
Python 3.8) -- no ``numpy`` dependency. Every function is deterministic
given its seed. Operates on a list of **scenario-level** differences (the
generalization unit, unchanged since Phase 7); it is never given
trial-level or pooled arm-rate data.
"""

from __future__ import annotations

import random
import statistics
from statistics import NormalDist

# Pre-registered constants (docs/phase_8a_parameters.md S4).
BOOTSTRAP_SEED: int = 20261102
PERMUTATION_SEED: int = 20261103
BOOTSTRAP_B: int = 10_000
PERMUTATION_M: int = 20_000
CI_ALPHA: float = 0.05
# Exact 2^S sign-flip enumeration below this scenario count; Monte Carlo
# with PERMUTATION_M draws at or above it (design S7.2).
EXACT_PERMUTATION_MAX_S: int = 22

_STD_NORMAL = NormalDist()


def bca_ci(
    diffs: list[float],
    *,
    b: int = BOOTSTRAP_B,
    seed: int = BOOTSTRAP_SEED,
    alpha: float = CI_ALPHA,
) -> tuple[float, float]:
    """Bias-corrected and accelerated bootstrap CI of the mean of ``diffs``.

    Degenerate inputs (n <= 1, or every bootstrap resample identical to the
    observed mean) fall back to the point estimate as both bounds -- there
    is no dispersion to estimate, never a crash or a fabricated interval.
    """
    n = len(diffs)
    if n == 0:
        return (0.0, 0.0)
    theta_hat = statistics.mean(diffs)
    if n == 1:
        return (theta_hat, theta_hat)

    rng = random.Random(seed)
    boot_means = sorted(
        statistics.mean(diffs[rng.randrange(n)] for _ in range(n)) for _ in range(b)
    )

    prop_less = sum(1 for bm in boot_means if bm < theta_hat) / b
    # Clamp away from 0/1 so inv_cdf never sees a non-finite input.
    prop_less = min(max(prop_less, 1 / (b + 1)), b / (b + 1))
    z0 = _STD_NORMAL.inv_cdf(prop_less)

    jack_means = [statistics.mean(diffs[:i] + diffs[i + 1 :]) for i in range(n)]
    jack_avg = statistics.mean(jack_means)
    num = sum((jack_avg - jm) ** 3 for jm in jack_means)
    den = 6.0 * (sum((jack_avg - jm) ** 2 for jm in jack_means) ** 1.5)
    accel = num / den if den else 0.0

    def _adjusted_percentile(z_alpha: float) -> float:
        denom = 1 - accel * (z0 + z_alpha)
        if denom == 0:
            denom = 1e-12
        return _STD_NORMAL.cdf(z0 + (z0 + z_alpha) / denom)

    lo_p = _adjusted_percentile(_STD_NORMAL.inv_cdf(alpha / 2))
    hi_p = _adjusted_percentile(_STD_NORMAL.inv_cdf(1 - alpha / 2))
    lo_idx = min(max(round(lo_p * (b - 1)), 0), b - 1)
    hi_idx = min(max(round(hi_p * (b - 1)), 0), b - 1)
    lo, hi = boot_means[lo_idx], boot_means[hi_idx]
    return (lo, hi) if lo <= hi else (hi, lo)


def paired_permutation_p(
    diffs: list[float],
    *,
    m: int = PERMUTATION_M,
    seed: int = PERMUTATION_SEED,
) -> float:
    """Two-sided sign-flip permutation p-value against the scenario-level
    null of no mean difference. Exact enumeration of all ``2**n`` sign
    assignments when ``n <= EXACT_PERMUTATION_MAX_S``; otherwise ``m``
    Monte-Carlo sign flips under the frozen seed."""
    n = len(diffs)
    if n == 0:
        return 1.0
    observed = abs(statistics.mean(diffs))
    tol = 1e-9

    if n <= EXACT_PERMUTATION_MAX_S:
        total = 1 << n
        at_least_as_extreme = 0
        for bits in range(total):
            signed_sum = sum(-d if (bits >> i) & 1 else d for i, d in enumerate(diffs))
            if abs(signed_sum / n) >= observed - tol:
                at_least_as_extreme += 1
        return at_least_as_extreme / total

    rng = random.Random(seed)
    at_least_as_extreme = 0
    for _ in range(m):
        signed_sum = sum(-d if rng.random() < 0.5 else d for d in diffs)
        if abs(signed_sum / n) >= observed - tol:
            at_least_as_extreme += 1
    return at_least_as_extreme / m


def holm(pvals: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni step-down correction within one named family. The
    caller is responsible for the family's membership (design S12/O12
    enumerates the pre-registered families) -- this function only corrects
    whatever mapping it is given."""
    ordered = sorted(pvals.items(), key=lambda kv: kv[1])
    m = len(ordered)
    adjusted: dict[str, float] = {}
    running_max = 0.0
    for i, (name, p) in enumerate(ordered):
        step = min(1.0, (m - i) * p)
        running_max = max(running_max, step)
        adjusted[name] = running_max
    return adjusted
