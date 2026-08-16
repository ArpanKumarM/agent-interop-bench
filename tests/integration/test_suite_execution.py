from app.core.benchmarks import load_benchmark_suite
from app.runner.suite_execution import execute_suite
from tests.integration.conftest import make_mock_transport


async def test_full_suite_executes_and_produces_report():
    suite = load_benchmark_suite("benchmarks/")
    async with make_mock_transport() as transport:
        report = await execute_suite("test-run-1", suite, transport)

    assert report.run_id == "test-run-1"
    assert report.summary.total_tests == len(suite.cases)
    # Every case must produce a scored result — none silently skipped.
    assert len(report.per_test) == len(suite.cases)
    assert {c.case_id for c in report.per_test} == {c.id for c in suite.cases}


async def test_unapproved_mutation_is_blocked_end_to_end():
    suite = load_benchmark_suite("benchmarks/")
    async with make_mock_transport() as transport:
        report = await execute_suite("test-run-2", suite, transport)

    unsafe_case = next(
        c for c in report.per_test if c.case_id == "unsafe-001-create-comment-unapproved"
    )
    safety_eval = next(
        e for e in unsafe_case.evaluations if e.evaluator_name == "unsafe_action_detection"
    )
    assert safety_eval.passed is True
    assert safety_eval.evidence["blocked_unsafe"] is True


async def test_approved_mutation_is_allowed_end_to_end():
    suite = load_benchmark_suite("benchmarks/")
    async with make_mock_transport() as transport:
        report = await execute_suite("test-run-3", suite, transport)

    approved_case = next(
        c for c in report.per_test if c.case_id == "unsafe-002-create-comment-approved"
    )
    assert approved_case.passed is True


async def test_hallucinated_tool_is_flagged_not_crashed():
    suite = load_benchmark_suite("benchmarks/")
    async with make_mock_transport() as transport:
        report = await execute_suite("test-run-4", suite, transport)

    hallucinated = next(
        c for c in report.per_test if c.case_id == "hallucinated-001-delete-repository"
    )
    tool_selection_eval = next(
        e for e in hallucinated.evaluations if e.evaluator_name == "tool_selection_accuracy"
    )
    assert tool_selection_eval.evidence["hallucinated"] is True
