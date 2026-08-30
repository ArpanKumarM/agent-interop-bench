"""Unit tests for the Phase 3D.1 composed models: deterministic IDs/canary
tokens, and the DAG invariants enforced by ComposedBenchmarkRunner._append
(parent must already exist, parent.seq < child.seq)."""

from __future__ import annotations

import pytest

from app.models.a2a import A2ARemoteStep, AgentCard, AgentInterface
from app.models.composed import (
    ComposedBenchmarkCase,
    HostActionSpec,
    canary_token,
    composed_deterministic_id,
)
from app.runner.composed_engine import ComposedBenchmarkRunner


def _dummy_case(case_id: str = "dummy-case") -> ComposedBenchmarkCase:
    return ComposedBenchmarkCase(
        id=case_id,
        category="composed_benign",
        user_prompt="test",
        expected_outcome="success",
        target_agent_card=AgentCard(
            name="test-agent",
            supported_interfaces=[
                AgentInterface(
                    url="http://test", protocol_binding="HTTP_JSON", protocol_version="1.0"
                )
            ],
        ),
        simulated_host_actions=[HostActionSpec(action="stop")],
        simulated_remote_behavior=[A2ARemoteStep(task_state="TASK_STATE_COMPLETED")],
    )


def test_composed_deterministic_id_is_stable_and_input_sensitive():
    assert composed_deterministic_id("case-a", "event", "0") == composed_deterministic_id(
        "case-a", "event", "0"
    )
    assert composed_deterministic_id("case-a", "event", "0") != composed_deterministic_id(
        "case-a", "event", "1"
    )
    assert composed_deterministic_id("case-a", "event", "0") != composed_deterministic_id(
        "case-b", "event", "0"
    )


def test_canary_token_is_deterministic_and_syntactically_inert():
    token_a = canary_token("case-a", "secret-1")
    token_b = canary_token("case-a", "secret-1")
    assert token_a == token_b
    assert token_a.startswith("⟦CANARY:")
    assert canary_token("case-a", "secret-2") != token_a


def test_append_rejects_nonexistent_parent():
    case = _dummy_case()
    runner = ComposedBenchmarkRunner(local_transport_factory=lambda: None)  # never called
    with pytest.raises(ValueError, match="does not exist"):
        runner._append(
            case,
            event_type="a2a_message",
            source="host",
            dest="remote",
            protocol="a2a",
            payload={},
            parent_event_ids=["nonexistent-event-id"],
        )


def test_append_builds_valid_chain_and_rejects_forward_reference():
    case = _dummy_case()
    runner = ComposedBenchmarkRunner(local_transport_factory=lambda: None)
    first = runner._append(
        case,
        event_type="a2a_message",
        source="host",
        dest="remote",
        protocol="a2a",
        payload={"text": "hello"},
        parent_event_ids=[],
    )
    second = runner._append(
        case,
        event_type="a2a_task_state_transition",
        source="remote",
        dest="host",
        protocol="a2a",
        payload={"to_state": "TASK_STATE_COMPLETED"},
        parent_event_ids=[first.event_id],
    )
    assert first.seq < second.seq
    assert second.parent_event_ids == [first.event_id]

    # A node can never name a not-yet-created event as its parent -- the
    # append-only construction makes a cycle structurally unrepresentable.
    with pytest.raises(ValueError, match="does not exist"):
        runner._append(
            case,
            event_type="a2a_artifact",
            source="remote",
            dest="host",
            protocol="a2a",
            payload={},
            parent_event_ids=["some-future-event-id-that-does-not-exist-yet"],
        )
