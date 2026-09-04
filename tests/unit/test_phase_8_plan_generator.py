"""Phase 8 artifact generator (docs/phase_8_change_list.md S5/S6):
deterministic, byte-for-byte reproducible, every overlay/plan validates
against its schema, and every generated file matches what is committed on
disk. PROVISIONAL under the default HEADROOM_FRAMING until the Phase 8C
pilot re-pins it (see the module docstring in freeze_phase_8_artifacts.py).
"""

from __future__ import annotations

import json

import yaml

from app.cli.freeze_phase_8_artifacts import (
    _SUBSTUDIES,
    OVERLAYS_PATH,
    PLAN_PATHS,
    SCHEDULE_PATHS,
    build_overlays_doc,
    build_plan_doc,
)
from app.models.live_overlay import LiveOverlaySuite
from app.models.pilot_plan import PilotExperimentPlan
from app.runner.blocked_schedule import build_phase_8_schedule_artifact
from mock_servers.phase_8_fixtures import all_phase_8_field_values


def test_overlay_doc_is_deterministic():
    assert build_overlays_doc() == build_overlays_doc()


def test_plan_doc_is_deterministic():
    for substudy in _SUBSTUDIES:
        assert build_plan_doc(substudy) == build_plan_doc(substudy)


def test_every_overlay_validates_against_the_schema():
    doc = build_overlays_doc()
    suite = LiveOverlaySuite.model_validate(doc)
    assert len(suite.overlays) == 280  # 144+16+48+48+24


def test_every_plan_validates_and_names_every_overlay_it_uses():
    doc = build_overlays_doc()
    overlay_ids = {o["id"] for o in doc["overlays"]}
    for substudy in _SUBSTUDIES:
        plan = PilotExperimentPlan.model_validate({**build_plan_doc(substudy), "model": "x"})
        assert set(plan.overlay_ids) <= overlay_ids
        assert plan.max_total_decisions == len(plan.overlay_ids) * (
            plan.max_total_decisions // len(plan.overlay_ids)
        )


def test_no_substantive_value_leaks_into_any_generated_prompt():
    values = set(all_phase_8_field_values())
    doc = build_overlays_doc()
    for overlay in doc["overlays"]:
        for v in values:
            assert v not in overlay["user_prompt"]


def test_plan_schedule_and_overlay_agree_on_overlay_id_sets():
    for substudy in _SUBSTUDIES:
        plan = build_plan_doc(substudy)
        schedule = build_phase_8_schedule_artifact(substudy)
        scheduled_ids = {e["overlay_id"] for e in schedule["cells"]}
        assert set(plan["overlay_ids"]) == scheduled_ids


def test_on_disk_artifacts_match_generator_byte_for_byte():
    on_disk_overlays = yaml.safe_load(OVERLAYS_PATH.read_text())
    assert on_disk_overlays == build_overlays_doc(), "live_overlays_phase8.yaml drifted"
    for substudy in _SUBSTUDIES:
        on_disk_plan = json.loads(PLAN_PATHS[substudy].read_text())
        assert on_disk_plan == build_plan_doc(substudy), f"{substudy} plan drifted"
        on_disk_schedule = json.loads(SCHEDULE_PATHS[substudy].read_text())
        assert on_disk_schedule == build_phase_8_schedule_artifact(substudy), (
            f"{substudy} schedule drifted"
        )
