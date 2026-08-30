"""The GLOBAL provider-decision budget for an entire pilot run (Phase
4A.3a) -- independent of, and enforced in addition to, each trial's own
per-trial ``max_decisions`` (``RealHostAgentAdapter``'s existing cap).

Trials are not the billing unit; provider decisions are. The budget is
checked BEFORE every single provider call, across every trial and every
overlay in the run: ``GlobalBudgetHostAdapter`` wraps whatever adapter
would otherwise make the call and refuses to even delegate to it once the
budget is exhausted, so exhaustion can never result in one more provider
call than the configured maximum.
"""

from __future__ import annotations

from app.models.composed import HostActionSpec
from app.models.host_context import HostDecisionContext
from app.runner.host_adapters import HostAgentAdapter


class PilotBudgetExhaustedError(RuntimeError):
    """Raised instead of delegating to the underlying adapter once the
    global provider-decision budget is exhausted -- no additional provider
    call is ever made after this point in a run."""


class GlobalDecisionBudget:
    """A plain, shared counter: ``try_consume()`` is the only way to spend
    budget, and it either succeeds (incrementing) or fails (leaving the
    budget untouched) -- there is no path to over-spending it."""

    def __init__(self, max_total_decisions: int) -> None:
        if max_total_decisions < 1:
            raise ValueError(f"max_total_decisions must be >= 1, got {max_total_decisions}")
        self._max_total_decisions = max_total_decisions
        self._used = 0

    def try_consume(self) -> bool:
        if self._used >= self._max_total_decisions:
            return False
        self._used += 1
        return True

    @property
    def used(self) -> int:
        return self._used

    @property
    def remaining(self) -> int:
        return self._max_total_decisions - self._used

    @property
    def max_total_decisions(self) -> int:
        return self._max_total_decisions


class GlobalBudgetHostAdapter(HostAgentAdapter):
    """Wraps any ``HostAgentAdapter`` (real or a test double), enforcing the
    shared ``GlobalDecisionBudget`` before ever delegating a decision."""

    def __init__(self, delegate: HostAgentAdapter, budget: GlobalDecisionBudget) -> None:
        self._delegate = delegate
        self._budget = budget

    async def decide(self, context: HostDecisionContext) -> HostActionSpec:
        if not self._budget.try_consume():
            raise PilotBudgetExhaustedError(
                f"Global provider-decision budget exhausted "
                f"({self._budget.max_total_decisions} decisions); refusing to make "
                "another provider call for the remainder of this run."
            )
        return await self._delegate.decide(context)
