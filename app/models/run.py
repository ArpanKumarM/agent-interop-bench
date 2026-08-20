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


class RunAdapter(StrEnum):
    """Which AgentAdapter executes a run's decisions.

    ``DETERMINISTIC`` (the default) is free, reproducible, and requires no
    provider dependency or credential — it's what every existing run before
    Phase 2C used, and what an omitted ``adapter`` field still means.
    ``OPENAI`` is optional, incurs provider usage/cost, and is not
    deterministic; see ``docs/scoring.md`` and the README's real-model
    section for the full opt-in contract.
    """

    DETERMINISTIC = "deterministic"
    OPENAI = "openai"


class RunCreateRequest(BaseModel):
    """Request body for POST /runs.

    Only one suite is ever loaded (``BENCHMARKS_PATH``); there is no
    multi-suite execution. ``suite_name`` exists so a caller can name the
    suite they expect to run and be rejected (400) if it doesn't match,
    rather than silently having a different suite run than the one they
    asked for. Omit it, or pass the loaded suite's actual name, to queue a
    run normally.

    ``adapter`` defaults to ``deterministic`` — the existing free,
    reproducible, CI-safe behavior is unchanged for any caller that omits
    this field. Selecting ``openai`` additionally requires ``model``
    (there is no default live model — see Part H's cost-safety design) and
    is subject to ``case_ids``/a configured case-count cap; see
    ``POST /runs``'s validation in ``app/api/main.py``.
    """

    suite_name: str | None = None
    adapter: RunAdapter = RunAdapter.DETERMINISTIC
    model: str | None = None
    case_ids: list[str] | None = None


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
    """Full run record, including its report once completed.

    ``request`` is the (already-validated) submission that created this run
    — RunManager's worker reads it back at execution time to decide which
    adapter to build and which cases to run, rather than the queue carrying
    anything beyond a bare run ID.
    """

    summary: RunSummary
    request: RunCreateRequest = Field(default_factory=RunCreateRequest)
    report: Report | None = None
