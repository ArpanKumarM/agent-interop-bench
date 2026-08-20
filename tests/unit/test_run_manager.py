"""Unit tests for RunManager: lifecycle transitions, bounded queue/concurrency,
failure isolation, and terminal-state monotonicity — independent of the API
and of any real MCP transport/subprocess (execute_fn and transport_factory
are injected fakes throughout).
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import pytest

from app.api.repository import InMemoryRunRepository
from app.models.benchmark import BenchmarkSuite
from app.models.evaluation import Report, ScoreSummary
from app.models.run import RunStatus
from app.runner.run_manager import RunManager, RunQueueFullError

EMPTY_SUITE = BenchmarkSuite(name="unit-test-suite", cases=[])


def _report(run_id: str) -> Report:
    return Report(
        run_id=run_id,
        suite_name="unit-test-suite",
        suite_version=EMPTY_SUITE.version,
        summary=ScoreSummary(
            total_tests=0,
            passed_tests=0,
            failed_tests=0,
            tool_selection_accuracy=None,
            argument_accuracy=None,
            recovery_rate=None,
            unsafe_action_rate=None,
            prompt_injection_resistance=None,
            average_latency_ms=0.0,
        ),
        per_test=[],
    )


@asynccontextmanager
async def _fake_transport():
    """Never touched by the fake execute_fn below; just satisfies the interface."""
    yield object()


def make_manager(*, execute_fn, queue_maxsize=10, worker_count=2) -> RunManager:
    return RunManager(
        suite=EMPTY_SUITE,
        transport_factory=_fake_transport,
        repository=InMemoryRunRepository(),
        queue_maxsize=queue_maxsize,
        worker_count=worker_count,
        execute_fn=execute_fn,
    )


async def _join(manager: RunManager, timeout: float = 5.0) -> None:
    """manager.join() with a timeout: if queue.task_done() accounting were
    ever broken (e.g. a missed call), join() would hang forever rather than
    fail with a clear error — this turns that into a fast, diagnosable
    test failure instead of a stuck CI run."""
    await asyncio.wait_for(manager.join(), timeout=timeout)


async def test_submit_creates_a_queued_run_before_any_worker_runs():
    async def never_called(run_id, suite, transport):
        raise AssertionError("execute_fn should not have run yet")

    manager = make_manager(execute_fn=never_called, worker_count=1)
    # start()'s body has no internal `await`, so awaiting it does not yield
    # control to the scheduler — the worker task it creates cannot possibly
    # have run yet by the time submit() (also non-yielding) executes next.
    # This is a structural guarantee, not a timing race.
    await manager.start()
    try:
        summary = manager.submit()

        assert summary.status == RunStatus.QUEUED
        assert summary.created_at is not None
        assert summary.started_at is None
        assert summary.completed_at is None
        assert summary.failed_at is None

        stored = manager.get(summary.run_id)
        assert stored is not None
        assert stored.summary.status == RunStatus.QUEUED
        assert stored.report is None
    finally:
        await manager.stop()


async def test_submit_before_start_without_queue_raises():
    async def never_called(run_id, suite, transport):
        raise AssertionError("should not run")

    manager = make_manager(execute_fn=never_called)
    with pytest.raises(RuntimeError):
        manager.submit()


async def test_worker_processes_queued_run_to_completed():
    async def fake_execute(run_id, suite, transport):
        return _report(run_id)

    manager = make_manager(execute_fn=fake_execute)
    await manager.start()
    try:
        summary = manager.submit()
        await _join(manager)

        run = manager.get(summary.run_id)
        assert run is not None
        assert run.summary.status == RunStatus.COMPLETED
        assert run.summary.started_at is not None
        assert run.summary.completed_at is not None
        assert run.summary.failed_at is None
        assert run.summary.error is None
        assert run.report is not None
        assert run.report.run_id == summary.run_id
    finally:
        await manager.stop()


async def test_timestamp_invariants_hold_for_queued_running_completed_failed():
    gate = asyncio.Event()
    started = asyncio.Event()

    async def gated_execute(run_id, suite, transport):
        # _execute() persists the RUNNING transition before calling this
        # function, so by the time `started` is set, that write has already
        # landed — no polling needed to observe it deterministically.
        started.set()
        await gate.wait()
        return _report(run_id)

    manager = make_manager(execute_fn=gated_execute)
    await manager.start()
    try:
        summary = manager.submit()

        # queued invariants (checked before the worker has picked it up —
        # deterministic because no `await` has happened yet since submit(),
        # so the single-threaded event loop cannot have scheduled the worker).
        run = manager.get(summary.run_id)
        assert run.summary.status == RunStatus.QUEUED
        assert run.summary.created_at is not None
        assert run.summary.started_at is None
        assert run.summary.completed_at is None
        assert run.summary.failed_at is None

        await asyncio.wait_for(started.wait(), timeout=5.0)
        run = manager.get(summary.run_id)
        assert run.summary.status == RunStatus.RUNNING
        assert run.summary.created_at is not None
        assert run.summary.started_at is not None
        assert run.summary.completed_at is None
        assert run.summary.failed_at is None

        gate.set()
        await _join(manager)

        run = manager.get(summary.run_id)
        assert run.summary.status == RunStatus.COMPLETED
        assert run.summary.created_at is not None
        assert run.summary.started_at is not None
        assert run.summary.completed_at is not None
        assert run.summary.failed_at is None
        assert run.summary.error is None
        assert run.report is not None
    finally:
        await manager.stop()


async def test_failed_run_has_no_report_and_worker_continues_to_next_run():
    calls: list[str] = []

    async def flaky_execute(run_id, suite, transport):
        calls.append(run_id)
        if len(calls) == 1:
            raise RuntimeError("simulated failure")
        return _report(run_id)

    manager = make_manager(execute_fn=flaky_execute)
    await manager.start()
    try:
        first = manager.submit()
        await _join(manager)

        failed_run = manager.get(first.run_id)
        assert failed_run.summary.status == RunStatus.FAILED
        assert failed_run.summary.error is not None
        assert "simulated failure" in failed_run.summary.error
        assert failed_run.summary.completed_at is None
        assert failed_run.summary.failed_at is not None
        assert failed_run.report is None

        second = manager.submit()
        await _join(manager)

        completed_run = manager.get(second.run_id)
        assert completed_run.summary.status == RunStatus.COMPLETED
        assert completed_run.report is not None
    finally:
        await manager.stop()


async def test_worker_survives_unexpected_bookkeeping_exception():
    """A bug outside execute_fn's own try/except (e.g. a broken repository
    write) must not kill the worker loop — it's caught by _worker_loop's
    outer guard, and the loop must still process the next queued run."""

    class FlakyRepository(InMemoryRunRepository):
        """Fails exactly once: the first queued -> running transition write,
        whichever run_id that happens to be. With worker_count=1 and FIFO
        dispatch, that's deterministically the first-submitted run."""

        def __init__(self) -> None:
            super().__init__()
            self._raised_once = False
            self.save_calls = 0

        def save(self, run):
            self.save_calls += 1
            if not self._raised_once and run.summary.status == RunStatus.RUNNING:
                self._raised_once = True
                raise RuntimeError("simulated repository bug")
            super().save(run)

    async def fake_execute(run_id, suite, transport):
        return _report(run_id)

    repository = FlakyRepository()
    manager = RunManager(
        suite=EMPTY_SUITE,
        transport_factory=_fake_transport,
        repository=repository,
        queue_maxsize=10,
        worker_count=1,
        execute_fn=fake_execute,
    )
    await manager.start()
    try:
        first = manager.submit()
        second = manager.submit()
        await _join(manager)

        # The first run's bookkeeping blew up mid-transition (worker_loop's
        # outer except caught it) — its queue slot is still marked done, and
        # the worker is provably still alive because it went on to process
        # the second run to completion.
        assert repository.save_calls >= 2
        assert manager.get(second.run_id).summary.status == RunStatus.COMPLETED
        assert manager.get(second.run_id).report is not None
        # The first run never reached a terminal state (its transition write
        # raised before either COMPLETED or FAILED could be persisted) — it
        # is stuck, not silently marked successful, which is the honest
        # outcome for a bookkeeping failure the worker couldn't recover from.
        assert manager.get(first.run_id).summary.status == RunStatus.QUEUED
    finally:
        await manager.stop()


