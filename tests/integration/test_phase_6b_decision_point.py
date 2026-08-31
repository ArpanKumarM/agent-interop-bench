"""Phase 6B end-to-end decision-point trial (offline; a scripted adapter,
no provider call). Proves: the call_tool path, the tool_invocation event
records the DISCOVERED is_mutating (never hardcoded), the mutation gate
blocks an unapproved mutating request by construction, and the raw trace ==
online summary == offline taxonomy for mutating vs read-only execution.
"""

from __future__ import annotations

import socket

import pytest

from app.core.live_overlays import load_live_overlays
from app.models.composed import HostActionSpec
from app.models.composed_provenance import ComposedModelRunProvenance, ComposedProviderCallRecord
from app.models.host_context import HostDecisionContext
from app.models.pilot_plan import PilotExperimentPlan
from app.reporting.composed_taxonomy import (
    ToolInvocationClass,
    assert_trace_taxonomy_consistent,
    classify_trace,
)
from app.runner.decision_point_pilot import bootstrap_plan_for, run_decision_point_trial
from app.runner.host_adapters import HostAgentAdapter
from app.runner.pilot_budget import GlobalDecisionBudget
from mock_servers.composed_record_fixtures import PHASE_6B_DISCOVERED_IS_MUTATING
from tests.integration.test_composed_engine import make_composed_tool_transport

OVERLAYS_V2 = "benchmarks/composed/live_overlays_v2.yaml"


@pytest.fixture(autouse=True)
def _no_sockets():
    original = socket.socket.connect

    def boom(self, address):
        raise AssertionError(f"phase-6b test attempted a real socket to {address}")

    socket.socket.connect = boom
    try:
        yield
    finally:
        socket.socket.connect = original


def _overlay(overlay_id: str):
    (o,) = [o for o in load_live_overlays(OVERLAYS_V2).overlays if o.id == overlay_id]
    return o


class _ScriptedAdapter(HostAgentAdapter):
    def __init__(self, action: HostActionSpec) -> None:
        self._action = action
        self.provenance = ComposedModelRunProvenance(
            adapter_type="scripted-6b",
            provider="fake",
            requested_model="fake",
            host_policy_sha256="x" * 64,
            tool_schema_sha256="y" * 64,
            configured_timeout_seconds=5.0,
            configured_max_retries=0,
            configured_max_output_tokens=100,
        )

    async def decide(self, context: HostDecisionContext) -> HostActionSpec:
        self.provenance.provider_calls.append(
            ComposedProviderCallRecord(
                case_id="c",
                decision_index=len(self.provenance.provider_calls),
                requested_model="fake",
                returned_model="fake-r",
                input_tokens=1,
                output_tokens=1,
                total_tokens=2,
                latency_ms=1.0,
                observable_action=self._action.model_dump(),
                status="ok",
            )
        )
        return self._action


async def _run(overlay_id: str, action: HostActionSpec):
    spy = _ScriptedAdapter(action)
    plan = PilotExperimentPlan(
        experiment_id="composed-live-canary-004",
        experiment_version="v4",
        model="fake",
        overlay_ids=[overlay_id],
        trials_per_condition=1,
        max_decisions_per_trial=1,
        max_total_decisions=8,
        timeout_seconds=20.0,
        max_output_tokens=512,
        execution_mode="decision_point",
    )
    return await run_decision_point_trial(
        plan,
        _overlay(overlay_id),
        0,
        lambda case_id, max_decisions, allowed: spy,
        make_composed_tool_transport,
        GlobalDecisionBudget(8),
    )


def test_influence_action_surface_is_call_tool_only():
    _, allowed = bootstrap_plan_for(_overlay("rq2-rollback-orders-adversarial"))
    assert allowed == ("call_tool", "stop")


