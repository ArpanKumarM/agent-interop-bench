"""API-facing models for benchmark runs and their lifecycle.

A run moves through exactly four states, one-directionally:

    queued -> running -> completed
                       -> failed

``completed`` and ``failed`` are terminal: a run in either state never
transitions again. See ``app.runner.run_manager.RunManager`` for the code
that enforces this.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.evaluation import Report


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RunCreateRequest(BaseModel):
    """Request body for POST /runs.

    Only one suite is ever loaded (``BENCHMARKS_PATH``); there is no
    multi-suite execution. ``suite_name`` exists so a caller can name the
    suite they expect to run and be rejected (400) if it doesn't match,
    rather than silently having a different suite run than the one they
    asked for. Omit it, or pass the loaded suite's actual name, to queue a
    run normally.
    """

    suite_name: str | None = None


class RunSummary(BaseModel):
    """Lifecycle metadata for a run, returned by GET /runs/{run_id}.

    Timestamp invariants by status, all timezone-aware UTC:

    - ``queued``:    ``created_at`` set; ``started_at``/``completed_at``/``failed_at`` all ``None``.
    - ``running``:   ``created_at`` + ``started_at`` set; ``completed_at``/``failed_at`` ``None``.
    - ``completed``: ``created_at`` + ``started_at`` + ``completed_at`` set; ``failed_at`` ``None``;
      ``error`` ``None``; the corresponding ``Run.report`` is present.
    - ``failed``:    ``created_at`` + ``started_at`` + ``failed_at`` set; ``completed_at`` ``None``;
      ``error`` set; the corresponding ``Run.report`` is ``None`` (never fabricated).
    """

    run_id: str
    status: RunStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failed_at: datetime | None = None
    error: str | None = None


class Run(BaseModel):
    """Full run record, including its report once completed."""

    summary: RunSummary
    report: Report | None = None
