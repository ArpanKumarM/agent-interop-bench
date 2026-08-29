"""RunManager's Phase 2C wiring: real-model request validation (before
queueing), adapter-factory dispatch, and provenance attachment — all with
fake transports/adapters, no real MCP subprocess and no real provider.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

from app.api.repository import InMemoryRunRepository
from app.models.benchmark import BenchmarkCase, BenchmarkSuite
from app.models.evaluation import CaseReport, Report, ScoreSummary
from app.models.execution import TerminationReason
from app.models.provenance import ModelRunProvenance
from app.models.run import RunAdapter, RunCreateRequest, RunStatus
from app.runner.run_manager import InvalidRunRequestError, RunManager, RunQueueFullError

SUITE = BenchmarkSuite(
    name="unit-test-suite",
    cases=[
        BenchmarkCase(
            id="case-1",
            category="correct_tool_selection",
            user_prompt="p1",
            expected_tool="t1",
            expected_outcome="success",
        ),
        BenchmarkCase(
            id="case-2",
            category="correct_tool_selection",
            user_prompt="p2",
            expected_tool="t2",
            expected_outcome="success",
        ),
        BenchmarkCase(
            id="case-3",
            category="correct_tool_selection",
            user_prompt="p3",
            expected_tool="t3",
            expected_outcome="success",
        ),
        BenchmarkCase(
            id="case-4",
            category="correct_tool_selection",
            user_prompt="p4",
            expected_tool="t4",
            expected_outcome="success",
        ),
    ],
)


def _report(run_id: str, case_ids: list[str]) -> Report:
    return Report(
        run_id=run_id,
        suite_name="unit-test-suite",
        suite_version="0.0.0",
        summary=ScoreSummary(
            total_tests=len(case_ids),
            passed_tests=len(case_ids),
            failed_tests=0,
            tool_selection_accuracy=1.0,
            argument_accuracy=None,
            recovery_rate=None,
            unsafe_action_rate=None,
            prompt_injection_resistance=None,
            trajectory_integrity=None,
            average_latency_ms=0.0,
        ),
        per_test=[
            CaseReport(
                case_id=cid,
                category="correct_tool_selection",
                expected_outcome="success",
                passed=True,
                latency_ms=0.0,
                turns=[],
                termination_reason=TerminationReason.MAX_TURNS_REACHED,
                evaluations=[],
            )
            for cid in case_ids
        ],
    )


class _FakeTransport:
    """Enough of MCPTransport for execute_suite's real-model path: tools
    discovery only. RecordingAdapter always votes to stop, so call_tool()
    is never invoked and doesn't need to be implemented here."""

    async def list_tools(self):
        return []


@asynccontextmanager
async def _fake_transport():
    yield _FakeTransport()


class RecordingAdapter:
    """A fake real-model adapter: not a real AgentAdapter subclass (doesn't
    need to be — RunManager/execute_suite duck-type via .decide/.provenance),
    just enough to prove wiring without ever touching a provider."""

    def __init__(self, model: str):
        self.model = model
        self.provenance = ModelRunProvenance(
            adapter_type="fake",
            provider="fake",
            requested_model=model,
            baseline_policy_version="real-model-baseline-v1",
            baseline_policy_sha256="0" * 64,
            tool_schema_sha256="",
            configured_timeout_seconds=1.0,
            configured_max_retries=0,
            configured_max_output_tokens=1,
        )
        self.bound_case_ids: list[str] = []

    def bind_case(self, case_id: str) -> None:
        self.bound_case_ids.append(case_id)

    async def decide(self, prompt, available_tools, history):
        from app.models.execution import ToolCallDecision

        return ToolCallDecision(tool_name=None)


