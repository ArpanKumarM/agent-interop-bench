"""Phase 8 wiring into app.cli.composed_live_pilot (docs/phase_8_change_list.md
S4.2). Every check here makes NO provider call: real-adapter construction
happens only in ``run_live``, never reached from these tests.
"""

from __future__ import annotations

import asyncio

import app.cli.composed_live_pilot as clp
from app.models.composed import HostActionSpec
from app.models.composed_provenance import ComposedModelRunProvenance
from app.runner.blocked_schedule import ScheduledTrial
from app.runner.decision_point_pilot import run_decision_point_pilot
from app.runner.host_adapters import HostAgentAdapter
from app.runner.pilot_ledger import TrialLedger
from mock_servers.phase_8_fixtures import PHASE_8_OPERATIONAL_POLICY_TEXT

_ALL_V8 = ("v8a", "v8a2", "v8b", "v8c", "v8d")


def test_every_substudy_plan_loads_and_resolves():
    for sub in _ALL_V8:
        plan = clp.load_frozen_plan("gpt-5.6-sol", sub)
        overlays = clp.resolve_overlays(plan)
        assert len(overlays) == len(plan.overlay_ids)
        assert plan.execution_mode == "decision_point"


def test_canonical_actions_per_substudy():
    expected = {
        "v8a": {"relay_to_remote", "reply_to_user", "stop"},
        "v8a2": {"relay_to_remote", "stop"},
        "v8b": {"relay_to_remote", "stop"},
        "v8c": {"relay_to_remote", "stop"},
        "v8d": {"relay_to_remote", "stop"},
    }
    for sub in _ALL_V8:
        plan = clp.load_frozen_plan("gpt-5.6-sol", sub)
        assert set(clp._canonical_actions_for(plan)) == expected[sub]


def test_host_policy_text_is_operational_only_for_v8d():
    for sub in _ALL_V8:
        plan = clp.load_frozen_plan("gpt-5.6-sol", sub)
        text = clp._host_policy_text_for(plan)
        if sub == "v8d":
            assert text == PHASE_8_OPERATIONAL_POLICY_TEXT
        else:
            assert text != PHASE_8_OPERATIONAL_POLICY_TEXT


def test_resolve_schedule_matches_blocked_schedule_builder():
    from app.runner.blocked_schedule import build_phase_8_model_schedule

    for sub in _ALL_V8:
        plan = clp.load_frozen_plan("gpt-5.6-sol", sub)
        schedule = clp._resolve_schedule(plan)
        assert schedule == build_phase_8_model_schedule(sub, "gpt-5.6-sol")


def test_resolve_schedule_rejects_model_outside_panel():
    import pytest

    plan = clp.load_frozen_plan("not-a-real-model", "v8a")
    with pytest.raises(clp.ComposedLivePilotConfigError):
        clp._resolve_schedule(plan)


def test_preflight_report_v8a_makes_no_provider_call_and_has_expected_shape():
    plan = clp.load_frozen_plan("gpt-5.6-sol", "v8a")
    report = clp.preflight_report(plan, "unit-test-v8a-preflight")
    assert report["provider_calls_made"] == 0
    assert report["execution_mode"] == "decision_point"
    assert report["fingerprint_version"] == "v2"
    assert set(report["canonical_actions"]) == {"relay_to_remote", "reply_to_user", "stop"}
    assert report["blocked_schedule"]["trials_in_schedule"] == 864


def test_preflight_report_v8d_uses_operational_policy_hash():
    plan_strict = clp.load_frozen_plan("gpt-5.6-sol", "v8a")
    plan_operational = clp.load_frozen_plan("gpt-5.6-sol", "v8d")
    strict = clp.preflight_report(plan_strict, "unit-test-v8a-policy")
    operational = clp.preflight_report(plan_operational, "unit-test-v8d-policy")
    assert strict["host_policy_sha256"] != operational["host_policy_sha256"]


class _StubProvenanceAdapter(HostAgentAdapter):
    """Mirrors composed_live_pilot._DryRunAdapter's provenance shape, but
    returns the sink-appropriate action instead of always stopping -- so a
    real end-to-end dispatch can exercise reply_to_user / relay_to_remote
    through the actual CLI wiring (adapter-factory selection, host-policy
    selection, fingerprinting) without any network or provider call."""

    def __init__(self, case_id: str, max_decisions: int, allowed_actions: tuple[str, ...]) -> None:
        self._allowed = allowed_actions
        self.provenance = ComposedModelRunProvenance(
            adapter_type="test_stub",
            provider="none",
            requested_model="test-stub",
            host_policy_sha256="0" * 64,
            tool_schema_sha256="0" * 64,
            configured_timeout_seconds=0.0,
            configured_max_retries=0,
            configured_max_output_tokens=0,
        )

    async def decide(self, context):
        if "reply_to_user" in self._allowed:
            return HostActionSpec(action="reply_to_user", relay_template="hi there")
        if "relay_to_remote" in self._allowed:
            return HostActionSpec(
                action="relay_to_remote", relay_template="hi there", content_type="text/plain"
            )
        return HostActionSpec(action="stop")


def _run_two_trials(sub: str, overlay_a: str, overlay_b: str, tmp_path) -> list:
    plan = clp.load_frozen_plan("gpt-5.6-sol", sub)
    plan = plan.model_copy(update={"overlay_ids": [overlay_a, overlay_b]})
    overlays = clp.resolve_overlays(plan)
    schedule = [
        ScheduledTrial(
            model=plan.model,
            block_index=0,
            position_in_block=i,
            experiment="sensitive_egress",
            condition=overlay.condition,
            overlay_id=overlay.id,
            trial_index=0,
        )
        for i, overlay in enumerate(overlays)
    ]
    ledger = TrialLedger(tmp_path / "run")
    records = asyncio.run(
        run_decision_point_pilot(
            plan,
            overlays,
            ledger,
            _StubProvenanceAdapter,
            clp.local_transport_factory,
            execution_fingerprint=None,
            schedule=schedule,
        )
    )
    return records


def test_end_to_end_v8a_both_sinks_through_cli_wiring(tmp_path):
    records = _run_two_trials(
        "v8a",
        "p8a-saas-support-unlabeled-a2a_relay",
        "p8a-saas-support-unlabeled-user_reply",
        tmp_path,
    )
    assert len(records) == 2
    by_id = {r.overlay_id: r for r in records}
    a2a = by_id["p8a-saas-support-unlabeled-a2a_relay"]
    reply = by_id["p8a-saas-support-unlabeled-user_reply"]
    assert a2a.status == "completed"
    assert reply.status == "completed"
    assert a2a.outcomes.relay_initiated is True
    assert reply.outcomes.reply_initiated is True
    assert any(e.event_type == "a2a_message" for e in a2a.events)
    assert any(e.event_type == "host_user_reply" for e in reply.events)
    assert all(e.event_type != "host_user_reply" for e in a2a.events)
    assert all(e.event_type != "a2a_message" for e in reply.events)


def test_end_to_end_v8d_operational_policy_through_cli_wiring(tmp_path):
    records = _run_two_trials(
        "v8d", "p8d-saas-support-unlabeled", "p8d-saas-support-public", tmp_path
    )
    assert len(records) == 2
    for record in records:
        assert record.status == "completed"
        assert record.outcomes.relay_initiated is True
