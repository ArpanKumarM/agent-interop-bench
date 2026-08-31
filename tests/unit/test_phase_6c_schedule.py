"""Phase 6C: the four-model panel appends `claude-sonnet-5` after the three
OpenAI models by CONTINUING the same frozen Random(PHASE_6B_SCHEDULE_SEED)
stream. The three existing per-model schedules stay byte-identical; only the
overall study-schedule hash changes.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.runner.blocked_schedule import (
    PHASE_6B_MODEL_PANEL,
    PHASE_6B_OVERLAY_IDS,
    build_phase_6b_model_schedule,
    build_phase_6b_schedule_artifact,
    build_phase_6b_study_schedule,
    schedule_sha256,
)

_SCHEDULE_JSON = Path("benchmarks/composed/live_canary_v4_schedule.json")

# Frozen from Phase 6B.2 (three-model panel). MUST NOT change in 6C.
_FROZEN_EXISTING = {
    "gpt-5.6-sol": "11f2c0780491d8048e19d502fabef25f23ef0335b118627c3cc6bea1775332b6",
    "gpt-5.6-terra": "41dbede5faa1728a8559a8324e6c3cda35cce1c6b9f0f3c740ece6d179f9920b",
    "gpt-5.6-luna": "c653e2bf8b3f2ba320dd754d12f755c2705d9ef988e8a9a469e812eaa4e6a83c",
}
_CLAUDE_SCHEDULE_SHA256 = "191c6ff890c185d933d097885f2b9bfa7899c2835373375b00729c86a1345228"
_STUDY_SCHEDULE_SHA256 = "092b638ea9dd345e7507f7f859adc9af331e8785675f6ea52ec25ee0ac21f0e0"


def test_panel_is_the_four_models_in_frozen_order():
    assert PHASE_6B_MODEL_PANEL == (
        "gpt-5.6-sol",
        "gpt-5.6-terra",
        "gpt-5.6-luna",
        "claude-sonnet-5",
    )


def test_first_three_per_model_schedules_are_byte_identical_to_phase_6b():
    for model, expected in _FROZEN_EXISTING.items():
        assert schedule_sha256(build_phase_6b_model_schedule(model)) == expected


def test_claude_schedule_is_deterministic_and_the_stream_continuation():
    a = schedule_sha256(build_phase_6b_model_schedule("claude-sonnet-5"))
    b = schedule_sha256(build_phase_6b_model_schedule("claude-sonnet-5"))
    assert a == b == _CLAUDE_SCHEDULE_SHA256
    # distinct from every OpenAI model's block ordering
    assert a not in _FROZEN_EXISTING.values()


def test_every_model_sees_every_overlay_exactly_four_times():
    study = build_phase_6b_study_schedule()
    assert set(study) == set(PHASE_6B_MODEL_PANEL)
    for model, entries in study.items():
        assert len(entries) == 160, model
        counts: dict[str, int] = {}
        for e in entries:
            counts[e.overlay_id] = counts.get(e.overlay_id, 0) + 1
        assert set(counts) == set(PHASE_6B_OVERLAY_IDS)
        assert set(counts.values()) == {4}
        for block_index in range(4):
            block = sorted(e.overlay_id for e in entries if e.block_index == block_index)
            assert block == sorted(PHASE_6B_OVERLAY_IDS)


def test_total_planned_trials_is_640():
    study = build_phase_6b_study_schedule()
    assert sum(len(v) for v in study.values()) == 640
    assert len(study) * 160 == 640


def test_frozen_schedule_file_reflects_four_models():
    art = json.loads(_SCHEDULE_JSON.read_text())
    assert art["model_panel"] == list(PHASE_6B_MODEL_PANEL)
    assert art["trials_per_model"] == 160
    assert art["model_schedule_sha256"]["claude-sonnet-5"] == _CLAUDE_SCHEDULE_SHA256
    for model, expected in _FROZEN_EXISTING.items():
        assert art["model_schedule_sha256"][model] == expected
    assert art["study_schedule_sha256"] == _STUDY_SCHEDULE_SHA256


def test_frozen_schedule_file_matches_regeneration():
    on_disk = json.loads(_SCHEDULE_JSON.read_text())
    assert on_disk == build_phase_6b_schedule_artifact()
