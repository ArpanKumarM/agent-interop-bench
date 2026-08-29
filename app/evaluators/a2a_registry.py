"""Registry of all A2A evaluators. Structurally parallel to
``app.evaluators.registry`` but a separate list -- MCP's registry and
evaluators are untouched."""

from __future__ import annotations

from app.evaluators.a2a_resilience import (
    CapabilityCompatibilityEvaluator,
    RemoteErrorHandlingEvaluator,
)
from app.evaluators.a2a_security import CrossAgentInjectionResistanceEvaluator
from app.evaluators.a2a_task import ArtifactValidityEvaluator, TaskStateCorrectnessEvaluator
from app.models.a2a import A2ABenchmarkCase, A2AInteractionRecord
from app.models.evaluation import EvaluationResult

ALL_A2A_EVALUATORS = [
    TaskStateCorrectnessEvaluator(),
    ArtifactValidityEvaluator(),
    CrossAgentInjectionResistanceEvaluator(),
    RemoteErrorHandlingEvaluator(),
    CapabilityCompatibilityEvaluator(),
]


def evaluate_a2a_case(
    case: A2ABenchmarkCase, interactions: list[A2AInteractionRecord]
) -> list[EvaluationResult]:
    return [evaluator.evaluate(case, interactions) for evaluator in ALL_A2A_EVALUATORS]
