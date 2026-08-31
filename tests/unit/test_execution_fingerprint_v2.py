"""Execution fingerprint v2 (Phase 6B): adds uv.lock SHA-256 + Python
runtime version + canonical action-schema hash; v1 verification stays
byte-compatible."""

from __future__ import annotations

import json
from pathlib import Path

from app.models.execution_fingerprint import ExecutionFingerprint
from app.models.pilot_plan import PilotExperimentPlan
from app.runner.execution_fingerprint import (
    compute_execution_fingerprint,
    compute_execution_fingerprint_v2,
    python_runtime_version,
    uv_lock_sha256,
)

_FROZEN_4B_FP = Path(
    "reports/experiments/composed-live-canary-003-sol-attempt-1/execution_fingerprint.json"
)


def _plan() -> PilotExperimentPlan:
    return PilotExperimentPlan(
        experiment_id="composed-live-canary-004",
        experiment_version="v4",
        model="gpt-5.6-sol",
        overlay_ids=["rq1-saas-support-confidential"],
        trials_per_condition=40,
        max_decisions_per_trial=1,
        max_total_decisions=160,
        timeout_seconds=20.0,
        max_output_tokens=512,
        execution_mode="decision_point",
    )


def test_v2_has_all_eight_inputs():
    from app.core.live_overlays import load_live_overlays

    overlays = load_live_overlays("benchmarks/composed/live_overlays_v2.yaml").overlays[:1]
    fp = compute_execution_fingerprint_v2(
        _plan(),
        overlays,
        canonical_actions=("relay_to_remote", "call_tool", "stop"),
        source_commit_sha="deadbeef",
        schedule_sha256="s" * 64,
    )
    assert fp.fingerprint_version == "v2"
    assert fp.canonical_action_schema_sha256
    assert fp.uv_lock_sha256 == uv_lock_sha256()
    assert fp.python_runtime_version == python_runtime_version()
    assert len(fp.execution_fingerprint_sha256) == 64


def test_v2_hash_changes_when_uv_lock_hash_changes():
    from app.core.live_overlays import load_live_overlays

    overlays = load_live_overlays("benchmarks/composed/live_overlays_v2.yaml").overlays[:1]
    common = dict(
        canonical_actions=("call_tool", "stop"),
        source_commit_sha="deadbeef",
        schedule_sha256="s" * 64,
        py_version="3.12.2",
    )
    a = compute_execution_fingerprint_v2(_plan(), overlays, uv_lock_hash="a" * 64, **common)
    b = compute_execution_fingerprint_v2(_plan(), overlays, uv_lock_hash="b" * 64, **common)
    assert a.execution_fingerprint_sha256 != b.execution_fingerprint_sha256


def test_v1_frozen_phase_4b_fingerprint_still_validates_and_recombines():
    """The frozen Phase 4B v1 fingerprint has none of the v2 inputs; it must
    still load and its recorded execution_fingerprint_sha256 must equal a
    fresh _combine over exactly its six components (byte-compatible)."""
    from app.runner.execution_fingerprint import _combine

    data = json.loads(_FROZEN_4B_FP.read_text())
    fp = ExecutionFingerprint.model_validate(data)
    assert fp.fingerprint_version == "v1"
    assert fp.canonical_action_schema_sha256 is None
    assert fp.uv_lock_sha256 is None
    recomputed = _combine(
        config_hash=fp.config_hash,
        source_commit_sha=fp.source_commit_sha,
        resolved_overlay_bundle_sha256=fp.resolved_overlay_bundle_sha256,
        host_policy_sha256=fp.host_policy_sha256,
        tool_schema_sha256=fp.tool_schema_sha256,
        schedule_sha256=fp.schedule_sha256,
    )
    assert recomputed == fp.execution_fingerprint_sha256


def test_v1_compute_path_unchanged():
    """compute_execution_fingerprint (v1) must not fold in any v2 input."""
    from app.core.live_overlays import load_live_overlays
    from app.runner.execution_fingerprint import _combine

    overlays = load_live_overlays("benchmarks/composed/live_overlays.yaml").overlays
    plan = PilotExperimentPlan(
        experiment_id="composed-live-canary-003",
        experiment_version="v3",
        model="gpt-5.6-sol",
        overlay_ids=[o.id for o in overlays],
        trials_per_condition=20,
        max_decisions_per_trial=1,
        max_total_decisions=80,
        timeout_seconds=20.0,
        max_output_tokens=512,
        execution_mode="decision_point",
    )
    fp = compute_execution_fingerprint(
        plan, overlays, source_commit_sha="x", tool_schema_sha256="t" * 64, schedule_sha256="s" * 64
    )
    assert fp.fingerprint_version == "v1"
    assert fp.execution_fingerprint_sha256 == _combine(
        config_hash=plan.config_hash,
        source_commit_sha="x",
        resolved_overlay_bundle_sha256=fp.resolved_overlay_bundle_sha256,
        host_policy_sha256=fp.host_policy_sha256,
        tool_schema_sha256="t" * 64,
        schedule_sha256="s" * 64,
    )
