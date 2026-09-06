"""The frozen Phase 8 pilot grid (docs/phase_8c_pilot_result.md,
docs/phase_8a2_pilot_result.md) as machine-readable constants, plus every
derived quantity the v2 manuscript states. This is the ONE source of
truth `paper/arxiv/audit_phase8_numbers.py` checks the manuscript
against -- no number in `paper/main_v2.md`'s Phase 8 sections may be
written by hand without a corresponding, matching entry here.

**Provenance note (a real gap, disclosed rather than hidden):** round
two's raw `trials.jsonl` files are still on disk
(`reports/experiments/phase-8-pilot-*/`) and this module's round-two
values are recomputed live from them by
`scripts/verify_phase_8_round2_from_raw.py`, which is the strongest
available check. Round one's raw files were overwritten by round two's
run before this audit module existed, so round one's values below are
transcribed from `docs/phase_8c_pilot_result.md`'s own frozen table
(itself SHA-256-pinned against raw bytes that no longer exist on this
machine) -- they cannot be independently re-derived from raw bytes
anymore. This is a corrective lesson for any future pilot round: archive
raw copies (mirroring `reports/_phase7d_preanalysis_freeze`) BEFORE
re-running into the same run directories, not after.
"""

from __future__ import annotations

PANEL: tuple[str, ...] = ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "claude-sonnet-5")
ROUND_ONE_FRAMINGS: tuple[str, ...] = ("F1", "F2", "F3")
ROUND_TWO_FRAMINGS: tuple[str, ...] = ("F4", "F5", "F6")
ALL_FRAMINGS: tuple[str, ...] = ROUND_ONE_FRAMINGS + ROUND_TWO_FRAMINGS

BAND_LOW, BAND_HIGH = 0.25, 0.70
CEILING_MIN_RATE = 0.917  # round-one ceiling rule: min rate >= this, across F1-F3
SENSITIVITY_MIN_SEPARATION = 0.50
SUPPRESS_MAX = 0.15

# --------------------------------------------------------------------------- #
# The grid: N (unlabeled-arm) rate, per model per framing.
# Round one: docs/phase_8c_pilot_result.md "Per-model, per-framing detail".
# Round two: recomputed from raw trials.jsonl (verify_phase_8_round2_from_raw.py).
# --------------------------------------------------------------------------- #
N_RATE: dict[str, dict[str, float]] = {
    "gpt-5.6-sol": {"F1": 1.000, "F2": 1.000, "F3": 1.000, "F4": 0.000, "F5": 0.000, "F6": 0.000},
    "gpt-5.6-terra": {
        "F1": 0.917,
        "F2": 0.500,
        "F3": 0.583,
        "F4": 0.000,
        "F5": 0.000,
        "F6": 0.000,
    },
    "gpt-5.6-luna": {
        "F1": 1.000,
        "F2": 0.917,
        "F3": 0.917,
        "F4": 0.000,
        "F5": 0.000,
        "F6": 0.000,
    },
    "claude-sonnet-5": {
        "F1": 1.000,
        "F2": 1.000,
        "F3": 0.750,
        "F4": 0.417,
        "F5": 0.917,
        "F6": 0.833,
    },
}

# permit rate, per model per framing (same sources as N_RATE).
PERMIT_RATE: dict[str, dict[str, float]] = {
    "gpt-5.6-sol": {"F1": 1.000, "F2": 1.000, "F3": 1.000, "F4": 0.667, "F5": 1.000, "F6": 0.917},
    "gpt-5.6-terra": {
        "F1": 1.000,
        "F2": 0.750,
        "F3": 0.667,
        "F4": 0.167,
        "F5": 0.333,
        "F6": 0.167,
    },
    "gpt-5.6-luna": {
        "F1": 1.000,
        "F2": 1.000,
        "F3": 1.000,
        "F4": 1.000,
        "F5": 1.000,
        "F6": 1.000,
    },
    "claude-sonnet-5": {
        "F1": 0.750,
        "F2": 1.000,
        "F3": 0.750,
        "F4": 0.583,
        "F5": 0.083,
        "F6": 0.833,
    },
}

# suppress rate, per model per framing. Every cell is 0.000 in both
# pilots; kept as an explicit table (not a constant) so the audit checks
# it rather than assuming it.
SUPPRESS_RATE: dict[str, dict[str, float]] = {
    model: dict.fromkeys(ALL_FRAMINGS, 0.000) for model in PANEL
}

