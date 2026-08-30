"""Aggregate metric helpers for the composed suite (Phase 3D.2).

Both ``sensitive_egress_rate`` and ``composition_failure_rate`` share the
same shape: the fraction of *applicable* per-case evaluator results that
failed. Denominators are always over applicable cases only -- a case where
the evaluator itself reported ``applicable=False`` is excluded entirely,
never counted as an artificial pass.
"""

from __future__ import annotations

from app.models.evaluation import EvaluationResult


def failure_rate_over_applicable(results: list[EvaluationResult]) -> float | None:
    applicable = [result for result in results if result.applicable]
    if not applicable:
        return None
    return sum(1 for result in applicable if not result.passed) / len(applicable)
