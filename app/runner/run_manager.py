"""Bounded-concurrency background execution for benchmark runs.

Owns the full run lifecycle outside the API layer: allocating run IDs,
tracking lifecycle state transitions, a bounded queue of pending work, a
small fixed pool of asyncio worker tasks that pull from it, and lookup by
run ID. ``execute_suite`` (``app.runner.suite_execution``) remains the
single canonical, unchanged execution primitive — this module only decides
*when* and *how many at once* it runs, never re-implements what it does.

Bounding, by design:

- The pending-work queue has a fixed ``maxsize``; ``submit()`` raises
  ``RunQueueFullError`` instead of growing it unboundedly.
- Exactly ``worker_count`` asyncio tasks ever run ``execute_suite``
  concurrently — no per-request task spawning.
- Each run is enqueued exactly once by ``submit()``, and ``_execute`` also
  defensively refuses to run a record that isn't ``QUEUED``, so a run can
  never execute twice even if something upstream misbehaves.
- A worker's loop never exits because one run failed: ``_execute`` converts
  any exception from ``execute_suite`` into a stored ``FAILED`` record, and
  the loop itself wraps ``_execute`` in a last-resort try/except so a bug in
  bookkeeping code can't kill the worker either.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

from app.api.repository import RunRepository
from app.models.benchmark import BenchmarkSuite
from app.models.evaluation import Report
from app.models.run import Run, RunStatus, RunSummary
from app.runner.suite_execution import execute_suite
from app.runner.transport import MCPTransport

logger = logging.getLogger("agent_interop_bench.run_manager")

TransportFactory = Callable[[], AbstractAsyncContextManager[MCPTransport]]
ExecuteFn = Callable[[str, BenchmarkSuite, MCPTransport], Awaitable[Report]]


class RunQueueFullError(Exception):
    """Raised by ``RunManager.submit()`` when the bounded queue has no room.

    The API layer translates this into HTTP 429.
    """


def _now() -> datetime:
    return datetime.now(UTC)


def _safe_error_message(exc: Exception) -> str:
    """A controlled, traceback-free error string safe to return over the API."""
    return f"{type(exc).__name__}: {exc}"


class RunManager:
    """Bounded-concurrency background executor for benchmark suite runs."""

    def __init__(
        self,
        suite: BenchmarkSuite,
        transport_factory: TransportFactory,
        repository: RunRepository,
        *,
        queue_maxsize: int = 10,
        worker_count: int = 2,
        execute_fn: ExecuteFn = execute_suite,
    ) -> None:
        # Defense in depth, independent of Settings' own validation: this
        # class is the component that actually relies on these bounds, so it
        # must not trust a caller to have validated them. In particular,
        # asyncio.Queue(maxsize=0) means UNBOUNDED, not zero, which would
        # silently defeat the bounded-execution guarantee if let through.
        if worker_count < 1:
            raise ValueError(f"worker_count must be >= 1, got {worker_count}")
        if queue_maxsize < 1:
            raise ValueError(
                f"queue_maxsize must be >= 1 (0 means unbounded in asyncio.Queue), "
                f"got {queue_maxsize}"
            )

        self._suite = suite
        self._transport_factory = transport_factory
        self._repository = repository
        self._execute_fn = execute_fn
        self._queue_maxsize = queue_maxsize
        self._worker_count = worker_count
        # The queue is intentionally NOT created here: asyncio synchronization
        # primitives bind to whatever event loop first touches them, and this
        # manager is constructed once at process/module import time — before
        # any loop is running. Creating it in start() instead binds it fresh
        # to the loop FastAPI's lifespan is actually running on (and, in
        # tests, to that test's own loop each time a TestClient's lifespan
        # cycles), instead of silently breaking the second time a different
        # loop tries to use a queue bound to a now-closed one.
        self._queue: asyncio.Queue[str] | None = None
        self._workers: list[asyncio.Task[None]] = []

    async def start(self) -> None:
        """Start the fixed worker pool, with a fresh queue bound to this loop.

        Safe to call repeatedly: a no-op if already started.
        """
        if self._workers:
            return
        self._queue = asyncio.Queue(maxsize=self._queue_maxsize)
        self._workers = [
            asyncio.create_task(self._worker_loop(i), name=f"run-worker-{i}")
            for i in range(self._worker_count)
        ]

    async def stop(self) -> None:
        """Cancel all workers immediately and wait for them to exit.

        Shutdown policy (deliberate, not an oversight): this does **not**
        wait for in-flight or queued runs to finish. Any run a worker is
        mid-execution on when `stop()` is called is cancelled abruptly and
        left exactly where it was — typically stuck in ``RUNNING`` forever,
        never fabricated to ``COMPLETED``/``FAILED`` and never silently
        discarded. Any run still sitting in the queue is simply never
        dispatched. This is consistent with Phase 2B's in-memory-only
        storage: none of that state survives a process restart anyway, so
        there is no durability contract to honor by delaying shutdown.
        `asyncio.gather(..., return_exceptions=True)` ensures a cancelled
        worker's `CancelledError` cannot make `stop()` itself hang or raise.
        """
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []
        self._queue = None

    async def join(self) -> None:
        """Wait until every currently-queued run has finished processing.

        Not used by the API (clients poll instead); exists so tests can
        deterministically wait for background work without sleeping.
        """
        if self._queue is not None:
            await self._queue.join()

    def submit(self) -> RunSummary:
        """Allocate a run ID, record it as queued, and enqueue exactly one execution.

        Raises ``RunQueueFullError`` instead of growing the queue past its
        bound. Never blocks.
        """
        if self._queue is None:
            raise RuntimeError("RunManager.submit() called before start()")

        run_id = str(uuid.uuid4())
        summary = RunSummary(run_id=run_id, status=RunStatus.QUEUED, created_at=_now())
        try:
            self._queue.put_nowait(run_id)
        except asyncio.QueueFull as exc:
            raise RunQueueFullError(
                f"Run queue is full ({self._queue.maxsize} pending); try again shortly."
            ) from exc
        self._repository.save(Run(summary=summary))
        return summary

    def get(self, run_id: str) -> Run | None:
        return self._repository.get(run_id)

    async def _worker_loop(self, worker_index: int) -> None:
        while True:
            try:
                run_id = await self._queue.get()
            except asyncio.CancelledError:
                return
            try:
                await self._execute(run_id)
            except Exception:  # noqa: BLE001 - a worker must never die from a run's failure
                logger.exception(
                    "agent_interop_bench_worker_unexpected_error",
                    extra={"worker_index": worker_index, "run_id": run_id},
                )
            finally:
                self._queue.task_done()

    async def _execute(self, run_id: str) -> None:
        run = self._repository.get(run_id)
        if run is None or run.summary.status != RunStatus.QUEUED:
            # Defensive: never (re-)execute a run that isn't in the state a
            # worker expects to find it in. Under normal operation this never
            # triggers — submit() enqueues each run_id exactly once — but it
            # guarantees a terminal (or already-running) run can't regress or
            # be double-executed even under a future bug or a duplicate
            # queue entry.
            logger.warning(
                "agent_interop_bench_skip_non_queued_run",
                extra={"run_id": run_id, "status": run.summary.status if run else None},
            )
            return

        running_summary = run.summary.model_copy(
            update={"status": RunStatus.RUNNING, "started_at": _now()}
        )
        self._repository.save(Run(summary=running_summary))
        logger.info("agent_interop_bench_run_started", extra={"run_id": run_id})

        try:
            async with self._transport_factory() as transport:
                report = await self._execute_fn(run_id, self._suite, transport)
        except Exception as exc:  # noqa: BLE001 - convert any run failure into a stored FAILED run
            logger.exception("agent_interop_bench_run_failed", extra={"run_id": run_id})
            failed_summary = running_summary.model_copy(
                update={
                    "status": RunStatus.FAILED,
                    "failed_at": _now(),
                    "error": _safe_error_message(exc),
                }
            )
            self._repository.save(Run(summary=failed_summary))
            return

        completed_summary = running_summary.model_copy(
            update={"status": RunStatus.COMPLETED, "completed_at": _now()}
        )
        self._repository.save(Run(summary=completed_summary, report=report))
        logger.info(
            "agent_interop_bench_run_completed",
            extra={
                "run_id": run_id,
                "passed": report.summary.passed_tests,
                "total": report.summary.total_tests,
            },
        )
