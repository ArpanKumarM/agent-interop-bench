"""Wires transport + discovery + adapter + runner + reporting into one call."""

from __future__ import annotations

from app.models.benchmark import BenchmarkSuite
from app.models.evaluation import Report
from app.models.execution import ToolCallDecision
from app.reporting.builder import build_report
from app.runner.adapters import AgentAdapter, DeterministicFakeAdapter
from app.runner.engine import BenchmarkRunner
from app.runner.transport import MCPTransport


def build_fake_adapter(suite: BenchmarkSuite) -> DeterministicFakeAdapter:
    """Build a DeterministicFakeAdapter from a suite's fixture responses.

    ``simulated_agent_response`` drives turn 0 for every case.
    ``simulated_reaction``, when a case sets it, drives turn 1 — the
    decision the adapter makes after observing turn 0's tool output. Cases
    that don't set it get a one-entry script, so the runner's turn loop
    (bounded by ``max_turns``, 1 by default) never asks for a second
    decision in the first place.
    """
    scripts: dict[str, list[ToolCallDecision]] = {}
    for case in suite.cases:
        assert case.simulated_agent_response is not None
        script = [
            ToolCallDecision(
                tool_name=case.simulated_agent_response.tool_name,
                arguments=case.simulated_agent_response.arguments,
            )
        ]
        if case.simulated_reaction is not None:
            script.append(
                ToolCallDecision(
                    tool_name=case.simulated_reaction.tool_name,
                    arguments=case.simulated_reaction.arguments,
                )
            )
        scripts[case.user_prompt] = script
    return DeterministicFakeAdapter(scripts)


async def execute_suite(
    run_id: str,
    suite: BenchmarkSuite,
    transport: MCPTransport,
    *,
    adapter: AgentAdapter | None = None,
    case_ids: list[str] | None = None,
) -> Report:
    """Run cases from ``suite`` against an already-open ``transport`` and score them.

    ``adapter`` defaults to ``None``, which builds the free, deterministic
    ``DeterministicFakeAdapter`` from the suite's own fixtures — this is the
    unchanged Phase 1/2A/2B behavior every existing caller relies on, and no
    provider SDK is imported or touched on this path. Passing a real
    ``AgentAdapter`` (e.g. ``OpenAIResponsesAdapter``) here is the only hook
    Phase 2C needed to add live-model execution; nothing about
    ``BenchmarkRunner``, evaluators, or scoring changed to support it.

    ``case_ids``, when given, restricts execution to that subset (in the
    suite's own order) instead of the full suite — used by live-model runs
    to bound provider cost; ``None`` runs every case, as before.
    """
    tools = await transport.list_tools()
    resolved_adapter = adapter if adapter is not None else build_fake_adapter(suite)
    runner = BenchmarkRunner(transport, resolved_adapter, tools)

    # Provider-neutral hook: if this adapter carries a `provenance` object
    # (real-model adapters do; DeterministicFakeAdapter/PlaceholderAdapter
    # don't), record the exact discovered tool schemas it was given, so a
    # live run's provenance is auditable against the actual tool surface at
    # execution time. No OpenAI-specific import here — see
    # app/runner/tool_schema_openai.py for the one place that shape lives.
    provenance = getattr(resolved_adapter, "provenance", None)
    if provenance is not None and not provenance.tool_schema_sha256:
        from app.runner.tool_schema_openai import tool_schema_fingerprint

        provenance.tool_schema_sha256 = tool_schema_fingerprint(tools)

    cases = suite.cases
    if case_ids is not None:
        wanted = set(case_ids)
        cases = [case for case in suite.cases if case.id in wanted]

    results = {}
    for case in cases:
        if hasattr(resolved_adapter, "bind_case"):
            resolved_adapter.bind_case(case.id)
        results[case.id] = await runner.run_case(case)

    return build_report(run_id, suite.name, cases, results, tools)
