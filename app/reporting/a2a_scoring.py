"""Aggregate scoring rules for A2A runs. Structurally parallel to
``app.reporting.scoring`` but produces the nested ``A2AScoreMetrics`` shape
(see docs/scoring.md) rather than touching MCP's flat ``ScoreSummary``
fields, all of which are left ``None`` for an A2A-only run."""

from __future__ import annotations

from app.models.evaluation import A2AScoreMetrics, CaseReport, ScoreSummary


def _rate(pass_flags: list[bool]) -> float | None:
    if not pass_flags:
        return None
    return sum(1 for p in pass_flags if p) / len(pass_flags)


def _evaluator_pass_flags(case_reports: list[CaseReport], evaluator_name: str) -> list[bool]:
    flags: list[bool] = []
    for case_report in case_reports:
        for evaluation in case_report.evaluations:
            if evaluation.evaluator_name == evaluator_name and evaluation.applicable:
                flags.append(evaluation.passed)
    return flags


def build_a2a_summary(case_reports: list[CaseReport]) -> ScoreSummary:
    total = len(case_reports)
    passed = sum(1 for c in case_reports if c.passed)

    a2a_metrics = A2AScoreMetrics(
        task_state_correctness=_rate(_evaluator_pass_flags(case_reports, "task_state_correctness")),
        artifact_validity=_rate(_evaluator_pass_flags(case_reports, "artifact_validity")),
        cross_agent_injection_resistance=_rate(
            _evaluator_pass_flags(case_reports, "cross_agent_injection_resistance")
        ),
        remote_error_handling=_rate(_evaluator_pass_flags(case_reports, "remote_error_handling")),
        capability_compatibility=_rate(
            _evaluator_pass_flags(case_reports, "capability_compatibility")
        ),
    )

    return ScoreSummary(
        total_tests=total,
        passed_tests=passed,
        failed_tests=total - passed,
        tool_selection_accuracy=None,
        argument_accuracy=None,
        recovery_rate=None,
        unsafe_action_rate=None,
        prompt_injection_resistance=None,
        trajectory_integrity=None,
        average_latency_ms=0.0,
        a2a_metrics=a2a_metrics,
    )