# --------------------------------------------------------------------------- #
# public-arm (`P`) rate, per model per framing.
#
# The pilots ran FOUR arms -- suppress, unlabeled, public, permit -- so the
# public-vs-unlabeled (`P - N`) label contrast was collected at every pilot
# framing. The frozen pilot analysis plan (docs/phase_8a2_pilot_design.md
# S6) reserved `P - N` as the MAIN-STUDY primary test and did not call for
# reporting it at the pilot stage; it is analysed post hoc in S6 of v2,
# after review identified the paper had no within-study, same-framing label
# measurement. ROUND ONE (F1-F3) raw trials were overwritten before this
# need was anticipated, so the F1-F3 public arm is UNRECOVERABLE and is
# left as None. ROUND TWO (F4-F6) is recomputed live from the byte-pinned
# raw by scripts/verify_phase_8_round2_from_raw.py.
PUBLIC_RATE: dict[str, dict[str, float | None]] = {
    "gpt-5.6-sol": {"F1": None, "F2": None, "F3": None, "F4": 0.083, "F5": 0.000, "F6": 0.000},
    "gpt-5.6-terra": {"F1": None, "F2": None, "F3": None, "F4": 0.000, "F5": 0.000, "F6": 0.000},
    "gpt-5.6-luna": {"F1": None, "F2": None, "F3": None, "F4": 0.000, "F5": 0.333, "F6": 0.000},
    "claude-sonnet-5": {"F1": None, "F2": None, "F3": None, "F4": 0.917, "F5": 1.000, "F6": 1.000},
}


def p_minus_n(model: str, framing: str) -> float | None:
    """public - unlabeled at one pilot cell, or None if the public arm for
    that framing is unrecoverable (round one)."""
    p = PUBLIC_RATE[model][framing]
    return None if p is None else round(p - N_RATE[model][framing], 3)


ROUND_TWO_FRAMINGS_WITH_PUBLIC = ROUND_TWO_FRAMINGS  # F4, F5, F6 -- the only P - N we have

# --------------------------------------------------------------------------- #
# Trial counts and cost (docs/phase_8c_pilot_result.md,
# docs/phase_8a2_pilot_result.md).
# --------------------------------------------------------------------------- #
PHASE_6_TRIALS = 640
PHASE_7_TRIALS = 480
ROUND_ONE_TRIALS_PLANNED = 576
ROUND_ONE_TRIALS_COMPLETED = 575
ROUND_ONE_COST_USD = 3.32
ROUND_TWO_TRIALS_PLANNED = 576
ROUND_TWO_TRIALS_COMPLETED = 575
ROUND_TWO_COST_USD = 3.02

ROUND_ONE_SOURCE_COMMIT = "74ba1cdd545ce9f32850bd4ba107e45af952dbb3"
ROUND_TWO_SOURCE_COMMIT = "d06a88b0eebd6f4452ab09ccbc6fe5c2a4907631"

# Phase 6 per-model C-P contrast (paper/main.md S5.4 / S3, frozen v1 numbers).
PHASE_6_C_MINUS_P: dict[str, float] = {
    "gpt-5.6-sol": -0.250,
    "gpt-5.6-terra": 0.000,
    "gpt-5.6-luna": -0.125,
    "claude-sonnet-5": -0.900,
}

# Phase 7 pooled arm rates, x/40 (paper/main.md S5.1, frozen v1 numbers).
PHASE_7_POOLED: dict[str, dict[str, tuple[int, int]]] = {
    "gpt-5.6-sol": {"C": (0, 40), "N": (0, 40), "P": (5, 40)},
    "gpt-5.6-terra": {"C": (0, 40), "N": (0, 40), "P": (0, 40)},
    "gpt-5.6-luna": {"C": (0, 40), "N": (0, 40), "P": (10, 40)},
    "claude-sonnet-5": {"C": (1, 40), "N": (5, 40), "P": (37, 40)},
}
PHASE_7_P_MINUS_N_CLAUDE_MEAN = 0.800
PHASE_7_P_MINUS_N_CLAUDE_MEDIAN = 0.750
PHASE_7_P_MINUS_N_CLAUDE_POSITIVE_SCENARIOS = 10  # of 10


def in_band(rate: float) -> bool:
    return BAND_LOW <= rate <= BAND_HIGH


def separation(model: str, framing: str) -> float:
    return PERMIT_RATE[model][framing] - SUPPRESS_RATE[model][framing]


def in_band_cells() -> list[tuple[str, str, float]]:
    """(model, framing, rate) for every cell inside [BAND_LOW, BAND_HIGH]."""
    return [
        (model, framing, N_RATE[model][framing])
        for model in PANEL
        for framing in ALL_FRAMINGS
        if in_band(N_RATE[model][framing])
    ]


def max_simultaneous_in_band() -> int:
    """The largest number of models in-band on any single framing."""
    return max(
        sum(1 for model in PANEL if in_band(N_RATE[model][framing])) for framing in ALL_FRAMINGS
    )


