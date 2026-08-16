"""Wires transport + discovery + adapter + runner + reporting into one call."""

from __future__ import annotations

from app.models.benchmark import BenchmarkSuite
from app.models.evaluation import Report
from app.models.execution import ToolCallDecision
from app.reporting.builder import build_report
from app.runner.adapters import DeterministicFakeAdapter
from app.runner.engine import BenchmarkRunner
from app.runner.transport import MCPTransport


def build_fake_adapter(suite: BenchmarkSuite) -> DeterministicFakeAdapter:
    """Build a DeterministicFakeAdapter from a suite's simulated_agent_response fixtures."""
    responses: dict[str, ToolCallDecision] = {}
    for case in suite.cases:
        assert case.simulated_agent_response is not None
        responses[case.user_prompt] = ToolCallDecision(
            tool_name=case.simulated_agent_response.tool_name,
            arguments=case.simulated_agent_response.arguments,
        )
    return DeterministicFakeAdapter(responses)


async def execute_suite(run_id: str, suite: BenchmarkSuite, transport: MCPTransport) -> Report:
    """Run every case in ``suite`` against an already-open ``transport`` and score it."""
    tools = await transport.list_tools()
    adapter = build_fake_adapter(suite)
    runner = BenchmarkRunner(transport, adapter, tools)

    results = {case.id: await runner.run_case(case) for case in suite.cases}

    return build_report(run_id, suite.name, suite.cases, results, tools)
