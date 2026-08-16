from app.models.evaluation import CaseReport, EvaluationResult
from app.reporting.scoring import build_summary


def _case_report(case_id, passed, evaluations, latency_ms=10.0) -> CaseReport:
    return CaseReport(
        case_id=case_id,
        category="correct_tool_selection",
        expected_outcome="success",
        passed=passed,
        latency_ms=latency_ms,
        evaluations=evaluations,
        failure_reasons=[] if passed else ["something failed"],
    )


def test_build_summary_counts_and_rates():
    reports = [
        _case_report(
            "c1",
            True,
            [
                EvaluationResult(
                    evaluator_name="tool_selection_accuracy", passed=True, reason="ok"
                ),
                EvaluationResult(evaluator_name="argument_correctness", passed=True, reason="ok"),
            ],
        ),
        _case_report(
            "c2",
            False,
            [
                EvaluationResult(
                    evaluator_name="tool_selection_accuracy", passed=False, reason="wrong"
                ),
                EvaluationResult(
                    evaluator_name="argument_correctness",
                    applicable=False,
                    passed=True,
                    reason="n/a",
                ),
            ],
        ),
    ]

    summary = build_summary(reports)
    assert summary.total_tests == 2
    assert summary.passed_tests == 1
    assert summary.failed_tests == 1
    assert summary.tool_selection_accuracy == 0.5
    # Only one case has an applicable argument_correctness evaluation, and it passed.
    assert summary.argument_accuracy == 1.0


def test_build_summary_none_when_no_applicable_cases():
    reports = [
        _case_report(
            "c1",
            True,
            [
                EvaluationResult(
                    evaluator_name="timeout_recovery",
                    applicable=False,
                    passed=True,
                    reason="n/a",
                )
            ],
        )
    ]
    summary = build_summary(reports)
    assert summary.recovery_rate is None


def test_build_summary_empty_reports():
    summary = build_summary([])
    assert summary.total_tests == 0
    assert summary.average_latency_ms == 0.0
    assert summary.tool_selection_accuracy is None
