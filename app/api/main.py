"""FastAPI application exposing the Agent Interop Bench MCP evaluation engine.

Run execution (Phase 2B): ``POST /runs`` queues a run and returns
immediately (202); a bounded pool of background workers (``RunManager``)
executes it. See ``app.runner.run_manager`` for the lifecycle and
concurrency model, and ``docs/scoring.md`` / README for the full contract.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response

from app.api.repository import InMemoryRunRepository, RunRepository
from app.core.benchmarks import load_benchmark_suite
from app.core.config import settings
from app.core.logging import configure_logging
from app.models.benchmark import BenchmarkCase
from app.models.evaluation import Report
from app.models.run import RunCreateRequest, RunStatus, RunSummary
from app.models.tools import ToolDefinition
from app.runner.run_manager import RunManager, RunQueueFullError
from app.runner.transport import StdioMCPTransport

configure_logging(settings.log_level)
logger = logging.getLogger("agent_interop_bench.api")


def new_transport() -> StdioMCPTransport:
    return StdioMCPTransport(command=settings.mock_server_command, args=settings.mock_server_args)


class AppState:
    """Process-lifetime state: loaded suite, run storage, and the background run manager."""

    def __init__(self) -> None:
        self.suite = load_benchmark_suite(settings.benchmarks_path)
        self.run_repository: RunRepository = InMemoryRunRepository()
        self.run_manager = RunManager(
            suite=self.suite,
            transport_factory=new_transport,
            repository=self.run_repository,
            queue_maxsize=settings.run_queue_maxsize,
            worker_count=settings.run_worker_count,
        )


app_state = AppState()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "agent_interop_bench_startup",
        extra={
            "suite_name": app_state.suite.name,
            "case_count": len(app_state.suite.cases),
            "run_worker_count": settings.run_worker_count,
            "run_queue_maxsize": settings.run_queue_maxsize,
        },
    )
    await app_state.run_manager.start()
    try:
        yield
    finally:
        await app_state.run_manager.stop()


app = FastAPI(
    title="Agent Interop Bench",
    description=(
        "Reliability, security, and interoperability testing for MCP and A2A agents. "
        "MCP is implemented; A2A support is planned. Benchmark runs execute in the "
        "background against a bounded worker pool; see /runs for the queued/running/"
        "completed/failed lifecycle."
    ),
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/tools", response_model=list[ToolDefinition])
async def list_tools() -> list[ToolDefinition]:
    async with new_transport() as transport:
        return await transport.list_tools()


@app.get("/benchmarks", response_model=list[BenchmarkCase])
async def list_benchmarks() -> list[BenchmarkCase]:
    return app_state.suite.cases


@app.post("/runs", response_model=RunSummary, status_code=202)
async def create_run(response: Response, request: RunCreateRequest | None = None) -> RunSummary:
    """Queue a benchmark run and return immediately. Does not wait for completion.

    Only one suite is ever loaded and executed (``app_state.suite``, from
    ``BENCHMARKS_PATH``) — there is no multi-suite support. ``suite_name``
    is therefore validated, not used to select behavior: omitting it, or
    passing exactly the loaded suite's name, queues a run; any other value
    is rejected with ``400`` before anything is queued, so a caller can
    never be misled into thinking a different suite ran.

    Poll ``GET /runs/{run_id}`` for lifecycle status and
    ``GET /runs/{run_id}/report`` once ``status == "completed"``.
    """
    if (
        request is not None
        and request.suite_name is not None
        and request.suite_name != app_state.suite.name
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown suite_name '{request.suite_name}'; "
                f"only '{app_state.suite.name}' is available."
            ),
        )

    try:
        summary = app_state.run_manager.submit()
    except RunQueueFullError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    response.headers["Location"] = f"/runs/{summary.run_id}"
    logger.info("agent_interop_bench_run_queued", extra={"run_id": summary.run_id})
    return summary


@app.get("/runs/{run_id}", response_model=RunSummary)
async def get_run(run_id: str) -> RunSummary:
    """Lifecycle metadata only — never the full report. See /runs/{run_id}/report for that."""
    run = app_state.run_manager.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run.summary


def _report_not_ready_detail(run_id: str, status: RunStatus) -> dict[str, str]:
    messages = {
        RunStatus.QUEUED: "Run is queued and has not started yet.",
        RunStatus.RUNNING: "Run is still executing.",
        RunStatus.FAILED: (
            f"Run failed; no report was produced. See GET /runs/{run_id} for error details."
        ),
    }
    return {
        "run_id": run_id,
        "status": status.value,
        "message": messages.get(status, "Report is not available."),
    }


@app.get("/runs/{run_id}/report", response_model=Report)
async def get_run_report(run_id: str) -> Report:
    """Return the persisted report, only once the run has completed successfully.

    - Unknown run: 404.
    - Queued / running / failed: 409, with structured detail identifying why
      (never a fabricated report for a failed run).
    - Completed: 200 with the exact persisted ``Report``.
    """
    run = app_state.run_manager.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    if run.summary.status != RunStatus.COMPLETED or run.report is None:
        raise HTTPException(
            status_code=409, detail=_report_not_ready_detail(run_id, run.summary.status)
        )
    return run.report