def make_manager(
    *,
    execute_fn=None,
    real_model_adapter_factory=None,
    real_model_max_cases=3,
    queue_maxsize=10,
    worker_count=1,
) -> RunManager:
    async def default_execute_fn(run_id, suite, transport):
        return _report(run_id, [c.id for c in suite.cases])

    return RunManager(
        suite=SUITE,
        transport_factory=_fake_transport,
        repository=InMemoryRunRepository(),
        queue_maxsize=queue_maxsize,
        worker_count=worker_count,
        execute_fn=execute_fn or default_execute_fn,
        real_model_adapter_factory=real_model_adapter_factory,
        real_model_max_cases=real_model_max_cases,
    )


async def _join(manager: RunManager, timeout: float = 5.0) -> None:
    import asyncio

    await asyncio.wait_for(manager.join(), timeout=timeout)


# ---- deterministic default is unaffected (Part M) ----


async def test_deterministic_request_never_invokes_real_model_adapter_factory():
    def exploding_factory(request):
        raise AssertionError(
            "real_model_adapter_factory must not be called for a deterministic run"
        )

    manager = make_manager(real_model_adapter_factory=exploding_factory)
    await manager.start()
    try:
        summary = manager.submit()  # no request -> deterministic default
        await _join(manager)
        run = manager.get(summary.run_id)
        assert run.summary.status == RunStatus.COMPLETED
        assert run.report.model_provenance is None
    finally:
        await manager.stop()


async def test_deterministic_request_explicit_still_never_invokes_factory():
    def exploding_factory(request):
        raise AssertionError("must not be called")

    manager = make_manager(real_model_adapter_factory=exploding_factory)
    await manager.start()
    try:
        summary = manager.submit(RunCreateRequest(adapter=RunAdapter.DETERMINISTIC))
        await _join(manager)
        assert manager.get(summary.run_id).summary.status == RunStatus.COMPLETED
    finally:
        await manager.stop()


# ---- request validation before queueing (Part L) ----


async def test_openai_request_without_model_rejected_before_queueing():
    manager = make_manager(real_model_adapter_factory=lambda r: RecordingAdapter(r.model))
    await manager.start()
    try:
        with pytest.raises(InvalidRunRequestError, match="model"):
            manager.submit(RunCreateRequest(adapter=RunAdapter.OPENAI, case_ids=["case-1"]))
        assert manager._repository.list_all() == []  # noqa: SLF001 - nothing was ever persisted
    finally:
        await manager.stop()


async def test_unknown_case_ids_rejected_before_queueing():
    manager = make_manager(real_model_adapter_factory=lambda r: RecordingAdapter(r.model))
    await manager.start()
    try:
        with pytest.raises(InvalidRunRequestError, match="Unknown case_ids"):
            manager.submit(
                RunCreateRequest(
                    adapter=RunAdapter.OPENAI, model="m", case_ids=["case-1", "no-such-case"]
                )
            )
        assert manager._repository.list_all() == []  # noqa: SLF001
    finally:
        await manager.stop()


async def test_duplicate_case_ids_rejected_before_queueing():
    manager = make_manager(real_model_adapter_factory=lambda r: RecordingAdapter(r.model))
    await manager.start()
    try:
        with pytest.raises(InvalidRunRequestError, match="duplicate"):
            manager.submit(
                RunCreateRequest(
                    adapter=RunAdapter.OPENAI, model="m", case_ids=["case-1", "case-1"]
                )
            )
    finally:
        await manager.stop()


async def test_case_count_over_configured_limit_rejected_before_queueing():
    manager = make_manager(
        real_model_adapter_factory=lambda r: RecordingAdapter(r.model), real_model_max_cases=2
    )
    await manager.start()
    try:
        with pytest.raises(InvalidRunRequestError, match="exceeding"):
            manager.submit(
                RunCreateRequest(
                    adapter=RunAdapter.OPENAI, model="m", case_ids=["case-1", "case-2", "case-3"]
                )
            )
    finally:
        await manager.stop()


async def test_omitted_case_ids_checked_against_full_suite_count():
    """A live request with no case_ids means "run every case" -- and the
    suite here has 4, over a cap of 2."""
    manager = make_manager(
        real_model_adapter_factory=lambda r: RecordingAdapter(r.model), real_model_max_cases=2
    )
    await manager.start()
    try:
        with pytest.raises(InvalidRunRequestError, match="exceeding"):
            manager.submit(RunCreateRequest(adapter=RunAdapter.OPENAI, model="m"))
    finally:
        await manager.stop()


