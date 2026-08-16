"""Models for evaluator output and aggregated reports."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class EvaluationResult(BaseModel):
    """The verdict of a single deterministic evaluator against one run result."""

    evaluator_name: str
    applicable: bool = True
    passed: bool
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class CaseReport(BaseModel):
    """All evaluation results for one benchmark case, plus a rollup verdict."""

    case_id: str
    category: str
    expected_outcome: str
    passed: bool
    latency_ms: float
    evaluations: list[EvaluationResult]
    failure_reasons: list[str] = Field(default_factory=list)


class ScoreSummary(BaseModel):
    """Aggregate metrics across an entire benchmark run."""

    total_tests: int
    passed_tests: int
    failed_tests: int
    tool_selection_accuracy: float | None
    argument_accuracy: float | None
    recovery_rate: float | None
    unsafe_action_rate: float | None
    prompt_injection_resistance: float | None
    average_latency_ms: float


class Report(BaseModel):
    """The complete JSON reliability report produced for a benchmark run."""

    run_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    suite_name: str
    summary: ScoreSummary
    per_test: list[CaseReport]
    scoring_notes: str = (
        "See docs/scoring.md for the full definition of each metric. "
        "All evaluators are deterministic; no LLM is used as a judge."
    )
