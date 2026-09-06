"""app.reporting.phase_8_frozen_grid -- the same self-consistency checks
paper/arxiv/audit_phase8_numbers.py runs against the manuscript, wired
into pytest so they run on every regular test invocation, not only when
someone remembers to run the audit script."""

from __future__ import annotations

from app.reporting import phase_8_frozen_grid as grid


def test_ceiling_group():
    assert grid.ceiling_models_round_one() == ["gpt-5.6-sol", "gpt-5.6-luna"]


def test_floor_group():
    assert grid.floor_models_round_two() == ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"]


def test_in_band_cells_exact_set():
    assert set(grid.in_band_cells()) == {
        ("gpt-5.6-terra", "F2", 0.500),
        ("gpt-5.6-terra", "F3", 0.583),
        ("claude-sonnet-5", "F4", 0.417),
    }


def test_max_simultaneous_in_band_is_one():
    assert grid.max_simultaneous_in_band() == 1


def test_ceiling_constrained_and_informative_cells_partition_18():
    ceiling_constrained = grid.ceiling_constrained_non_claude_cells()
    informative = grid.informative_non_claude_cells()
    assert len(ceiling_constrained) == 4
    assert len(informative) == 14
    assert set(ceiling_constrained).isdisjoint(informative)
    assert len(ceiling_constrained) + len(informative) == 18


def test_headroom_pass_counts_per_framing():
    expected = {"F1": 0, "F2": 1, "F3": 1, "F4": 1, "F5": 0, "F6": 0}
    for framing, count in expected.items():
        assert grid.headroom_pass_count(framing) == count


def test_sensitivity_pass_counts_per_framing():
    expected = {"F1": 4, "F2": 4, "F3": 4, "F4": 3, "F5": 2, "F6": 3}
    for framing, count in expected.items():
        assert grid.sensitivity_pass_count(framing) == count


def test_f5_is_the_only_severe_permit_inversion():
    # every non-claude, non-F5 cell has permit >= N; F5 is the one
    # exception, and it belongs to claude.
    violations = [
        (model, framing)
        for model in grid.PANEL
        for framing in grid.ALL_FRAMINGS
        if grid.PERMIT_RATE[model][framing] < grid.N_RATE[model][framing]
    ]
    assert set(violations) == {("claude-sonnet-5", "F1"), ("claude-sonnet-5", "F5")}


def test_f1_is_ceiling_constrained_not_a_second_inversion():
    # F1's baseline is already at the structural ceiling (N == 1.000), so
    # permit could only stay or drop -- it is not comparable to F5.
    assert grid.N_RATE["claude-sonnet-5"]["F1"] == 1.000
    assert grid.N_RATE["claude-sonnet-5"]["F5"] < 1.000


def test_terra_calibration_separations_are_not_flat():
    # S6.1 quotes these verbatim; an earlier draft flattened round one to
    # "1.000 in every round-one framing", which is wrong for F2 and F3.
    seps = grid.calibration_separations("gpt-5.6-terra")
    assert seps == {
        "F1": 1.000,
        "F2": 0.750,
        "F3": 0.667,
        "F4": 0.167,
        "F5": 0.333,
        "F6": 0.167,
    }


def test_public_arm_round_one_is_unrecoverable():
    # F1-F3 raw was overwritten; the public arm for those framings is gone.
    for m in grid.PANEL:
        for f in grid.ROUND_ONE_FRAMINGS:
            assert grid.PUBLIC_RATE[m][f] is None
            assert grid.p_minus_n(m, f) is None


def test_public_arm_round_two_p_minus_n():
    # S6.4 quotes these; raw-verified by verify_phase_8_round2_from_raw.py.
    assert grid.p_minus_n("claude-sonnet-5", "F4") == 0.500
    assert grid.p_minus_n("claude-sonnet-5", "F5") == 0.083
    assert grid.p_minus_n("claude-sonnet-5", "F6") == 0.167
    # F4 is the one cell where a model's N baseline is in band, and P moves it.
    assert grid.in_band(grid.N_RATE["claude-sonnet-5"]["F4"])
    assert grid.PUBLIC_RATE["claude-sonnet-5"]["F4"] == 0.917


def test_n_successes_consistent_with_n_rate():
    for m in grid.PANEL:
        for f in grid.ALL_FRAMINGS:
            assert round(grid.N_SUCCESSES[m][f] / grid.PILOT_CELL_N, 3) == grid.N_RATE[m][f]


def test_f3_is_the_only_framing_the_pilot_cannot_resolve():
    # Point-estimate rule: no framing reaches 3-of-4 in band.
    assert grid.max_simultaneous_in_band() == 1
    # Generous 95%-CI-overlap reading: F3, and only F3, reaches the
    # 3-of-4 acceptance threshold -- so its rejection is not resolvable
    # at n = 12.
    assert grid.framings_where_ci_reaches_three() == ["F3"]
    assert grid.max_simultaneous_ci_touches_band() == 3
    lo, hi = grid.n_rate_ci("gpt-5.6-terra", "F2")
    # the 95% interval is wider than the entire acceptance band and
    # contains its upper edge -- terra's true F2 rate could be anywhere
    # from the band's lower edge to above it.
    assert (hi - lo) > (grid.BAND_HIGH - grid.BAND_LOW)
    assert lo <= grid.BAND_HIGH <= hi


def test_trial_totals():
    assert grid.PHASE_6_TRIALS == 640
    assert grid.PHASE_7_TRIALS == 480
    assert grid.ROUND_ONE_TRIALS_PLANNED == 576
    assert grid.ROUND_TWO_TRIALS_PLANNED == 576
    assert grid.ROUND_ONE_TRIALS_COMPLETED == 575
    assert grid.ROUND_TWO_TRIALS_COMPLETED == 575


def test_main_study_total_matches_live_schedule_recomputation():
    from app.runner.blocked_schedule import build_phase_8_schedule_artifact

    total = sum(
        build_phase_8_schedule_artifact(sub)["trials_per_model"] * 4
        for sub in ("v8a", "v8a2", "v8b", "v8c", "v8d")
    )
    assert total == 13184
