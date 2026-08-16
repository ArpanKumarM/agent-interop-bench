"""Evaluates whether a case expected to succeed actually completed successfully."""

from __future__ import annotations

from app.evaluators.base import Evaluator
from app.models.benchmark import BenchmarkCase
from app.models.enums import ExpectedOutcome
from app.models.evaluation import EvaluationResult
from app.models.execution import RunResult
from app.models.tools import ToolDefinition


class TaskCompletionEvaluator(Evaluator):
    name = "task_completion"

    def evaluate(
        self,
        case: BenchmarkCase,
        result: RunResult,
        tools_by_name: dict[str, ToolDefinition],
    ) -> EvaluationResult:
        if case.expected_outcome != ExpectedOutcome.SUCCESS:
            return self.not_applicable(
                "Task completion is only scored for cases with expected_outcome=success."
            )

        passed = (
            not result.is_error_result
            and not result.timed_out
            and not result.blocked_unsafe
            and (result.tool_output is not None or result.raw_text_output is not None)
        )
        evidence = {
            "is_error_result": result.is_error_result,
            "timed_out": result.timed_out,
            "blocked_unsafe": result.blocked_unsafe,
            "has_output": result.tool_output is not None or result.raw_text_output is not None,
        }
        reason = (
            "Tool call completed successfully with output."
            if passed
            else f"Expected success but got: {result.error or 'no output produced'}."
        )
        return EvaluationResult(
            evaluator_name=self.name, passed=passed, reason=reason, evidence=evidence
        )
