"""Models for evaluator output and aggregated reports."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.execution import TerminationReason, TurnResult
from app.models.provenance import ModelRunProvenance


class EvaluationResult(BaseModel):
    """The verdict of a single deterministic evaluator against one run result."""

    evaluator_name: str
    applicable: bool = True
    passed: bool
    reason: str
    evidence: dict[str, Any] = Field(default_factory=dict)


class CaseReport(BaseModel):
    """All evaluation results for one benchmark case, plus a rollup verdict.

    ``turns`` and ``termination_reason`` are the full, persisted interaction
    trace for this case — not just what individual evaluators chose to
    surface in their ``evidence``. Every executed or blocked turn (adapter
    decision, requested tool/arguments, mutation/safety-gate verdict,
    execution status, tool output/error, per-turn latency) is reconstructable
    directly from this JSON report, without relying on any evaluator's
    evidence dict as the only record of what happened.
    """

    case_id: str
    category: str
    expected_outcome: str
    passed: bool
    latency_ms: float
    turns: list[TurnResult]
    termination_reason: TerminationReason
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
    # Mean pass rate of `trajectory_integrity`, over cases with at least one
    # reaction turn (turns after the first) -- `None` for a run with no such
    # cases. See docs/scoring.md: this is independent of, and does not
    # replace, prompt_injection_resistance or unsafe_action_detection.
    trajectory_integrity: float | None
    average_latency_ms: float


class Report(BaseModel):
    """The complete JSON reliability report produced for a benchmark run.

    ``model_provenance`` is ``None`` for every deterministic run (the
    default, and the only kind of run CI or an unconfigured deployment can
    ever produce) and is the single, unambiguous signal that a report came
    from a live model adapter instead: its presence means this report is
    **not deterministic** and may not reproduce identically on a re-run,
    even with the same configuration. See ``app.models.provenance`` and
    `docs/scoring.md`.
    """

    run_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    suite_name: str
    # BenchmarkSuite.version at the time this run was scored (e.g. "0.2.0").
    # Evaluator semantics can change between suite versions (see
    # docs/scoring.md's "argument_correctness matchers" section) without any
    # change to run_id, generated_at, or suite_name, so a consumer needs this
    # to know which evaluator semantics produced a given report without
    # consulting git history or a filename.
    suite_version: str
    summary: ScoreSummary
    per_test: list[CaseReport]
    model_provenance: ModelRunProvenance | None = None
    scoring_notes: str = (
        "See docs/scoring.md for the full definition of each metric. "
        "All evaluators are deterministic; no LLM is used as a judge. "
        "If model_provenance is set, the underlying decisions came from a "
        "live model adapter and this report's results are not reproducible."
    )
