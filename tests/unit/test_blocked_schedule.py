"""Phase 4B kickoff: the deterministic BLOCKED trial schedule.

No provider call anywhere (autouse socket guard). Proves the schedule
contract, its determinism, and that its hash enters the execution
fingerprint -- without altering any prompt, overlay, policy, action
surface, or outcome logic.
"""

from __future__ import annotations

import json
import socket
from collections import Counter
from pathlib import Path

import pytest

from app.cli.composed_live_pilot import load_frozen_plan, resolve_overlays
from app.core.live_overlays import load_live_overlays
from app.runner.blocked_schedule import (
    CELLS,
    PHASE_4B_BLOCKS_PER_MODEL,
    PHASE_4B_MODEL_PANEL,
    PHASE_4B_SCHEDULE_SEED,
    build_model_schedule,
    build_schedule_artifact,
    build_study_schedule,
    schedule_sha256,
)
from app.runner.execution_fingerprint import compute_execution_fingerprint

_SCHEDULE_FILE = Path("benchmarks/composed/live_canary_v3_schedule.json")
_CELLKEYS = {(e, c) for (e, c, _o) in CELLS}


@pytest.fixture(autouse=True)
def _no_sockets():
    def boom(self, address):
        raise AssertionError(f"blocked-schedule test attempted a socket to {address}")

    orig = socket.socket.connect
    socket.socket.connect = boom
    try:
        yield
    finally:
        socket.socket.connect = orig


def test_panel_and_seed_are_frozen_exactly():
    assert PHASE_4B_MODEL_PANEL == ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")
    assert PHASE_4B_SCHEDULE_SEED == 20260401
    assert PHASE_4B_BLOCKS_PER_MODEL == 20
    assert len(CELLS) == 4


def test_exactly_20_observations_per_cell_per_model():
    study = build_study_schedule()
    for model in PHASE_4B_MODEL_PANEL:
        entries = study[model]
        assert len(entries) == 80
        counts = Counter((e.experiment, e.condition) for e in entries)
        assert set(counts) == _CELLKEYS
        assert all(v == 20 for v in counts.values()), counts
        # trial_index runs 0..19 exactly once per cell
        for key in _CELLKEYS:
            idxs = sorted(e.trial_index for e in entries if (e.experiment, e.condition) == key)
            assert idxs == list(range(20))


def test_every_block_contains_all_four_cells_exactly_once():
    study = build_study_schedule()
    for model in PHASE_4B_MODEL_PANEL:
        for block in range(PHASE_4B_BLOCKS_PER_MODEL):
            block_entries = [e for e in study[model] if e.block_index == block]
            assert len(block_entries) == 4
            assert {(e.experiment, e.condition) for e in block_entries} == _CELLKEYS
            assert sorted(e.position_in_block for e in block_entries) == [0, 1, 2, 3]


def test_deterministic_seed_gives_identical_schedule():
    a = build_study_schedule(seed=PHASE_4B_SCHEDULE_SEED)
    b = build_study_schedule(seed=PHASE_4B_SCHEDULE_SEED)
    assert {m: [e.model_dump() for e in v] for m, v in a.items()} == {
        m: [e.model_dump() for e in v] for m, v in b.items()
    }
    for model in PHASE_4B_MODEL_PANEL:
        assert schedule_sha256(a[model]) == schedule_sha256(b[model])


def test_different_seed_gives_different_ordering():
    base = build_study_schedule(seed=PHASE_4B_SCHEDULE_SEED)
    other = build_study_schedule(seed=PHASE_4B_SCHEDULE_SEED + 1)
    # every model's ordering changes, and its schedule hash changes
    for model in PHASE_4B_MODEL_PANEL:
        assert [(e.block_index, e.position_in_block, e.overlay_id) for e in base[model]] != [
            (e.block_index, e.position_in_block, e.overlay_id) for e in other[model]
        ]
        assert schedule_sha256(base[model]) != schedule_sha256(other[model])
    # ... while the per-cell counts are still exactly 20 (blocked invariant holds)
    for model in PHASE_4B_MODEL_PANEL:
        counts = Counter((e.experiment, e.condition) for e in other[model])
        assert all(v == 20 for v in counts.values())


def test_schedule_hash_enters_the_execution_fingerprint():
    plan = load_frozen_plan("gpt-5.6-sol", "v3")
    overlays = resolve_overlays(plan)
    sol_sched = build_model_schedule("gpt-5.6-sol")
    terra_sched = build_model_schedule("gpt-5.6-terra")

    fp_no_sched = compute_execution_fingerprint(
        plan, overlays, source_commit_sha="c", tool_schema_sha256="t"
    )
    fp_sol = compute_execution_fingerprint(
        plan,
        overlays,
        source_commit_sha="c",
        tool_schema_sha256="t",
        schedule_sha256=schedule_sha256(sol_sched),
    )
    fp_terra = compute_execution_fingerprint(
        plan,
        overlays,
        source_commit_sha="c",
        tool_schema_sha256="t",
        schedule_sha256=schedule_sha256(terra_sched),
    )
    assert fp_sol.schedule_sha256 == schedule_sha256(sol_sched)
    assert fp_sol.execution_fingerprint_sha256 != fp_no_sched.execution_fingerprint_sha256
    assert fp_sol.execution_fingerprint_sha256 != fp_terra.execution_fingerprint_sha256


