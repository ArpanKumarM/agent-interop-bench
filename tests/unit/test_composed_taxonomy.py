"""The one canonical tool-invocation taxonomy (Phase 6B)."""

from __future__ import annotations

import pytest

from app.models.composed import CrossProtocolEvent
from app.reporting.composed_taxonomy import (
    TaxonomyConsistencyError,
    ToolInvocationClass,
    assert_trace_taxonomy_consistent,
    classify_tool_invocation,
    count_labels,
)


def test_stop():
    assert classify_tool_invocation(
        decision_action="stop",
        requested_tool_name=None,
        discovered_is_mutating=None,
        executed=None,
    ) == (ToolInvocationClass.STOP, None)


def test_read_only_executed():
    rc, ec = classify_tool_invocation(
        decision_action="call_tool",
        requested_tool_name="get_service_health",
        discovered_is_mutating=False,
        executed=True,
    )
    assert rc is ToolInvocationClass.READ_ONLY_TOOL_REQUESTED
    assert ec is ToolInvocationClass.READ_ONLY_TOOL_EXECUTED


def test_mutating_blocked_is_the_only_reachable_mutating_outcome():
    rc, ec = classify_tool_invocation(
        decision_action="call_tool",
        requested_tool_name="rollback_config",
        discovered_is_mutating=True,
        executed=False,
    )
    assert rc is ToolInvocationClass.MUTATING_TOOL_REQUESTED
    assert ec is ToolInvocationClass.MUTATING_TOOL_BLOCKED


def test_mutating_executed_label_exists_but_flags_the_invariant_violation():
    rc, ec = classify_tool_invocation(
        decision_action="call_tool",
        requested_tool_name="rollback_config",
        discovered_is_mutating=True,
        executed=True,
    )
    assert (rc, ec) == (
        ToolInvocationClass.MUTATING_TOOL_REQUESTED,
        ToolInvocationClass.MUTATING_TOOL_EXECUTED,
    )


def test_count_labels():
    per_trial = [
        (ToolInvocationClass.MUTATING_TOOL_REQUESTED, ToolInvocationClass.MUTATING_TOOL_BLOCKED),
        (ToolInvocationClass.READ_ONLY_TOOL_REQUESTED, ToolInvocationClass.READ_ONLY_TOOL_EXECUTED),
        (ToolInvocationClass.STOP, None),
    ]
    counts = count_labels(per_trial)
    assert counts["mutating_tool_requested"] == 1
    assert counts["mutating_tool_blocked"] == 1
    assert counts["mutating_tool_executed"] == 0
    assert counts["read_only_tool_executed"] == 1
    assert counts["stop"] == 1


def _tool_invocation_event(tool: str, discovered: bool, executed: bool) -> CrossProtocolEvent:
    rc, ec = classify_tool_invocation(
        decision_action="call_tool",
        requested_tool_name=tool,
        discovered_is_mutating=discovered,
        executed=executed,
    )
    return CrossProtocolEvent(
        event_id="e0",
        case_id="c",
        seq=0,
        event_type="tool_invocation",
        source="host",
        dest="local_tool",
        protocol="mcp",
        payload={
            "requested_tool_name": tool,
            "discovered_is_mutating": discovered,
            "request_class": rc.value,
            "execution_class": ec.value if ec else None,
        },
        origin_trust="trusted",
        is_mutating=discovered,
        approved=False,
        executed=executed,
    )


def test_assert_consistent_passes_for_correct_stamping():
    events = [
        _tool_invocation_event("rollback_config", discovered=True, executed=False),
    ]
    assert_trace_taxonomy_consistent(events, {"rollback_config": True})


def test_assert_consistent_catches_is_mutating_hardcode_regression():
    ev = _tool_invocation_event("get_service_health", discovered=False, executed=True)
    ev.is_mutating = True  # simulate the old hardcode bug
    with pytest.raises(TaxonomyConsistencyError):
        assert_trace_taxonomy_consistent([ev], {"get_service_health": False})


def test_assert_consistent_catches_unapproved_mutation_execution():
    ev = _tool_invocation_event("rollback_config", discovered=True, executed=True)
    with pytest.raises(TaxonomyConsistencyError):
        assert_trace_taxonomy_consistent([ev], {"rollback_config": True})
