"""Models describing a single benchmark case execution."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import FailureMode


class ToolCallDecision(BaseModel):
    """A decision made by an AgentAdapter: which tool to call, and with what arguments.

    ``tool_name`` is ``None`` when the adapter deliberately declines to call any
    tool (a refusal), which is itself a valid, scoreable outcome.
    """

    tool_name: str | None
    arguments: dict[str, Any] = Field(default_factory=dict)
    rationale: str | None = None


class RunResult(BaseModel):
    """Everything captured while executing one benchmark case."""

    case_id: str
    selected_tool: str | None
    selected_arguments: dict[str, Any] = Field(default_factory=dict)
    tool_output: Any | None = None
    raw_text_output: str | None = None
    error: str | None = None
    is_error_result: bool = False
    latency_ms: float
    failure_mode_applied: FailureMode
    timed_out: bool = False
    blocked_unsafe: bool = False
    tool_not_found: bool = False
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
