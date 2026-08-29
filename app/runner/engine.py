"""Deterministic benchmark runner: a bounded decision -> validate -> execute loop.

Each case runs a turn loop, capped at ``case.max_turns`` (1 by default, i.e.
single-turn): ask the adapter for a decision, validate and gate it, execute
the tool call if it's allowed to run, hand the result back to the adapter,
repeat. The loop always terminates for exactly one of three reasons —
``TerminationReason`` — and never runs more than ``max_turns`` iterations,
so there is no path to an unbounded loop regardless of what an adapter
returns.
"""

from __future__ import annotations

from app.models.benchmark import BenchmarkCase
from app.models.enums import FailureMode
from app.models.execution import RunResult, TerminationReason, ToolCallDecision, TurnResult
from app.models.tools import ToolDefinition
from app.runner.adapters import AgentAdapter
from app.runner.transport import MCPTransport, ToolCallOutcome

UNAPPROVED_MUTATION_MESSAGE = (
    "Blocked: mutating action requires pre-approval and none was granted for this case"
)


class BenchmarkRunner:
    """Executes benchmark cases against a connected MCP transport, one at a time."""

    def __init__(
        self,
        transport: MCPTransport,
        adapter: AgentAdapter,
        tool_definitions: list[ToolDefinition],
    ) -> None:
        self._transport = transport
        self._adapter = adapter
        self._tools_by_name = {tool.name: tool for tool in tool_definitions}

    async def run_case(self, case: BenchmarkCase) -> RunResult:
        tools = list(self._tools_by_name.values())
        turns: list[TurnResult] = []
        termination_reason = TerminationReason.MAX_TURNS_REACHED
        # Which turn indices actually see the case's simulated_failure_mode;
        # every other turn gets NORMAL regardless of what tool is called.
        # None (every case before Phase 2D) means exactly {0}, preserving
        # the original turn-0-only behavior byte-for-byte.
        injected_turns = set(case.injected_turns) if case.injected_turns is not None else {0}

        for turn_index in range(case.max_turns):
            decision = await self._adapter.decide(case.user_prompt, tools, turns)
            failure_mode = (
                case.simulated_failure_mode if turn_index in injected_turns else FailureMode.NORMAL
            )

            if decision.tool_name is None:
                turns.append(
                    TurnResult(
                        turn_index=turn_index,
                        requested_tool=None,
                        requested_arguments=decision.arguments,
                        decision_rationale=decision.rationale,
                        stopped=True,
                        executed=False,
                        failure_mode_applied=failure_mode,
                    )
                )
                termination_reason = TerminationReason.VOLUNTARY_STOP
                break

            blocked_turn = self._blocked_turn(case, decision, turn_index, failure_mode)
            if blocked_turn is not None:
                turns.append(blocked_turn)
                termination_reason = TerminationReason.BLOCKED_UNSAFE
                break

            outcome = await self._transport.call_tool(
                decision.tool_name,
                {**decision.arguments, "failure_mode": failure_mode.value},
                timeout_seconds=case.max_latency_ms / 1000,
            )
            turns.append(self._executed_turn(case, decision, outcome, turn_index, failure_mode))

        return RunResult(
            case_id=case.id,
            turns=turns,
            termination_reason=termination_reason,
            failure_mode_applied=case.simulated_failure_mode,
        )

    def _blocked_turn(
        self,
        case: BenchmarkCase,
        decision: ToolCallDecision,
        turn_index: int,
        failure_mode: FailureMode,
    ) -> TurnResult | None:
        """The mutation safety gate: applied identically to every turn, not just the first.

        An agent hijacked mid-interaction into requesting a mutation is
        exactly as untrusted as one that requested it on turn one — the
        gate never conditions on which turn it is.
        """
        tool_def = self._tools_by_name.get(decision.tool_name)
        if tool_def is None or not tool_def.is_mutating or case.approved_mutation:
            return None

        return TurnResult(
            turn_index=turn_index,
            requested_tool=decision.tool_name,
            requested_arguments=decision.arguments,
            decision_rationale=decision.rationale,
            tool_known=True,
            is_mutating=True,
            mutation_approved=False,
            blocked_unsafe=True,
            blocked_reason=UNAPPROVED_MUTATION_MESSAGE,
            executed=False,
            error=UNAPPROVED_MUTATION_MESSAGE,
            is_error_result=True,
            failure_mode_applied=failure_mode,
        )

    def _executed_turn(
        self,
        case: BenchmarkCase,
        decision: ToolCallDecision,
        outcome: ToolCallOutcome,
        turn_index: int,
        failure_mode: FailureMode,
    ) -> TurnResult:
        tool_def = self._tools_by_name.get(decision.tool_name)
        return TurnResult(
            turn_index=turn_index,
            requested_tool=decision.tool_name,
            requested_arguments=decision.arguments,
            decision_rationale=decision.rationale,
            tool_known=tool_def is not None,
            is_mutating=tool_def.is_mutating if tool_def is not None else None,
            mutation_approved=case.approved_mutation if tool_def is not None else None,
            executed=True,
            tool_output=outcome.structured_output,
            raw_text_output=outcome.text_output,
            error=outcome.error_message,
            is_error_result=outcome.is_error,
            timed_out=outcome.timed_out,
            tool_not_found=outcome.tool_not_found,
            latency_ms=outcome.latency_ms,
            failure_mode_applied=failure_mode,
        )

    async def run_suite(self, cases: list[BenchmarkCase]) -> list[RunResult]:
        return [await self.run_case(case) for case in cases]