def test_absent_schedule_leaves_pre_phase_4b_fingerprint_byte_identical():
    # the frozen v2 fingerprint (Phase 4A.3f inputs) must be unchanged by the
    # addition of the optional schedule_sha256 field.
    plan = load_frozen_plan("gpt-5.6-terra", "v2")
    overlays = resolve_overlays(plan)
    fp = compute_execution_fingerprint(
        plan,
        overlays,
        source_commit_sha="084073dcfe9a4961baa1cff99a7a85bc60392d66",
        tool_schema_sha256="efa354c3b7ba9bf5050d32f152ed29f583c7348063184dfb5a8989cf26304b85",
    )
    assert fp.schedule_sha256 is None
    assert (
        fp.execution_fingerprint_sha256
        == "7722de918b515f72283323851d6b8e786367fb66af93a1054998404c993d797d"
    )


def test_treatment_control_stimuli_unchanged_from_phase_4b_design():
    # v3 resolves the identical four overlays; the resolved-overlay bundle
    # hash matches the value frozen in Phase 4A.3f/4B (same overlays).
    plan = load_frozen_plan("gpt-5.6-sol", "v3")
    overlays = resolve_overlays(plan)
    assert [o.id for o in overlays] == [
        "live-sensitive-egress-treatment",
        "live-sensitive-egress-control",
        "live-influence-treatment",
        "live-influence-control",
    ]
    fp = compute_execution_fingerprint(
        plan, overlays, source_commit_sha="c", tool_schema_sha256="t"
    )
    assert (
        fp.resolved_overlay_bundle_sha256
        == "9e4a500eb15635976e3f9ea60905011b1ee057df4b32bcfa9e311f3219125896"
    )
    # and the raw overlay objects are byte-identical to a direct load
    direct = {
        o.id: o for o in load_live_overlays("benchmarks/composed/live_overlays.yaml").overlays
    }
    for o in overlays:
        assert o.model_dump() == direct[o.id].model_dump()


def test_committed_schedule_artifact_matches_the_builder_exactly():
    assert _SCHEDULE_FILE.exists()
    on_disk = json.loads(_SCHEDULE_FILE.read_text())
    rebuilt = build_schedule_artifact()
    assert on_disk == rebuilt
    assert on_disk["scheduling_seed"] == PHASE_4B_SCHEDULE_SEED
    assert on_disk["model_panel"] == list(PHASE_4B_MODEL_PANEL)
    assert set(on_disk["model_schedule_sha256"]) == set(PHASE_4B_MODEL_PANEL)


def test_v3_plan_config_hash_is_deterministic_and_distinct_from_v1_v2():
    a = load_frozen_plan("gpt-5.6-sol", "v3").config_hash
    b = load_frozen_plan("gpt-5.6-sol", "v3").config_hash
    assert a == b
    assert a != load_frozen_plan("gpt-5.6-sol", "v1").config_hash
    assert a != load_frozen_plan("gpt-5.6-sol", "v2").config_hash
    # a different model -> a different config_hash (model is in the hash)
    assert a != load_frozen_plan("gpt-5.6-terra", "v3").config_hash


def test_v3_plan_frozen_fields():
    plan = load_frozen_plan("gpt-5.6-sol", "v3")
    assert plan.experiment_id == "composed-live-canary-003"
    assert plan.experiment_version == "v3"
    assert plan.execution_mode == "decision_point"
    assert plan.trials_per_condition == 20
    assert plan.max_decisions_per_trial == 1
    assert plan.max_total_decisions == 80
    assert plan.timeout_seconds == 20.0
    assert plan.max_output_tokens == 512
    assert plan.reasoning_effort == "low"
    assert len(plan.overlay_ids) == 4


def test_build_model_schedule_rejects_a_model_outside_the_panel():
    with pytest.raises(ValueError, match="not in the frozen Phase 4B panel"):
        build_model_schedule("gpt-5.6-nova")


def test_v3_cli_resolves_the_frozen_per_model_schedule_as_dispatch_order():
    from app.cli import composed_live_pilot as cli

    plan = load_frozen_plan("gpt-5.6-terra", "v3")
    schedule = cli._resolve_schedule(plan)
    assert schedule == build_model_schedule("gpt-5.6-terra")
    order = [(e.overlay_id, e.trial_index) for e in schedule]
    assert len(order) == 80
    assert Counter(oid for oid, _ in order) == {oid: 20 for oid in plan.overlay_ids}
    # v1/v2 plans have no blocked schedule
    assert cli._resolve_schedule(load_frozen_plan("m", "v2")) is None
    assert cli._resolve_schedule(load_frozen_plan("m", "v1")) is None


def test_v3_cli_refuses_a_model_outside_the_frozen_panel():
    from app.cli import composed_live_pilot as cli

    with pytest.raises(cli.ComposedLivePilotConfigError, match="not in the frozen Phase 4B panel"):
        cli._resolve_schedule(load_frozen_plan("gpt-5.6-nova", "v3"))


def test_ledger_persists_schedule_and_resume_refuses_a_rerandomised_one(tmp_path):
    from app.runner.pilot_ledger import PilotResumeScheduleMismatchError, TrialLedger

    original = build_model_schedule("gpt-5.6-sol")
    ledger = TrialLedger(tmp_path / "run")
    ledger.write_or_verify_schedule(original)

    persisted = json.loads((tmp_path / "run" / "schedule.json").read_text())
    assert persisted["schedule_sha256"] == schedule_sha256(original)
    assert len(persisted["entries"]) == 80

    # a reopened ledger with the SAME frozen schedule verifies fine
    TrialLedger(tmp_path / "run").write_or_verify_schedule(build_model_schedule("gpt-5.6-sol"))
    # a re-randomised order (different seed) is refused
    reshuffled = build_study_schedule(seed=PHASE_4B_SCHEDULE_SEED + 7)["gpt-5.6-sol"]
    with pytest.raises(PilotResumeScheduleMismatchError):
        TrialLedger(tmp_path / "run").write_or_verify_schedule(reshuffled)
