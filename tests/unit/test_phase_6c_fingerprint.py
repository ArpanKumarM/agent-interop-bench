"""Phase 6C: the provider inference interface participates in execution
fingerprint v2, and Phase 4B fingerprint-v1 verification stays byte-
identical.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.live_overlays import load_live_overlays
from app.models.execution_fingerprint import ExecutionFingerprint
from app.models.pilot_plan import PilotExperimentPlan
from app.runner.execution_fingerprint import _combine, compute_execution_fingerprint_v2
from app.runner.model_panel import provider_config_sha256

_CANON = ("relay_to_remote", "call_tool", "stop")
_FROZEN_4B_FP = Path(
    "reports/experiments/composed-live-canary-003-sol-attempt-1/execution_fingerprint.json"
)


def _plan(model: str = "gpt-5.6-sol") -> PilotExperimentPlan:
    return PilotExperimentPlan(
        experiment_id="composed-live-canary-004",
        experiment_version="v4",
        model=model,
        overlay_ids=["rq1-saas-support-confidential"],
        trials_per_condition=40,
        max_decisions_per_trial=1,
        max_total_decisions=160,
        timeout_seconds=20.0,
        max_output_tokens=512,
        execution_mode="decision_point",
    )


def _overlays():
    return load_live_overlays("benchmarks/composed/live_overlays_v2.yaml").overlays[:1]


def _fp(model: str, *, provider_hash: str | None = None):
    return compute_execution_fingerprint_v2(
        _plan(model),
        _overlays(),
        canonical_actions=_CANON,
        source_commit_sha="deadbeef",
        schedule_sha256="s" * 64,
        provider_config_sha256=(
            provider_hash
            if provider_hash is not None
            else provider_config_sha256(model, canonical_actions=_CANON, timeout_seconds=20.0)
        ),
    )


def test_provider_config_participates_in_the_fingerprint():
    fp = _fp("claude-sonnet-5")
    assert fp.provider_config_sha256 and len(fp.provider_config_sha256) == 64
    # dropping the provider config yields a different combined hash
    without = compute_execution_fingerprint_v2(
        _plan("claude-sonnet-5"),
        _overlays(),
        canonical_actions=_CANON,
        source_commit_sha="deadbeef",
        schedule_sha256="s" * 64,
    )
    assert without.provider_config_sha256 is None
    assert without.execution_fingerprint_sha256 != fp.execution_fingerprint_sha256


def test_changing_anthropic_model_id_changes_the_fingerprint():
    base = provider_config_sha256("claude-sonnet-5", canonical_actions=_CANON, timeout_seconds=20.0)
    other = provider_config_sha256(
        "claude-sonnet-5-1990", canonical_actions=_CANON, timeout_seconds=20.0
    )
    assert base != other
    assert (
        _fp("claude-sonnet-5", provider_hash=base).execution_fingerprint_sha256
        != _fp("claude-sonnet-5", provider_hash=other).execution_fingerprint_sha256
    )


def test_changing_anthropic_effort_mode_changes_the_provider_hash(monkeypatch):
    import app.runner.model_panel as mp

    base = provider_config_sha256("claude-sonnet-5", canonical_actions=_CANON, timeout_seconds=20.0)
    monkeypatch.setattr(mp, "LOW_EFFORT", "medium")
    changed = mp.provider_config_sha256(
        "claude-sonnet-5", canonical_actions=_CANON, timeout_seconds=20.0
    )
    assert base != changed


def test_changing_anthropic_wire_schema_changes_the_provider_hash(monkeypatch):
    import app.runner.model_panel as mp

    base = provider_config_sha256("claude-sonnet-5", canonical_actions=_CANON, timeout_seconds=20.0)

    def _fake_wire(_actions):
        return "f" * 64

    monkeypatch.setattr(mp, "anthropic_wire_tool_schema_sha256", _fake_wire)
    changed = mp.provider_config_sha256(
        "claude-sonnet-5", canonical_actions=_CANON, timeout_seconds=20.0
    )
    assert base != changed


def test_openai_and_anthropic_have_distinct_provider_hashes():
    o = provider_config_sha256("gpt-5.6-sol", canonical_actions=_CANON, timeout_seconds=20.0)
    a = provider_config_sha256("claude-sonnet-5", canonical_actions=_CANON, timeout_seconds=20.0)
    assert o != a


def test_each_of_the_three_openai_models_has_its_own_provider_hash():
    hs = {
        m: provider_config_sha256(m, canonical_actions=_CANON, timeout_seconds=20.0)
        for m in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna")
    }
    assert len(set(hs.values())) == 3


def test_phase_4b_v1_fingerprint_still_recombines_byte_identically():
    data = json.loads(_FROZEN_4B_FP.read_text())
    fp = ExecutionFingerprint.model_validate(data)
    assert fp.fingerprint_version == "v1"
    assert fp.provider_config_sha256 is None
    recomputed = _combine(
        config_hash=fp.config_hash,
        source_commit_sha=fp.source_commit_sha,
        resolved_overlay_bundle_sha256=fp.resolved_overlay_bundle_sha256,
        host_policy_sha256=fp.host_policy_sha256,
        tool_schema_sha256=fp.tool_schema_sha256,
        schedule_sha256=fp.schedule_sha256,
    )
    assert recomputed == fp.execution_fingerprint_sha256


def test_v2_without_provider_config_is_unchanged_from_pre_6c():
    """A v2 fingerprint that passes no provider config must _combine exactly
    as it did before Phase 6C (the field is folded in only when present)."""
    fp = compute_execution_fingerprint_v2(
        _plan(),
        _overlays(),
        canonical_actions=("call_tool", "stop"),
        source_commit_sha="x",
        schedule_sha256="s" * 64,
        uv_lock_hash="l" * 64,
        py_version="3.12.2",
    )
    assert fp.execution_fingerprint_sha256 == _combine(
        config_hash=fp.config_hash,
        source_commit_sha="x",
        resolved_overlay_bundle_sha256=fp.resolved_overlay_bundle_sha256,
        host_policy_sha256=fp.host_policy_sha256,
        tool_schema_sha256=fp.tool_schema_sha256,
        schedule_sha256="s" * 64,
        canonical_action_schema_sha256=fp.canonical_action_schema_sha256,
        uv_lock_sha256="l" * 64,
        python_runtime_version="3.12.2",
    )
