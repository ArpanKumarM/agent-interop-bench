"""Phase 4A.1: the sanitized HostDecisionContext/ObservableEvent schemas
must never declare a field carrying benchmark ground truth or
fixture-authored provenance labels -- checked structurally, at the model
level, independent of any particular run's data.
"""

from __future__ import annotations

from app.models.host_context import HostDecisionContext, ObservableEvent

BANNED_FIELD_NAMES = {
    "expected_outcome",
    "category",
    "content_class",
    "origin_trust",
    "sensitivity",
    "canary_ids",
    "propagated_canary_ids",
    "adversarial_ancestor_ids",
    "sensitive_ancestor_ids",
    "allowed_sensitive_edges",
    "evaluator_name",
    "passed",
    "applicable",
    "simulated_host_actions",
    "simulated_remote_behavior",
    "simulated_client_actions",
    "expected_task_state",
    "expected_artifact",
    "provenance_canaries",
    "action_triggers",
}


def test_host_decision_context_declares_no_banned_fields():
    assert set(HostDecisionContext.model_fields) & BANNED_FIELD_NAMES == set()


def test_observable_event_declares_no_banned_fields():
    assert set(ObservableEvent.model_fields) & BANNED_FIELD_NAMES == set()


def test_host_decision_context_declares_exactly_the_specified_fields():
    assert set(HostDecisionContext.model_fields) == {
        "user_prompt",
        "host_policy",
        "history",
        "available_tools",
        "target_agent_card",
        "current_step",
    }


def test_observable_event_declares_only_protocol_observable_facts():
    assert set(ObservableEvent.model_fields) == {
        "seq",
        "event_type",
        "source",
        "dest",
        "protocol",
        "payload",
        "is_mutating",
        "approved",
        "executed",
    }
