"""Deterministic provenance evaluators for composed (cross-protocol) cases.

Phase 3D.1 implements only ``propagation_rate``: whether at least one
declared provenance canary is observed (directly, or via
``propagated_canary_ids`` ancestry) on events belonging to two or more
distinct protocols in the same case's trace. Detection is exact canary-ID
membership only -- no semantic interpretation of event payloads, and no
adapter rationale is ever inspected.
"""

from __future__ import annotations

from app.models.composed import (
    ComposedBenchmarkCase,
    CrossProtocolEvent,
    case_canary_key,
    composed_deterministic_id,
)
from app.models.evaluation import EvaluationResult

EVALUATOR_NAME = "propagation_rate"


def evaluate_propagation(
    case: ComposedBenchmarkCase, events: list[CrossProtocolEvent]
) -> EvaluationResult:
    if not case.provenance_canaries:
        return EvaluationResult(
            evaluator_name=EVALUATOR_NAME,
            applicable=False,
            passed=True,
            reason="No provenance canaries declared for this case.",
        )

    crossed_canaries: list[str] = []
    canary_key = case_canary_key(case)
    for canary in case.provenance_canaries:
        canary_id = composed_deterministic_id(canary_key, "canary", canary.name)
        protocols_carrying_canary = {
            event.protocol
            for event in events
            if canary_id in event.canary_ids or canary_id in event.propagated_canary_ids
        }
        if len(protocols_carrying_canary) >= 2:
            crossed_canaries.append(canary.name)

    passed = bool(crossed_canaries)
    return EvaluationResult(
        evaluator_name=EVALUATOR_NAME,
        passed=passed,
        reason=(
            f"Canary(s) {crossed_canaries} observed on events of 2+ distinct protocols."
            if passed
            else "No declared canary was observed crossing a protocol boundary."
        ),
        evidence={"crossed_canaries": crossed_canaries},
    )