async def test_queue_full_raises_run_queue_full_error():
    async def never_called(run_id, suite, transport):
        raise AssertionError("the worker never gets to run in this test")

    # worker_count=1, but no `await` happens between start() and the two
    # submit() calls below, so the worker task — created inside start()'s
    # non-yielding body — structurally cannot have run yet. This is a
    # scheduling guarantee, not a timing race: asyncio.Queue(maxsize=1) is
    # full by the second submit() with certainty, every run.
    manager = make_manager(execute_fn=never_called, queue_maxsize=1, worker_count=1)
    await manager.start()
    try:
        manager.submit()  # fills the one queue slot
        with pytest.raises(RunQueueFullError):
            manager.submit()
    finally:
        await manager.stop()


async def test_queue_full_leaves_no_orphan_run_record():
    """RunManager.submit() must be atomic w.r.t. the repository: if
    put_nowait() raises QueueFull, no record for the rejected submission may
    have been written, the accepted run(s) must be untouched, and there must
    be no way to retrieve or execute the rejected submission."""

    async def never_called(run_id, suite, transport):
        raise AssertionError("the worker never gets to run in this test")

    repository = InMemoryRunRepository()
    manager = RunManager(
        suite=EMPTY_SUITE,
        transport_factory=_fake_transport,
        repository=repository,
        queue_maxsize=1,
        worker_count=1,
        execute_fn=never_called,
    )
    await manager.start()
    try:
        accepted = manager.submit()
        assert len(repository.list_all()) == 1

        with pytest.raises(RunQueueFullError):
            manager.submit()

        # No orphan record: the repository holds exactly the one accepted
        # run, nothing more — the rejected submission left no trace at all
        # (it never even receives a run_id the caller could look up).
        all_runs = repository.list_all()
        assert len(all_runs) == 1
        assert all_runs[0].summary.run_id == accepted.run_id

        # The accepted run is untouched: still queued, unchanged.
        stored = manager.get(accepted.run_id)
        assert stored is not None
        assert stored.summary.status == RunStatus.QUEUED
        assert stored.summary == accepted
    finally:
        await manager.stop()


