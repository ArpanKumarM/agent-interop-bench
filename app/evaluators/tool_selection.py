"""Evaluates whether the agent selected the correct tool."""

from __future__ import annotations

from app.evaluators.base import Evaluator
from app.models.benchmark import BenchmarkCase
from app.models.evaluation import EvaluationResult
from app.models.execution import RunResult
from app.models.tools import ToolDefinition


class ToolSelectionEvaluator(Evaluator):
    name = "tool_selection_accuracy"

    def evaluate(
        self,
        case: BenchmarkCase,
        result: RunResult,
        tools_by_name: dict[str, ToolDefinition],
    ) -> EvaluationResult:
        passed = result.selected_tool == case.expected_tool
        evidence = {
            "expected_tool": case.expected_tool,
            "selected_tool": result.selected_tool,
            "hallucinated": result.tool_not_found,
        }
        if passed:
            reason = "Selected tool matches expected tool."
        elif result.tool_not_found:
            reason = f"Agent called a nonexistent tool: '{result.selected_tool}'."
        else:
            reason = f"Expected tool '{case.expected_tool}', got '{result.selected_tool}'."
        return EvaluationResult(
            evaluator_name=self.name, passed=passed, reason=reason, evidence=evidence
        )
