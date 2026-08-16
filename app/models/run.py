"""API-facing models for benchmark runs."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.evaluation import Report


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RunCreateRequest(BaseModel):
    """Request body for POST /runs. Empty for Phase 1 (always runs the full suite)."""

    suite_name: str | None = None


class RunSummary(BaseModel):
    """Lightweight run metadata, returned by GET /runs/{run_id}."""

    run_id: str
    status: RunStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    error: str | None = None


class Run(BaseModel):
    """Full run record, including its report once completed."""

    summary: RunSummary
    report: Report | None = None
