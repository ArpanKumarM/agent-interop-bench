"""Unit tests for the global provider-decision budget."""

from __future__ import annotations

import pytest

from app.models.composed import HostActionSpec
from app.runner.host_adapters import HostAgentAdapter
from app.runner.pilot_budget import (
    GlobalBudgetHostAdapter,
    GlobalDecisionBudget,
    PilotBudgetExhaustedError,
)


class _CountingAdapter(HostAgentAdapter):
    def __init__(self) -> None:
        self.call_count = 0

    async def decide(self, context):
        self.call_count += 1
        return HostActionSpec(action="stop")


def test_try_consume_succeeds_until_max_then_fails():
    budget = GlobalDecisionBudget(max_total_decisions=3)
    assert budget.try_consume() is True
    assert budget.try_consume() is True
    assert budget.try_consume() is True
    assert budget.try_consume() is False
    assert budget.used == 3
    assert budget.remaining == 0


def test_failed_consume_does_not_increment_used():
    budget = GlobalDecisionBudget(max_total_decisions=1)
    assert budget.try_consume() is True
    assert budget.try_consume() is False
    assert budget.try_consume() is False
    assert budget.used == 1


def test_zero_or_negative_max_rejected():
    with pytest.raises(ValueError, match="max_total_decisions"):
        GlobalDecisionBudget(max_total_decisions=0)


async def test_global_budget_host_adapter_blocks_delegate_once_exhausted():
    budget = GlobalDecisionBudget(max_total_decisions=1)
    delegate = _CountingAdapter()
    adapter = GlobalBudgetHostAdapter(delegate, budget)

    await adapter.decide(context=None)
    assert delegate.call_count == 1

    with pytest.raises(PilotBudgetExhaustedError, match="budget exhausted"):
        await adapter.decide(context=None)

    # The exhausted call never reached the delegate -- no extra provider call.
    assert delegate.call_count == 1


async def test_shared_budget_is_enforced_across_multiple_adapters():
    """The whole point of a GLOBAL budget: two different adapter instances
    (e.g. two different trials) sharing one budget object must never
    collectively exceed it."""
    budget = GlobalDecisionBudget(max_total_decisions=2)
    delegate_a = _CountingAdapter()
    delegate_b = _CountingAdapter()
    adapter_a = GlobalBudgetHostAdapter(delegate_a, budget)
    adapter_b = GlobalBudgetHostAdapter(delegate_b, budget)

    await adapter_a.decide(context=None)
    await adapter_b.decide(context=None)
    with pytest.raises(PilotBudgetExhaustedError):
        await adapter_a.decide(context=None)
    with pytest.raises(PilotBudgetExhaustedError):
        await adapter_b.decide(context=None)

    assert delegate_a.call_count == 1
    assert delegate_b.call_count == 1
