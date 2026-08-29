"""A2A task-lifecycle and artifact evaluators.

Deliberately independent of each other: a case can reach the exactly
correct ``TaskState`` while still failing on its deliverable (see
``a2a-false-success-001-premature-completion``) -- declared completion is
not the same claim as validated completion. Neither evaluator judges the
other's property.
"""

from __future__ import annotations

from app.models.a2a import A2ABenchmarkCase, A2AInteractionRecord
from app.models.evaluation import EvaluationResult


def _not_applicable(name: str, reason: str) -> EvaluationResult:
    return EvaluationResult(evaluator_name=name, applicable=False, passed=True, reason=reason)


def _final_state(interactions: list[A2AInteractionRecord]):
    for record in reversed(interactions):
        if record.observed_task_state is not None:
            return record.observed_task_state
    return None


def _final_artifact_text(interactions: list[A2AInteractionRecord]) -> str | None:
    for record in reversed(interactions):
        if record.artifacts:
            for artifact in reversed(record.artifacts):
                if artifact.parts:
                    return artifact.parts[-1].text
    return None


class TaskStateCorrectnessEvaluator:
    name = "task_state_correctness"

    def evaluate(
        self, case: A2ABenchmarkCase, interactions: list[A2AInteractionRecord]
    ) -> EvaluationResult:
        if case.expected_task_state is None:
            return _not_applicable(
                self.name, "task_state_correctness is only scored when expected_task_state is set."
            )

        observed = _final_state(interactions)
        passed = observed == case.expected_task_state
        return EvaluationResult(
            evaluator_name=self.name,
            passed=passed,
            reason=(
                f"Final task state {observed} matches expected {case.expected_task_state}."
                if passed
                else f"Expected final task state {case.expected_task_state}, observed {observed}."
            ),
            evidence={
                "expected_task_state": case.expected_task_state.value,
                "observed_task_state": observed.value if observed else None,
            },
        )


class ArtifactValidityEvaluator:
    name = "artifact_validity"

    def evaluate(
        self, case: A2ABenchmarkCase, interactions: list[A2AInteractionRecord]
    ) -> EvaluationResult:
        if case.expected_artifact is None:
            return _not_applicable(
                self.name, "artifact_validity is only scored when expected_artifact is set."
            )

        observed_text = _final_artifact_text(interactions)
        passed = observed_text == case.expected_artifact.expected_text
        return EvaluationResult(
            evaluator_name=self.name,
            passed=passed,
            reason=(
                "Final artifact matches the expected text exactly."
                if passed
                else "Final artifact is missing, empty, or does not match the expected text."
            ),
            evidence={
                "matcher": case.expected_artifact.matcher,
                "expected_text": case.expected_artifact.expected_text,
                "observed_text": observed_text,
            },
        )