async def test_bounded_worker_concurrency_is_enforced():
    worker_count = 2
    concurrent = 0
    max_concurrent = 0
    reached_cap = asyncio.Event()
    release = asyncio.Event()
    lock = asyncio.Lock()

    async def slow_execute(run_id, suite, transport):
        nonlocal concurrent, max_concurrent
        async with lock:
            concurrent += 1
            max_concurrent = max(max_concurrent, concurrent)
            if concurrent == worker_count:
                reached_cap.set()
        await release.wait()
        async with lock:
            concurrent -= 1
        return _report(run_id)

    manager = make_manager(execute_fn=slow_execute, worker_count=worker_count, queue_maxsize=10)
    await manager.start()
    try:
        run_ids = [manager.submit().run_id for _ in range(4)]

        await asyncio.wait_for(reached_cap.wait(), timeout=5.0)
        assert max_concurrent == worker_count  # never exceeded the bound

        # The remaining runs must still be queued, not somehow also running.
        statuses = [manager.get(rid).summary.status for rid in run_ids]
        assert statuses.count(RunStatus.RUNNING) == worker_count
        assert statuses.count(RunStatus.QUEUED) == len(run_ids) - worker_count

        release.set()
        await _join(manager)

        final_statuses = [manager.get(rid).summary.status for rid in run_ids]
        assert final_statuses == [RunStatus.COMPLETED] * len(run_ids)
        assert max_concurrent == worker_count
    finally:
        await manager.stop()


async def test_execute_does_not_regress_a_terminal_run(monkeypatch):
    """White-box check that _execute refuses to touch a non-QUEUED record —
    the guard that makes terminal states monotonic even under a hypothetical
    duplicate-dispatch bug."""
    call_count = 0

    async def fake_execute(run_id, suite, transport):
        nonlocal call_count
        call_count += 1
        return _report(run_id)

    manager = make_manager(execute_fn=fake_execute)
    await manager.start()
    try:
        summary = manager.submit()
        await _join(manager)
        assert call_count == 1
        completed_run = manager.get(summary.run_id)
        assert completed_run.summary.status == RunStatus.COMPLETED
        completed_at = completed_run.summary.completed_at

        # Directly invoke the internal transition method again for the same,
        # now-completed run_id, simulating a duplicate dispatch.
        await manager._execute(summary.run_id)  # noqa: SLF001 - deliberate white-box test

        assert call_count == 1  # execute_fn was NOT called a second time
        unchanged_run = manager.get(summary.run_id)
        assert unchanged_run.summary.status == RunStatus.COMPLETED
        assert unchanged_run.summary.completed_at == completed_at
    finally:
        await manager.stop()


async def test_stop_cancels_workers_and_start_is_idempotent():
    async def fake_execute(run_id, suite, transport):
        return _report(run_id)

    manager = make_manager(execute_fn=fake_execute)
    await manager.start()
    await manager.start()  # idempotent: must not spawn a second worker set
    assert len(manager._workers) == 2  # noqa: SLF001 - white-box assertion

    await manager.stop()
    assert manager._workers == []  # noqa: SLF001


async def test_stop_does_not_hang_on_an_in_flight_run_and_leaves_it_stuck_running():
    """Documented shutdown policy: stop() does not wait for in-flight runs to
    finish. A run a worker is mid-execution on is cancelled abruptly and left
    exactly where it was (RUNNING) — never fabricated to a terminal state,
    never silently discarded, and shutdown itself must not hang."""
    gate = asyncio.Event()  # deliberately never set
    started = asyncio.Event()

    async def gated_execute(run_id, suite, transport):
        started.set()
        await gate.wait()
        return _report(run_id)  # unreachable in this test

    manager = make_manager(execute_fn=gated_execute, worker_count=1)
    await manager.start()
    summary = manager.submit()
    await asyncio.wait_for(started.wait(), timeout=5.0)

    run = manager.get(summary.run_id)
    assert run.summary.status == RunStatus.RUNNING

    # Shutdown while the run is still in flight must complete promptly, not hang.
    await asyncio.wait_for(manager.stop(), timeout=5.0)

    stuck = manager.get(summary.run_id)
    assert stuck.summary.status == RunStatus.RUNNING  # left as-is, not COMPLETED/FAILED
    assert stuck.report is None
    assert manager._workers == []  # noqa: SLF001


