"""Wires the A2A mock agent + adapter + runner + reporting into one call,
structurally parallel to ``app.runner.suite_execution`` for MCP but sharing
no execution code with it (only the top-level ``Report``/``ScoreSummary``
envelope is genuinely shared — see the Phase 3A/3B.0 architecture audit)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.evaluators.a2a_registry import evaluate_a2a_case
from app.models.a2a import A2ABenchmarkSuite
from app.models.evaluation import CaseReport, Report
from app.reporting.a2a_scoring import build_a2a_summary
from app.runner.a2a_adapters import A2AAgentAdapter, build_a2a_fixture_adapter
from app.runner.a2a_engine import A2ABenchmarkRunner
from mock_servers.a2a_mock import build_a2a_mock_app


async def execute_a2a_suite(
    run_id: str,
    suite: A2ABenchmarkSuite,
    *,
    adapter: A2AAgentAdapter | None = None,
    case_ids: list[str] | None = None,
) -> Report:
    """Run cases from ``suite`` and score them.

    ``adapter`` defaults to ``None``, which builds the free, deterministic
    ``DeterministicA2AAdapter`` from the suite's own fixtures. No network
    call ever occurs: each case gets a fresh in-process mock agent exercised
    via ``TestClient`` (no sockets).
    """
    resolved_adapter = adapter if adapter is not None else build_a2a_fixture_adapter(suite)

    cases = suite.cases
    if case_ids is not None:
        wanted = set(case_ids)
        cases = [case for case in suite.cases if case.id in wanted]

    case_reports: list[CaseReport] = []
    for case in cases:
        mock_app = build_a2a_mock_app(
            case.target_agent_card, case.simulated_remote_behavior, case.id
        )
        with TestClient(mock_app) as client:
            runner = A2ABenchmarkRunner(client, resolved_adapter)
            interactions = await runner.run_case(case)

        evaluations = evaluate_a2a_case(case, interactions)
        applicable = [e for e in evaluations if e.applicable]
        passed = all(e.passed for e in applicable)
        failure_reasons = [e.reason for e in applicable if not e.passed]

        case_reports.append(
            CaseReport(
                case_id=case.id,
                category=case.category,
                expected_outcome=case.expected_outcome,
                passed=passed,
                latency_ms=0.0,
                termination_reason=(
                    interactions[-1].termination_classification if interactions else "unknown"
                ),
                evaluations=evaluations,
                failure_reasons=failure_reasons,
                protocol="a2a",
                protocol_version="1.0",
                protocol_binding="http+json",
                turns=None,
                a2a_interactions=interactions,
            )
        )

    summary = build_a2a_summary(case_reports)
    return Report(
        run_id=run_id,
        suite_name=suite.name,
        suite_version=suite.version,
        summary=summary,
        per_test=case_reports,
    )