async def test_valid_case_ids_within_limit_are_accepted():
    manager = make_manager(
        real_model_adapter_factory=lambda r: RecordingAdapter(r.model), real_model_max_cases=2
    )
    await manager.start()
    try:
        summary = manager.submit(
            RunCreateRequest(adapter=RunAdapter.OPENAI, model="m", case_ids=["case-1", "case-2"])
        )
        assert summary.status == RunStatus.QUEUED
    finally:
        await manager.stop()


# ---- adapter dispatch and provenance attachment ----


async def test_openai_request_dispatches_to_the_configured_factory_with_case_subset():
    built_adapters = []

    def factory(request):
        adapter = RecordingAdapter(request.model)
        built_adapters.append(adapter)
        return adapter

    async def execute_fn_should_not_be_called(run_id, suite, transport):
        raise AssertionError(
            "the deterministic execute_fn seam must not be used for a live request"
        )

    manager = make_manager(
        execute_fn=execute_fn_should_not_be_called, real_model_adapter_factory=factory
    )
    await manager.start()
    try:
        summary = manager.submit(
            RunCreateRequest(
                adapter=RunAdapter.OPENAI, model="gpt-test", case_ids=["case-1", "case-3"]
            )
        )
        await _join(manager)

        run = manager.get(summary.run_id)
        assert run.summary.status == RunStatus.COMPLETED
        assert len(built_adapters) == 1
        assert built_adapters[0].model == "gpt-test"
        assert sorted(built_adapters[0].bound_case_ids) == ["case-1", "case-3"]
        assert {c.case_id for c in run.report.per_test} == {"case-1", "case-3"}
    finally:
        await manager.stop()


async def test_openai_run_report_carries_model_provenance():
    manager = make_manager(real_model_adapter_factory=lambda r: RecordingAdapter(r.model))
    await manager.start()
    try:
        summary = manager.submit(
            RunCreateRequest(adapter=RunAdapter.OPENAI, model="gpt-test", case_ids=["case-1"])
        )
        await _join(manager)
        run = manager.get(summary.run_id)
        assert run.report.model_provenance is not None
        assert run.report.model_provenance.requested_model == "gpt-test"
    finally:
        await manager.stop()


async def test_missing_adapter_factory_fails_the_run_not_the_worker():
    """If adapter='openai' somehow reaches a RunManager with no factory
    configured (e.g. the feature was enabled after validation but the
    factory wasn't wired -- defensive case), the run fails cleanly and the
    worker keeps servicing subsequent runs, exactly like any other
    execute_suite exception."""
    manager = make_manager(real_model_adapter_factory=None)
    await manager.start()
    try:
        first = manager.submit(
            RunCreateRequest(adapter=RunAdapter.OPENAI, model="gpt-test", case_ids=["case-1"])
        )
        await _join(manager)
        assert manager.get(first.run_id).summary.status == RunStatus.FAILED
        assert manager.get(first.run_id).report is None

        second = manager.submit()  # deterministic, unaffected
        await _join(manager)
        assert manager.get(second.run_id).summary.status == RunStatus.COMPLETED
    finally:
        await manager.stop()


async def test_queue_full_still_enforced_for_real_model_requests():
    manager = make_manager(
        real_model_adapter_factory=lambda r: RecordingAdapter(r.model),
        queue_maxsize=1,
        worker_count=1,
    )
    await manager.start()
    try:
        manager.submit(RunCreateRequest(adapter=RunAdapter.OPENAI, model="m", case_ids=["case-1"]))
        with pytest.raises(RunQueueFullError):
            manager.submit(
                RunCreateRequest(adapter=RunAdapter.OPENAI, model="m", case_ids=["case-2"])
            )
    finally:
        await manager.stop()
