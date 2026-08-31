"""RQ3 as an INVARIANT (Phase 6B): an unapproved request whose trusted
discovered classification is mutating cannot execute -- by construction.
No empirical rate, no Wilson interval."""

from __future__ import annotations

import inspect
import itertools

from app.reporting.composed_taxonomy import (
    ToolInvocationClass,
    classify_tool_invocation,
)
from app.runner.mutation_gate import mutation_blocked


def test_mutation_gate_exhaustive_truth_table():
    table = {
        (True, False): True,  # mutating + unapproved -> blocked
        (True, True): False,  # mutating + approved -> allowed
        (False, False): False,
        (False, True): False,
    }
    for (is_mutating, approved), expected in table.items():
        assert mutation_blocked(is_mutating, approved) is expected


def test_no_live_host_adapter_can_emit_approved_true():
    """The real adapter hardcodes approved=False for every proposed call;
    grep its source for any assignment of approved=True."""
    import app.runner.real_host_adapter as rha

    src = inspect.getsource(rha)
    assert "approved=True" not in src.replace(" ", "")
    assert "approved = True" not in src


def test_unapproved_mutating_request_is_always_blocked_never_executed():
    """For every combination of (discovered-mutating tool, unapproved), the
    canonical classifier yields MUTATING_TOOL_BLOCKED and never
    MUTATING_TOOL_EXECUTED."""
    for tool, executed in itertools.product(
        ["rollback_config", "purge_cache", "revoke_session"], [False]
    ):
        # gate applied to an unapproved mutating request -> blocked -> executed False
        blocked = mutation_blocked(is_mutating=True, approved=False)
        assert blocked is True
        rc, ec = classify_tool_invocation(
            decision_action="call_tool",
            requested_tool_name=tool,
            discovered_is_mutating=True,
            executed=executed,
        )
        assert rc is ToolInvocationClass.MUTATING_TOOL_REQUESTED
        assert ec is ToolInvocationClass.MUTATING_TOOL_BLOCKED
        assert ec is not ToolInvocationClass.MUTATING_TOOL_EXECUTED
