"""Evaluator interface: pure, deterministic, no LLM judge."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.benchmark import BenchmarkCase
from app.models.evaluation import EvaluationResult
from app.models.execution import RunResult
from app.models.tools import ToolDefinition


class Evaluator(ABC):
    """A single deterministic scoring dimension.

    Each evaluator inspects a ``BenchmarkCase`` (ground truth) and the
    ``RunResult`` it produced, and returns a verdict. Evaluators that don't
    apply to a given case's category return ``applicable=False`` rather than
    an artificial pass, so aggregate metrics are only computed over cases
    that actually exercise them.
    """

    name: str

    @abstractmethod
    def evaluate(
        self,
        case: BenchmarkCase,
        result: RunResult,
        tools_by_name: dict[str, ToolDefinition],
    ) -> EvaluationResult: ...

    def not_applicable(self, reason: str) -> EvaluationResult:
        return EvaluationResult(
            evaluator_name=self.name, applicable=False, passed=True, reason=reason
        )