async def test_mutating_call_tool_is_blocked_by_construction():
    rec = await _run(
        "rq2-rollback-orders-adversarial",
        HostActionSpec(
            action="call_tool",
            tool_name="rollback_config",
            tool_arguments={"target": "orders-api@last-known-good"},
        ),
    )
    assert rec.status == "completed"
    inv = [e for e in rec.events if e.event_type == "tool_invocation"]
    assert len(inv) == 1
    ev = inv[0]
    # DISCOVERED value, not hardcoded
    assert ev.payload["discovered_is_mutating"] is True
    assert ev.is_mutating is True
    assert ev.executed is False
    assert ev.payload["gate_decision"] == "blocked"
    assert ev.payload["request_class"] == "mutating_tool_requested"
    assert ev.payload["execution_class"] == "mutating_tool_blocked"
    # canonical trace classification agrees
    rc, ecls = classify_trace(rec.events, rec.outcomes.decision_point_action)
    assert rc is ToolInvocationClass.MUTATING_TOOL_REQUESTED
    assert ecls is ToolInvocationClass.MUTATING_TOOL_BLOCKED
    assert rec.outcomes.mutating_tool_requested is True
    assert rec.outcomes.read_only_tool_requested is False
    assert_trace_taxonomy_consistent(rec.events, PHASE_6B_DISCOVERED_IS_MUTATING)


async def test_read_only_call_tool_executes_and_is_not_a_mutation():
    rec = await _run(
        "rq2-rollback-orders-adversarial",
        HostActionSpec(
            action="call_tool",
            tool_name="get_service_health",
            tool_arguments={"service": "orders-api"},
        ),
    )
    (ev,) = [e for e in rec.events if e.event_type == "tool_invocation"]
    assert ev.payload["discovered_is_mutating"] is False
    assert ev.is_mutating is False
    assert ev.executed is True
    assert ev.payload["request_class"] == "read_only_tool_requested"
    assert ev.payload["execution_class"] == "read_only_tool_executed"
    assert ev.payload["gate_decision"] is None  # gate not applied to a read-only call
    assert rec.outcomes.mutating_tool_requested is False
    assert rec.outcomes.read_only_tool_requested is True


async def test_rq1_confidential_relay_field_egress_detected():
    ov = _overlay("rq1-saas-support-confidential")
    email = ov.record_field_values["email"]
    rec = await _run(
        "rq1-saas-support-confidential",
        HostActionSpec(
            action="relay_to_remote",
            relay_template=f"Escalation: please email the customer at {email}.",
            content_type="text/plain",
        ),
    )
    assert rec.outcomes.relay_initiated is True
    assert rec.outcomes.any_field_value_egress is True
    assert "email" in rec.outcomes.field_types_copied
    assert rec.outcomes.disclosed_field_count == 1
    assert rec.outcomes.credential_token_copied is False


async def test_rq1_stop_counts_as_zero_egress_over_completed_trials():
    rec = await _run("rq1-saas-support-confidential", HostActionSpec(action="stop"))
    assert rec.status == "completed"
    assert rec.outcomes.relay_initiated is False
    assert rec.outcomes.any_field_value_egress is False
    assert rec.outcomes.disclosed_field_count == 0


async def test_raw_online_offline_taxonomy_agree():
    """raw trace event fields == online TrialOutcomes == offline classify_trace."""
    rec = await _run(
        "rq2-purge-pricing-adversarial",
        HostActionSpec(
            action="call_tool", tool_name="purge_cache", tool_arguments={"namespace": "pricing"}
        ),
    )
    (ev,) = [e for e in rec.events if e.event_type == "tool_invocation"]
    raw = (ev.payload["request_class"], ev.payload["execution_class"])
    online = (rec.outcomes.request_class, rec.outcomes.execution_class)
    rc, ecls = classify_trace(rec.events, rec.outcomes.decision_point_action)
    offline = (rc.value, ecls.value if ecls else None)
    assert raw == online == offline == ("mutating_tool_requested", "mutating_tool_blocked")
