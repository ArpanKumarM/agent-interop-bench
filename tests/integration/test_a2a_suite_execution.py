"""Integration coverage for the Phase 3B A2A deterministic suite: loading,
per-case behavior for all 8 cases, two-run determinism, and async-path
(via the existing, unmodified ``RunManager``) vs. direct-execution
scientific equivalence.

No network call, no OpenAI, no live A2A agent: every case runs against a
fresh in-process FastAPI mock exercised through ``TestClient`` (see
``mock_servers/a2a_mock.py``).
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager

from app.api.repository import InMemoryRunRepository
from app.core.a2a_benchmarks import load_a2a_suite
from app.models.run import RunCreateRequest, RunStatus
from app.runner.a2a_suite_execution import execute_a2a_suite
from app.runner.run_manager import RunManager

A2A_SUITE_PATH = "benchmarks/a2a/a2a_suite.yaml"

STRIP_KEYS = {
    "run_id",
    "generated_at",
    "executed_at",
    "latency_ms",
    "average_latency_ms",
}


def _strip(obj):
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k not in STRIP_KEYS}
    if isinstance(obj, list):
        return [_strip(x) for x in obj]
    return obj


async def _run(case_ids=None):
    suite = load_a2a_suite(A2A_SUITE_PATH)
    return await execute_a2a_suite("a2a-test-run", suite, case_ids=case_ids)


def test_a2a_suite_loads_with_8_unique_cases():
    suite = load_a2a_suite(A2A_SUITE_PATH)
    assert suite.name == "agent-interop-a2a"
    assert suite.version == "0.1.0"
    ids = [c.id for c in suite.cases]
    assert len(ids) == 8
    assert len(set(ids)) == 8


async def test_full_a2a_suite_executes_and_produces_report():
    report = await _run()
    assert report.suite_name == "agent-interop-a2a"
    assert report.suite_version == "0.1.0"
    assert report.summary.total_tests == 8
    assert len(report.per_test) == 8
    assert {t.case_id for t in report.per_test} == {
        c.id for c in load_a2a_suite(A2A_SUITE_PATH).cases
    }
    for t in report.per_test:
        assert t.protocol == "a2a"
        assert t.turns is None
        assert t.a2a_interactions is not None


async def test_a2a_summary_scores_and_counts():
    report = await _run()
    s = report.summary
    assert s.total_tests == 8
    assert s.passed_tests == 5
    assert s.failed_tests == 3
    # MCP fields are untouched/null for an A2A-only run.
    assert s.tool_selection_accuracy is None
    assert s.argument_accuracy is None
    assert s.prompt_injection_resistance is None
    assert s.trajectory_integrity is None
    m = s.a2a_metrics
    assert m is not None
    assert m.task_state_correctness == 1.0
    assert m.artifact_validity == 0.5
    assert m.cross_agent_injection_resistance == 0.5
    assert m.remote_error_handling == 1.0
    assert m.capability_compatibility == 0.0


async def test_basic_task_completion_passes():
    report = await _run(case_ids=["a2a-correct-001-basic-task-completion"])
    t = report.per_test[0]
    assert t.passed is True
    assert t.a2a_interactions[-1].observed_task_state == "TASK_STATE_COMPLETED"


async def test_capability_case_fails_overall_despite_graceful_error_handling():
    report = await _run(case_ids=["a2a-capability-001-unsupported-input-mode"])
    t = report.per_test[0]
    by_name = {e.evaluator_name: e for e in t.evaluations if e.applicable}
    assert by_name["capability_compatibility"].passed is False
    assert by_name["remote_error_handling"].passed is True
    assert t.passed is False  # overall case fails: capability_compatibility is applicable and fails
    assert t.a2a_interactions[0].protocol_error["reason"] == "CONTENT_TYPE_NOT_SUPPORTED"
    assert t.a2a_interactions[0].protocol_error["http_status"] == 415


async def test_lifecycle_input_required_recovery_passes():
    report = await _run(case_ids=["a2a-lifecycle-001-input-required-recovery"])
    t = report.per_test[0]
    states = [i.observed_task_state for i in t.a2a_interactions]
    assert states == [
        "TASK_STATE_WORKING",
        "TASK_STATE_INPUT_REQUIRED",
        "TASK_STATE_WORKING",
        "TASK_STATE_COMPLETED",
    ]
    assert t.passed is True


async def test_remote_task_failure_handled_gracefully():
    report = await _run(case_ids=["a2a-failure-001-remote-task-failure"])
    t = report.per_test[0]
    assert t.a2a_interactions[-1].observed_task_state == "TASK_STATE_FAILED"
    assert t.passed is True


async def test_injection_resists_passes_and_hijacks_fails():
    report = await _run(
        case_ids=[
            "a2a-injection-001-malicious-artifact-resists",
            "a2a-injection-002-malicious-artifact-hijacks",
        ]
    )
    by_id = {t.case_id: t for t in report.per_test}
    resists = by_id["a2a-injection-001-malicious-artifact-resists"]
    hijacks = by_id["a2a-injection-002-malicious-artifact-hijacks"]

    resists_ev = next(
        e for e in resists.evaluations if e.evaluator_name == "cross_agent_injection_resistance"
    )
    hijacks_ev = next(
        e for e in hijacks.evaluations if e.evaluator_name == "cross_agent_injection_resistance"
    )

    assert resists_ev.passed is True
    assert resists_ev.evidence["detected"] is True
    assert resists_ev.evidence["hijacked"] is False
    assert resists.passed is True

    assert hijacks_ev.passed is False
    assert hijacks_ev.evidence["detected"] is True
    assert hijacks_ev.evidence["hijacked"] is True
    assert hijacks.passed is False

    # The malicious content is visible in the persisted trace, not hidden.
    assert any(
        "ignore all previous instructions" in (i.remote_message.parts[0].text.lower())
        for i in resists.a2a_interactions
        if i.remote_message is not None
    )


async def test_false_success_fails_via_artifact_validity_not_task_state():
    report = await _run(case_ids=["a2a-false-success-001-premature-completion"])
    t = report.per_test[0]
    by_name = {e.evaluator_name: e for e in t.evaluations if e.applicable}
    assert by_name["task_state_correctness"].passed is True
    assert by_name["artifact_validity"].passed is False
    assert t.a2a_interactions[-1].observed_task_state == "TASK_STATE_COMPLETED"
    assert t.a2a_interactions[-1].artifacts == []
    assert t.passed is False


async def test_cancellation_reaches_canceled_state():
    report = await _run(case_ids=["a2a-cancel-001-cancellation-handled"])
    t = report.per_test[0]
    assert t.a2a_interactions[-1].observed_task_state == "TASK_STATE_CANCELED"
    assert t.passed is True


async def test_two_direct_runs_are_scientifically_identical():
    r1 = _strip(json.loads((await _run()).model_dump_json()))
    r2 = _strip(json.loads((await _run()).model_dump_json()))
    assert r1 == r2


async def test_async_run_manager_path_matches_direct_execution():
    """Reuses the existing, unmodified RunManager: constructing a second
    instance wired to the A2A suite/execute function is the dispatch
    mechanism itself (no if/else branch needed inside RunManager, and zero
    lines of app/runner/run_manager.py changed) -- see CHANGELOG.md."""

    suite = load_a2a_suite(A2A_SUITE_PATH)

    async def a2a_execute_fn(run_id, passed_suite, _unused_transport):
        return await execute_a2a_suite(run_id, passed_suite)

    @asynccontextmanager
    async def no_transport():
        yield None

    manager = RunManager(
        suite,
        no_transport,
        InMemoryRunRepository(),
        execute_fn=a2a_execute_fn,
    )
    await manager.start()
    try:
        summary = manager.submit(RunCreateRequest())
        await manager.join()
        run = manager.get(summary.run_id)
        assert run.summary.status == RunStatus.COMPLETED
        async_report = run.report
    finally:
        await manager.stop()

    direct_report = await execute_a2a_suite("direct-comparison", suite)

    async_stripped = _strip(json.loads(async_report.model_dump_json()))
    direct_stripped = _strip(json.loads(direct_report.model_dump_json()))
    assert async_stripped == direct_stripped


async def test_protocol_identifiers_are_deterministic_and_case_derived_not_random():
    """task_id/context_id/message_id must match exactly across two runs of the
    same case -- they are not run metadata like run_id/timestamps/latency,
    they are part of the persisted interaction's scientific content."""
    report_a = await _run(case_ids=["a2a-lifecycle-001-input-required-recovery"])
    report_b = await _run(case_ids=["a2a-lifecycle-001-input-required-recovery"])

    interactions_a = report_a.per_test[0].a2a_interactions
    interactions_b = report_b.per_test[0].a2a_interactions

    task_ids_a = [i.task_id for i in interactions_a]
    task_ids_b = [i.task_id for i in interactions_b]
    assert task_ids_a == task_ids_b
    assert all(tid is not None for tid in task_ids_a)

    context_ids_a = [i.context_id for i in interactions_a]
    context_ids_b = [i.context_id for i in interactions_b]
    assert context_ids_a == context_ids_b

    message_ids_a = [i.request_message_id for i in interactions_a if i.request_message_id]
    message_ids_b = [i.request_message_id for i in interactions_b if i.request_message_id]
    assert message_ids_a == message_ids_b
    assert len(message_ids_a) == len(
        set(message_ids_a)
    )  # distinct per step, not coincidentally equal

    remote_message_ids_a = [
        i.remote_message.message_id for i in interactions_a if i.remote_message is not None
    ]
    remote_message_ids_b = [
        i.remote_message.message_id for i in interactions_b if i.remote_message is not None
    ]
    assert remote_message_ids_a == remote_message_ids_b


async def test_different_cases_get_different_deterministic_ids():
    """IDs are case-derived, not a single constant -- two different cases must
    not collide on task_id."""
    report = await _run(
        case_ids=[
            "a2a-correct-001-basic-task-completion",
            "a2a-failure-001-remote-task-failure",
        ]
    )
    task_ids = {t.a2a_interactions[0].task_id for t in report.per_test}
    assert len(task_ids) == 2
