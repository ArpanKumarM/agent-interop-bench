"""Deterministic benchmark runner: adapter decision -> safety gate -> tool execution."""

from __future__ import annotations

from app.models.benchmark import BenchmarkCase
from app.models.execution import RunResult
from app.models.tools import ToolDefinition
from app.runner.adapters import AgentAdapter
from app.runner.transport import MCPTransport

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
        decision = await self._adapter.select_tool(
            case.user_prompt, list(self._tools_by_name.values())
        )

        if decision.tool_name is None:
            return RunResult(
                case_id=case.id,
                selected_tool=None,
                selected_arguments=decision.arguments,
                latency_ms=0.0,
                failure_mode_applied=case.simulated_failure_mode,
            )

        tool_def = self._tools_by_name.get(decision.tool_name)

        if tool_def is not None and tool_def.is_mutating and not case.approved_mutation:
            return RunResult(
                case_id=case.id,
                selected_tool=decision.tool_name,
                selected_arguments=decision.arguments,
                error=UNAPPROVED_MUTATION_MESSAGE,
                is_error_result=True,
                latency_ms=0.0,
                failure_mode_applied=case.simulated_failure_mode,
                blocked_unsafe=True,
            )

        call_arguments = dict(decision.arguments)
        call_arguments["failure_mode"] = case.simulated_failure_mode.value

        outcome = await self._transport.call_tool(
            decision.tool_name,
            call_arguments,
            timeout_seconds=case.max_latency_ms / 1000,
        )

        return RunResult(
            case_id=case.id,
            selected_tool=decision.tool_name,
            selected_arguments=decision.arguments,
            tool_output=outcome.structured_output,
            raw_text_output=outcome.text_output,
            error=outcome.error_message,
            is_error_result=outcome.is_error,
            latency_ms=outcome.latency_ms,
            failure_mode_applied=case.simulated_failure_mode,
            timed_out=outcome.timed_out,
            tool_not_found=outcome.tool_not_found,
        )

    async def run_suite(self, cases: list[BenchmarkCase]) -> list[RunResult]:
        return [await self.run_case(case) for case in cases]
