"""FastAPI application exposing the AgentTrust Phase 1 MCP evaluation engine."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, HTTPException

from app.api.repository import InMemoryRunRepository, RunRepository
from app.core.benchmarks import load_benchmark_suite
from app.core.config import settings
from app.core.logging import configure_logging
from app.models.benchmark import BenchmarkCase
from app.models.run import Run, RunCreateRequest, RunStatus, RunSummary
from app.models.tools import ToolDefinition
from app.runner.suite_execution import execute_suite
from app.runner.transport import StdioMCPTransport

configure_logging(settings.log_level)
logger = logging.getLogger("agenttrust.api")


class AppState:
    """Process-lifetime state: loaded suite and the run repository."""

    def __init__(self) -> None:
        self.suite = load_benchmark_suite(settings.benchmarks_path)
        self.run_repository: RunRepository = InMemoryRunRepository()


app_state = AppState()


def new_transport() -> StdioMCPTransport:
    return StdioMCPTransport(command=settings.mock_server_command, args=settings.mock_server_args)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "agenttrust_startup",
        extra={"suite_name": app_state.suite.name, "case_count": len(app_state.suite.cases)},
    )
    yield


app = FastAPI(
    title="AgentTrust",
    description="Reliability and security evaluation platform for MCP agents (Phase 1).",
    version="0.1.0",
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


@app.post("/runs", response_model=RunSummary)
async def create_run(_: RunCreateRequest | None = None) -> RunSummary:
    run_id = str(uuid.uuid4())
    summary = RunSummary(run_id=run_id, status=RunStatus.RUNNING)
    app_state.run_repository.save(Run(summary=summary))

    logger.info("agenttrust_run_started", extra={"run_id": run_id})
    try:
        async with new_transport() as transport:
            report = await execute_suite(run_id, app_state.suite, transport)
    except Exception as exc:  # noqa: BLE001 - convert any run failure into a stored FAILED run
        logger.exception("agenttrust_run_failed", extra={"run_id": run_id})
        failed_summary = RunSummary(
            run_id=run_id,
            status=RunStatus.FAILED,
            created_at=summary.created_at,
            completed_at=datetime.now(UTC),
            error=str(exc),
        )
        app_state.run_repository.save(Run(summary=failed_summary))
        raise HTTPException(status_code=500, detail=f"Run failed: {exc}") from exc

    completed_summary = RunSummary(
        run_id=run_id,
        status=RunStatus.COMPLETED,
        created_at=summary.created_at,
        completed_at=datetime.now(UTC),
    )
    app_state.run_repository.save(Run(summary=completed_summary, report=report))
    logger.info(
        "agenttrust_run_completed",
        extra={
            "run_id": run_id,
            "passed": report.summary.passed_tests,
            "total": report.summary.total_tests,
        },
    )
    return completed_summary


@app.get("/runs/{run_id}", response_model=RunSummary)
async def get_run(run_id: str) -> RunSummary:
    run = app_state.run_repository.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return run.summary


@app.get("/runs/{run_id}/report")
async def get_run_report(run_id: str):
    run = app_state.run_repository.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    if run.report is None:
        raise HTTPException(
            status_code=409,
            detail=f"Run '{run_id}' has status '{run.summary.status}', no report yet",
        )
    return run.report
