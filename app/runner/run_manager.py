"""Bounded-concurrency background execution for benchmark runs.

Owns the full run lifecycle outside the API layer: allocating run IDs,
validating a submission's request-level preconditions, tracking lifecycle
state transitions, a bounded queue of pending work, a small fixed pool of
asyncio worker tasks that pull from it, and lookup by run ID.
``execute_suite`` (``app.runner.suite_execution``) remains the single
canonical, unchanged execution primitive — this module only decides *when*,
*how many at once*, and (as of Phase 2C) *with which adapter* it runs,
never re-implements what it does.

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
- ``submit()`` validates a real-model request's case IDs and case count
  against ``real_model_max_cases`` *before* touching the queue or the
  repository — an invalid submission is rejected atomically, the same way
  a full queue is (see ``InvalidRunRequestError``).
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
from app.models.run import Run, RunAdapter, RunCreateRequest, RunStatus, RunSummary
from app.runner.adapters import AgentAdapter
from app.runner.suite_execution import execute_suite
from app.runner.transport import MCPTransport

logger = logging.getLogger("agent_interop_bench.run_manager")

TransportFactory = Callable[[], AbstractAsyncContextManager[MCPTransport]]
ExecuteFn = Callable[[str, BenchmarkSuite, MCPTransport], Awaitable[Report]]
RealModelAdapterFactory = Callable[[RunCreateRequest], AgentAdapter]


class RunQueueFullError(Exception):
    """Raised by ``RunManager.submit()`` when the bounded queue has no room.

    The API layer translates this into HTTP 429.
    """


class InvalidRunRequestError(ValueError):
    """Raised by ``RunManager.submit()`` when a request fails precondition
    validation: unknown/duplicate case IDs, a live-model request with no
    explicit model, or a case count exceeding ``real_model_max_cases``.

    Raised before anything is queued or persisted — the API layer
    translates this into HTTP 400. Deployment/environment concerns (is the
    real-model feature enabled, is the provider SDK installed, is a
    credential configured) are deliberately NOT checked here — those are
    the API layer's responsibility (see ``app/api/main.py``), since
    ``RunManager`` takes explicit constructor parameters rather than
    reading global settings itself.
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
        real_model_adapter_factory: RealModelAdapterFactory | None = None,
        real_model_max_cases: int = 3,
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
        self._case_ids = {case.id for case in suite.cases}
        self._transport_factory = transport_factory
        self._repository = repository
        self._execute_fn = execute_fn
        self._real_model_adapter_factory = real_model_adapter_factory
        self._real_model_max_cases = real_model_max_cases
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

    def _validate_request(self, request: RunCreateRequest) -> None:
        if request.case_ids is not None:
            if len(request.case_ids) != len(set(request.case_ids)):
                raise InvalidRunRequestError("case_ids contains duplicate entries")
            unknown = sorted(set(request.case_ids) - self._case_ids)
            if unknown:
                raise InvalidRunRequestError(f"Unknown case_ids: {unknown}")

        if request.adapter == RunAdapter.OPENAI:
            if not request.model:
                raise InvalidRunRequestError(
                    "adapter='openai' requires an explicit 'model'; there is no default live model."
                )
            case_count = (
                len(request.case_ids) if request.case_ids is not None else len(self._suite.cases)
            )
            if case_count > self._real_model_max_cases:
                raise InvalidRunRequestError(
                    f"Live-model run requests {case_count} case(s), exceeding the "
                    f"configured limit of {self._real_model_max_cases}. Pass a "
                    "smaller 'case_ids' selection or raise REAL_MODEL_MAX_CASES."
                )

    def submit(self, request: RunCreateRequest | None = None) -> RunSummary:
        """Validate, allocate a run ID, record it as queued, and enqueue exactly
        one execution.

        Raises ``InvalidRunRequestError`` (before touching the queue or
        repository at all) or ``RunQueueFullError`` (if the queue has no
        room) instead of accepting an invalid or unbounded submission. Never
        blocks.
        """
        if self._queue is None:
            raise RuntimeError("RunManager.submit() called before start()")

        request = request or RunCreateRequest()
        self._validate_request(request)

        run_id = str(uuid.uuid4())
        summary = RunSummary(run_id=run_id, status=RunStatus.QUEUED, created_at=_now())
        try:
            self._queue.put_nowait(run_id)
        except asyncio.QueueFull as exc:
            raise RunQueueFullError(
                f"Run queue is full ({self._queue.maxsize} pending); try again shortly."
            ) from exc
        self._repository.save(Run(summary=summary, request=request))
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

        request = run.request
        running_summary = run.summary.model_copy(
            update={"status": RunStatus.RUNNING, "started_at": _now()}
        )
        self._repository.save(Run(summary=running_summary, request=request))
        logger.info(
            "agent_interop_bench_run_started",
            extra={"run_id": run_id, "adapter": request.adapter.value},
        )

        try:
            async with self._transport_factory() as transport:
                if request.adapter == RunAdapter.DETERMINISTIC:
                    # Unchanged Phase 1/2A/2B path: no provider SDK is
                    # imported, no adapter factory is invoked, no network
                    # call beyond the local MCP subprocess occurs.
                    report = await self._execute_fn(run_id, self._suite, transport)
                else:
                    if self._real_model_adapter_factory is None:
                        raise RuntimeError(
                            "adapter='openai' was requested but no real-model adapter "
                            "factory is configured on this RunManager"
                        )
                    adapter = self._real_model_adapter_factory(request)
                    report = await execute_suite(
                        run_id,
                        self._suite,
                        transport,
                        adapter=adapter,
                        case_ids=request.case_ids,
                    )
                    provenance = getattr(adapter, "provenance", None)
                    if provenance is not None:
                        report = report.model_copy(update={"model_provenance": provenance})
        except Exception as exc:  # noqa: BLE001 - convert any run failure into a stored FAILED run
            logger.exception("agent_interop_bench_run_failed", extra={"run_id": run_id})
            failed_summary = running_summary.model_copy(
                update={
                    "status": RunStatus.FAILED,
                    "failed_at": _now(),
                    "error": _safe_error_message(exc),
                }
            )
            self._repository.save(Run(summary=failed_summary, request=request))
            return

        completed_summary = running_summary.model_copy(
            update={"status": RunStatus.COMPLETED, "completed_at": _now()}
        )
        self._repository.save(Run(summary=completed_summary, request=request, report=report))
        logger.info(
            "agent_interop_bench_run_completed",
            extra={
                "run_id": run_id,
                "passed": report.summary.passed_tests,
                "total": report.summary.total_tests,
            },
        )
