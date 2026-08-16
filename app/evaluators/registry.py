"""Registry of all evaluators and the aggregate that runs them for one case."""

from __future__ import annotations

from app.evaluators.arguments import ArgumentCorrectnessEvaluator, SchemaValidityEvaluator
from app.evaluators.base import Evaluator
from app.evaluators.completion import TaskCompletionEvaluator
from app.evaluators.resilience import ErrorHandlingEvaluator, TimeoutRecoveryEvaluator
from app.evaluators.safety import UnsafeActionEvaluator
from app.evaluators.security import PromptInjectionEvaluator
from app.evaluators.tool_selection import ToolSelectionEvaluator
from app.models.benchmark import BenchmarkCase
from app.models.evaluation import EvaluationResult
from app.models.execution import RunResult
from app.models.tools import ToolDefinition

ALL_EVALUATORS: list[Evaluator] = [
    ToolSelectionEvaluator(),
    ArgumentCorrectnessEvaluator(),
    SchemaValidityEvaluator(),
    TaskCompletionEvaluator(),
    ErrorHandlingEvaluator(),
    TimeoutRecoveryEvaluator(),
    UnsafeActionEvaluator(),
    PromptInjectionEvaluator(),
]


def evaluate_case(
    case: BenchmarkCase,
    result: RunResult,
    tools_by_name: dict[str, ToolDefinition],
) -> list[EvaluationResult]:
    """Run every evaluator against one case/result pair."""
    return [evaluator.evaluate(case, result, tools_by_name) for evaluator in ALL_EVALUATORS]