async def test_queue_task_done_accounting_survives_success_failure_and_bookkeeping_bug():
    """Directly inspects asyncio.Queue's own unfinished-task counter (rather
    than inferring it indirectly through join()) across all three paths a
    dequeued item can take: successful execution, execute_fn raising, and a
    repository write raising. Every path must leave exactly zero unfinished
    tasks — one queue.get() must always pair with exactly one task_done()."""

    class FlakyRepository(InMemoryRunRepository):
        def __init__(self) -> None:
            super().__init__()
            self._raised_once = False

        def save(self, run):
            if not self._raised_once and run.summary.status == RunStatus.RUNNING:
                self._raised_once = True
                raise RuntimeError("simulated repository bug")
            super().save(run)

    calls = 0

    async def sometimes_failing_execute(run_id, suite, transport):
        nonlocal calls
        calls += 1
        # Every other successful call fails at the execute_fn level.
        if calls % 2 == 0:
            raise RuntimeError("simulated benchmark failure")
        return _report(run_id)

    repository = FlakyRepository()
    manager = RunManager(
        suite=EMPTY_SUITE,
        transport_factory=_fake_transport,
        repository=repository,
        queue_maxsize=10,
        worker_count=1,
        execute_fn=sometimes_failing_execute,
    )
    await manager.start()
    try:
        # Run 1: bookkeeping raises before execute_fn is even reached.
        # Run 2: execute_fn succeeds (calls == 1, odd).
        # Run 3: execute_fn raises (calls == 2, even).
        ids = [manager.submit().run_id for _ in range(3)]
        await _join(manager)  # would hang forever if any task_done() were missed

        assert manager._queue._unfinished_tasks == 0  # noqa: SLF001

        assert manager.get(ids[0]).summary.status == RunStatus.QUEUED  # bookkeeping bug: stuck
        assert manager.get(ids[1]).summary.status == RunStatus.COMPLETED
        assert manager.get(ids[2]).summary.status == RunStatus.FAILED
    finally:
        await manager.stop()


async def test_repeated_lifespan_cycles_do_not_retain_workers_or_queue_state():
    """Simulates two consecutive FastAPI lifespan cycles (as happens across
    two separate TestClient `with` blocks) on the SAME manager instance:
    start/submit/finish/stop, then start/submit/finish/stop again. The
    second cycle must get a fresh queue and worker set, not leak state from
    the first (e.g. stale worker tasks, or a queue bound to a now-closed
    loop from a previous cycle)."""

    async def fake_execute(run_id, suite, transport):
        return _report(run_id)

    manager = make_manager(execute_fn=fake_execute, worker_count=2)

    await manager.start()
    first = manager.submit()
    await _join(manager)
    assert manager.get(first.run_id).summary.status == RunStatus.COMPLETED
    await manager.stop()
    assert manager._workers == []  # noqa: SLF001
    assert manager._queue is None  # noqa: SLF001

    # Second cycle, same manager instance.
    await manager.start()
    try:
        assert len(manager._workers) == 2  # noqa: SLF001 - fresh worker set
        second = manager.submit()
        await _join(manager)
        assert manager.get(second.run_id).summary.status == RunStatus.COMPLETED
        # Both runs' records persisted across cycles (repository isn't reset,
        # only the queue/workers are) — first run is still there, untouched.
        assert manager.get(first.run_id).summary.status == RunStatus.COMPLETED
    finally:
        await manager.stop()


@pytest.mark.parametrize("worker_count", [0, -1])
def test_worker_count_below_one_rejected(worker_count):
    async def never_called(run_id, suite, transport):
        raise AssertionError("should never run")

    with pytest.raises(ValueError, match="worker_count"):
        RunManager(
            suite=EMPTY_SUITE,
            transport_factory=_fake_transport,
            repository=InMemoryRunRepository(),
            worker_count=worker_count,
            execute_fn=never_called,
        )


@pytest.mark.parametrize("queue_maxsize", [0, -1])
def test_queue_maxsize_below_one_rejected(queue_maxsize):
    async def never_called(run_id, suite, transport):
        raise AssertionError("should never run")

    with pytest.raises(ValueError, match="queue_maxsize"):
        RunManager(
            suite=EMPTY_SUITE,
            transport_factory=_fake_transport,
            repository=InMemoryRunRepository(),
            queue_maxsize=queue_maxsize,
            execute_fn=never_called,
        )
