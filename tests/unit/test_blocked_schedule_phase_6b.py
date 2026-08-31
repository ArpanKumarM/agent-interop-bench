"""Phase 6B blocked schedule: 40 overlays, 4 blocks/model, each block every
overlay exactly once, deterministic from one frozen seed."""

from __future__ import annotations

import json
from pathlib import Path

from app.runner.blocked_schedule import (
    PHASE_6B_BLOCKS_PER_MODEL,
    PHASE_6B_MODEL_PANEL,
    PHASE_6B_OVERLAY_IDS,
    PHASE_6B_SCHEDULE_SEED,
    build_phase_6b_model_schedule,
    build_phase_6b_schedule_artifact,
    build_phase_6b_study_schedule,
    phase_6b_cells,
)

_SCHEDULE_JSON = Path("benchmarks/composed/live_canary_v4_schedule.json")


def test_shape():
    assert PHASE_6B_SCHEDULE_SEED == 20260615
    assert PHASE_6B_BLOCKS_PER_MODEL == 4
    assert len(PHASE_6B_OVERLAY_IDS) == 40
    assert len(set(PHASE_6B_OVERLAY_IDS)) == 40
    cells = phase_6b_cells()
    assert len(cells) == 40
    assert sum(1 for (e, _, _) in cells if e == "sensitive_egress") == 20
    assert sum(1 for (e, _, _) in cells if e == "adversarial_influence") == 20


def test_each_block_contains_every_overlay_exactly_once():
    for model in PHASE_6B_MODEL_PANEL:
        sched = build_phase_6b_model_schedule(model)
        assert len(sched) == 4 * 40 == 160
        for block_index in range(4):
            block = [e.overlay_id for e in sched if e.block_index == block_index]
            assert sorted(block) == sorted(PHASE_6B_OVERLAY_IDS)
        # trial_index == block_index (per model,overlay sequential 0..3)
        for e in sched:
            assert e.trial_index == e.block_index


def test_deterministic_reproducible():
    a = build_phase_6b_study_schedule()
    b = build_phase_6b_study_schedule()
    assert [e.model_dump() for e in a["gpt-5.6-sol"]] == [e.model_dump() for e in b["gpt-5.6-sol"]]


def test_distinct_per_model_permutation_streams():
    study = build_phase_6b_study_schedule()
    sol0 = [e.overlay_id for e in study["gpt-5.6-sol"] if e.block_index == 0]
    terra0 = [e.overlay_id for e in study["gpt-5.6-terra"] if e.block_index == 0]
    assert sol0 != terra0  # one rng advanced model-by-model


def test_frozen_schedule_file_matches_regeneration():
    on_disk = json.loads(_SCHEDULE_JSON.read_text())
    fresh = build_phase_6b_schedule_artifact()
    assert on_disk["study_schedule_sha256"] == fresh["study_schedule_sha256"]
    assert on_disk["scheduling_seed"] == PHASE_6B_SCHEDULE_SEED
    assert on_disk["trials_per_model"] == 160
