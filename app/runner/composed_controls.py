"""Actually executes a composed case's matched isolated controls through
the existing, unmodified MCP and A2A execution paths (Phase 3D.2.1) --
every field of ``ControlExecutionResult`` is always a real,
freshly-computed boolean from a real run, never hard-coded.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import NamedTuple

from app.models.a2a import A2ABenchmarkSuite
from app.models.benchmark import BenchmarkSuite
from app.models.composed import MatchedIsolatedControl
from app.runner.a2a_suite_execution import execute_a2a_suite
from app.runner.suite_execution import execute_suite
from app.runner.transport import MCPTransport


class ControlExecutionResult(NamedTuple):
    isolated_mcp_control_passed: bool
    isolated_a2a_control_passed: bool
    a2a_native_gap_control_passed: bool


async def run_matched_controls(
    control: MatchedIsolatedControl,
    mcp_transport_factory: Callable[[], MCPTransport],
) -> ControlExecutionResult:
    """Run ``control.mcp_control`` through the real, unmodified
    ``BenchmarkRunner``/MCP evaluators, and both ``control.a2a_control``
    (the TRUE public-twin matched control) and
    ``control.a2a_native_gap_control`` (the protocol-local-gap diagnostic,
    carrying the actual sensitive canary alone) through the real,
    unmodified ``A2ABenchmarkRunner``/A2A evaluators.
    """
    mcp_suite = BenchmarkSuite(
        name="composed-isolated-control", version="0.1.0", cases=[control.mcp_control]
    )
    async with mcp_transport_factory() as transport:
        mcp_report = await execute_suite("composed-isolated-control-mcp", mcp_suite, transport)
    isolated_mcp_control_passed = mcp_report.per_test[0].passed

    a2a_suite = A2ABenchmarkSuite(
        name="composed-isolated-control", version="0.1.0", cases=[control.a2a_control]
    )
    a2a_report = await execute_a2a_suite("composed-isolated-control-a2a", a2a_suite)
    isolated_a2a_control_passed = a2a_report.per_test[0].passed

    gap_suite = A2ABenchmarkSuite(
        name="composed-isolated-control-gap",
        version="0.1.0",
        cases=[control.a2a_native_gap_control],
    )
    gap_report = await execute_a2a_suite("composed-isolated-control-a2a-gap", gap_suite)
    a2a_native_gap_control_passed = gap_report.per_test[0].passed

    return ControlExecutionResult(
        isolated_mcp_control_passed=isolated_mcp_control_passed,
        isolated_a2a_control_passed=isolated_a2a_control_passed,
        a2a_native_gap_control_passed=a2a_native_gap_control_passed,
    )
