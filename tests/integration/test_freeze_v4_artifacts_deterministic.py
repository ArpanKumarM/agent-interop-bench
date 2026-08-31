"""The frozen Phase 6B artifacts must be exactly reproducible from the
generator (app.cli.freeze_v4_artifacts) -- no hand edits, no drift."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from app.cli.freeze_v4_artifacts import (
    OVERLAYS_PATH,
    PLAN_PATH,
    SCHEDULE_PATH,
    build_overlays_doc,
    build_plan_doc,
)
from app.runner.blocked_schedule import build_phase_6b_schedule_artifact


def test_overlays_v2_matches_generator():
    on_disk = yaml.safe_load(Path(OVERLAYS_PATH).read_text())
    assert on_disk == build_overlays_doc()
    assert len(on_disk["overlays"]) == 40


def test_plan_v4_matches_generator():
    on_disk = json.loads(Path(PLAN_PATH).read_text())
    assert on_disk == build_plan_doc()
    assert on_disk["experiment_id"] == "composed-live-canary-004"
    assert on_disk["trials_per_condition"] == 40
    assert on_disk["max_total_decisions"] == 160
    assert len(on_disk["overlay_ids"]) == 40


def test_schedule_v4_matches_generator():
    on_disk = json.loads(Path(SCHEDULE_PATH).read_text())
    fresh = build_phase_6b_schedule_artifact()
    assert on_disk == fresh
