"""Builds a complete Report from benchmark cases and their run results."""

from __future__ import annotations

from app.evaluators.registry import evaluate_case
from app.models.benchmark import BenchmarkCase
from app.models.evaluation import CaseReport, Report
from app.models.execution import RunResult
from app.models.tools import ToolDefinition
from app.reporting.scoring import build_summary


def build_case_report(
    case: BenchmarkCase,
    result: RunResult,
    tools_by_name: dict[str, ToolDefinition],
) -> CaseReport:
    evaluations = evaluate_case(case, result, tools_by_name)
    applicable = [e for e in evaluations if e.applicable]
    passed = all(e.passed for e in applicable)
    failure_reasons = [e.reason for e in applicable if not e.passed]

    return CaseReport(
        case_id=case.id,
        category=case.category.value,
        expected_outcome=case.expected_outcome.value,
        passed=passed,
        latency_ms=result.latency_ms,
        turns=result.turns,
        termination_reason=result.termination_reason,
        evaluations=evaluations,
        failure_reasons=failure_reasons,
    )


def build_report(
    run_id: str,
    suite_name: str,
    cases: list[BenchmarkCase],
    results: dict[str, RunResult],
    tool_definitions: list[ToolDefinition],
) -> Report:
    tools_by_name = {tool.name: tool for tool in tool_definitions}
    case_reports = [
        build_case_report(case, results[case.id], tools_by_name)
        for case in cases
        if case.id in results
    ]
    summary = build_summary(case_reports)
    return Report(run_id=run_id, suite_name=suite_name, summary=summary, per_test=case_reports)
