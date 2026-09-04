"""Phase 8 blocked schedules (docs/phase_8_design.md S5;
docs/phase_8_change_list.md S4.1). Trial counts must reconcile exactly
with the design doc's S5.1 budget table."""

from __future__ import annotations

from app.runner.blocked_schedule import (
    PHASE_8_MODEL_PANEL,
    PHASE_8_SCHEDULE_SEED,
    PHASE_8_SUBSTUDY_SEED_OFFSET,
    build_phase_8_model_schedule,
    build_phase_8_schedule_artifact,
    build_phase_8_study_schedule,
    phase_8_cells,
    phase_8a_cells,
    phase_8a_prime_cells,
    phase_8b_cells,
    phase_8c_cells,
    phase_8d_cells,
)

# (sub-study, expected cells, expected trials/model, expected total across
# the 4-model panel) -- from docs/phase_8_design.md S5.1 (R=6 default,
# S8-D fixed R=4).
_EXPECTED = {
    "v8a": (144, 864, 3456),
    "v8a2": (16, 96, 384),
    "v8b": (48, 288, 1152),
    "v8c": (48, 288, 1152),
    "v8d": (24, 96, 384),
}


_OVERLAY_PREFIX = {"v8a": "p8a-", "v8a2": "p8a2-", "v8b": "p8b-", "v8c": "p8c-", "v8d": "p8d-"}


def test_cell_counts_and_uniqueness():
    fns = {
        "v8a": phase_8a_cells,
        "v8a2": phase_8a_prime_cells,
        "v8b": phase_8b_cells,
        "v8c": phase_8c_cells,
        "v8d": phase_8d_cells,
    }
    for sub, (n_cells, _, _) in _EXPECTED.items():
        cells = fns[sub]()
        assert len(cells) == n_cells
        assert len(set(cells)) == n_cells, f"{sub}: duplicate cell"
        assert phase_8_cells(sub) == cells
        for experiment, condition, overlay_id in cells:
            assert experiment == "sensitive_egress"
            assert condition in {"treatment", "control", "neutral"}
            assert overlay_id.startswith(_OVERLAY_PREFIX[sub])


def test_trials_per_model_matches_design_budget():
    for sub, (_, per_model, total) in _EXPECTED.items():
        study = build_phase_8_study_schedule(sub)
        assert set(study) == set(PHASE_8_MODEL_PANEL)
        for entries in study.values():
            assert len(entries) == per_model
        assert sum(len(v) for v in study.values()) == total


def test_unknown_substudy_rejected():
    import pytest

    with pytest.raises(ValueError, match="unknown Phase 8 sub-study"):
        phase_8_cells("v8z")


def test_each_block_contains_every_cell_exactly_once():
    for sub in _EXPECTED:
        entries = build_phase_8_model_schedule(sub, PHASE_8_MODEL_PANEL[0])
        by_block: dict[int, list[str]] = {}
        for e in entries:
            by_block.setdefault(e.block_index, []).append(e.overlay_id)
        cell_ids = {oid for (_, _, oid) in phase_8_cells(sub)}
        for block_index, ids in by_block.items():
            assert set(ids) == cell_ids, f"{sub} block {block_index}: cell set mismatch"
            assert len(ids) == len(set(ids)), f"{sub} block {block_index}: duplicate within block"


def test_deterministic_and_matches_frozen_build():
    for sub in _EXPECTED:
        a = build_phase_8_schedule_artifact(sub)
        b = build_phase_8_schedule_artifact(sub)
        assert a == b


def test_distinct_seed_streams_per_substudy():
    # every sub-study gets a distinct rng stream (via the fixed offset), so
    # two same-length cell sets would not coincidentally shuffle identically
    offsets = PHASE_8_SUBSTUDY_SEED_OFFSET
    assert len(set(offsets.values())) == len(offsets)
    hashes = {
        sub: build_phase_8_schedule_artifact(sub)["study_schedule_sha256"] for sub in _EXPECTED
    }
    assert len(set(hashes.values())) == len(hashes)


def test_scheduling_seed_is_the_frozen_family_base():
    art = build_phase_8_schedule_artifact("v8a")
    assert art["scheduling_seed"] == PHASE_8_SCHEDULE_SEED + PHASE_8_SUBSTUDY_SEED_OFFSET["v8a"]


def test_model_not_in_panel_rejected():
    import pytest

    with pytest.raises(ValueError, match="not in the Phase 8 panel"):
        build_phase_8_model_schedule("v8a", "not-a-real-model")