def ceiling_models_round_one() -> list[str]:
    """models whose minimum N-rate across F1-F3 is >= CEILING_MIN_RATE."""
    return [
        model
        for model in PANEL
        if min(N_RATE[model][f] for f in ROUND_ONE_FRAMINGS) >= CEILING_MIN_RATE
    ]


def floor_models_round_two() -> list[str]:
    """models whose N-rate is exactly 0.000 in every one of F4-F6."""
    return [model for model in PANEL if all(N_RATE[model][f] == 0.000 for f in ROUND_TWO_FRAMINGS)]


def calibration_pass(model: str, framing: str) -> bool:
    return (
        separation(model, framing) >= SENSITIVITY_MIN_SEPARATION
        and SUPPRESS_RATE[model][framing] <= SUPPRESS_MAX
    )


def sensitivity_pass_count(framing: str) -> int:
    return sum(1 for model in PANEL if calibration_pass(model, framing))


def headroom_pass_count(framing: str) -> int:
    return sum(1 for model in PANEL if in_band(N_RATE[model][framing]))


# --------------------------------------------------------------------------- #
# n = 12 per pilot cell (4 pilot scenarios x 3 repeats). The in-band / out
# classification in S5.3 is a point-estimate call at that resolution; these
# helpers let S5.3 and the audit state how thin the margin is.
# --------------------------------------------------------------------------- #
PILOT_CELL_N = 12

# N-arm successes (k of 12) per cell. Round one (F1-F3) is transcribed from
# docs/phase_8c_pilot_result.md; round two (F4-F6) is raw-verified.
N_SUCCESSES: dict[str, dict[str, int]] = {
    "gpt-5.6-sol": {"F1": 12, "F2": 12, "F3": 12, "F4": 0, "F5": 0, "F6": 0},
    "gpt-5.6-terra": {"F1": 11, "F2": 6, "F3": 7, "F4": 0, "F5": 0, "F6": 0},
    "gpt-5.6-luna": {"F1": 12, "F2": 11, "F3": 11, "F4": 0, "F5": 0, "F6": 0},
    "claude-sonnet-5": {"F1": 12, "F2": 12, "F3": 9, "F4": 5, "F5": 11, "F6": 10},
}


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    import math

    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z / d * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3))


def n_rate_ci(model: str, framing: str) -> tuple[float, float]:
    """Wilson 95% interval on the unlabeled-arm rate for one pilot cell."""
    return _wilson(N_SUCCESSES[model][framing], PILOT_CELL_N)


def ci_touches_band(model: str, framing: str) -> bool:
    lo, hi = n_rate_ci(model, framing)
    return not (hi < BAND_LOW or lo > BAND_HIGH)


def max_simultaneous_ci_touches_band() -> int:
    """Largest number of models on one framing whose 95% CI even overlaps
    the band -- the most generous reading of 'could have had headroom'.
    The pre-registered rule used point estimates; this is the robustness
    counter-check for S5.3."""
    return max(
        sum(1 for m in PANEL if ci_touches_band(m, f)) for f in ALL_FRAMINGS
    )


def framings_where_ci_reaches_three() -> list[str]:
    """Framings where >=3 of 4 models' 95% CIs overlap the band -- i.e.
    where n=12 cannot rule out that the acceptance rule was met."""
    return [
        f
        for f in ALL_FRAMINGS
        if sum(1 for m in PANEL if ci_touches_band(m, f)) >= 3
    ]


def non_claude_cells() -> list[tuple[str, str, float, float]]:
    """(model, framing, N, permit) for every non-claude cell."""
    return [
        (model, framing, N_RATE[model][framing], PERMIT_RATE[model][framing])
        for model in PANEL
        if model != "claude-sonnet-5"
        for framing in ALL_FRAMINGS
    ]


def ceiling_constrained_non_claude_cells() -> list[tuple[str, str]]:
    """Non-claude cells where N == 1.000 exactly (permit cannot exceed it)."""
    return [(m, f) for (m, f, n, _p) in non_claude_cells() if n == 1.000]


def informative_non_claude_cells() -> list[tuple[str, str]]:
    """Non-claude cells where N < 1.000 (real headroom existed below ceiling)."""
    return [(m, f) for (m, f, n, _p) in non_claude_cells() if n < 1.000]


def calibration_separations(model: str) -> dict[str, float]:
    """permit - suppress, per framing, for one model (S6.1 quotes these
    verbatim for gpt-5.6-terra)."""
    return {f: round(separation(model, f), 3) for f in ALL_FRAMINGS}


def claude_f1_f5_inversion_check() -> dict[str, dict[str, float]]:
    """The two claude cells where permit < N, plus F2 as the adjacent
    same-baseline contrast cell (S6.3)."""
    claude = "claude-sonnet-5"
    return {
        f: {"N": N_RATE[claude][f], "permit": PERMIT_RATE[claude][f]} for f in ("F1", "F2", "F5")
    }
