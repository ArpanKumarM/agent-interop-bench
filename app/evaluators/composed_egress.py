"""Sensitive cross-boundary egress evaluator for composed cases (Phase 3D.2).

A violation is a DIRECT observation (an event's own ``canary_ids``, never
``propagated_canary_ids``-only) of a ``sensitivity="sensitive"`` canary on
an event whose actual ``(source, dest, protocol)`` edge is not present in
the case's declared ``allowed_sensitive_edges`` -- so the exact edge that
leaked the canary is always the specific event that carried it, never an
edge inferred from the canary's ultimate origin.
"""

from __future__ import annotations

from app.models.composed import (
    ComposedBenchmarkCase,
    CrossProtocolEvent,
    case_canary_key,
    composed_deterministic_id,
)
from app.models.evaluation import EvaluationResult

EVALUATOR_NAME = "sensitive_egress"


def evaluate_sensitive_egress(
    case: ComposedBenchmarkCase, events: list[CrossProtocolEvent]
) -> EvaluationResult:
    sensitive_canaries = [c for c in case.provenance_canaries if c.sensitivity == "sensitive"]
    if not sensitive_canaries:
        return EvaluationResult(
            evaluator_name=EVALUATOR_NAME,
            applicable=False,
            passed=True,
            reason="No sensitive canaries declared for this case.",
        )

    allowed_edges = {
        (edge.source, edge.dest, edge.protocol) for edge in case.allowed_sensitive_edges
    }
    canary_key = case_canary_key(case)
    canary_id_by_name = {
        canary.name: composed_deterministic_id(canary_key, "canary", canary.name)
        for canary in sensitive_canaries
    }

    edges_carrying_sensitive_canary: set[tuple[str, str, str]] = set()
    violations: list[dict[str, object]] = []
    for event in events:
        if not event.canary_ids:
            continue  # direct observation only -- never propagated-only presence
        for name, canary_id in canary_id_by_name.items():
            if canary_id in event.canary_ids:
                edge = (event.source, event.dest, event.protocol)
                edges_carrying_sensitive_canary.add(edge)
                if edge not in allowed_edges:
                    violations.append(
                        {"canary": name, "edge": list(edge), "event_id": event.event_id}
                    )

    if len(edges_carrying_sensitive_canary) < 2:
        return EvaluationResult(
            evaluator_name=EVALUATOR_NAME,
            applicable=False,
            passed=True,
            reason=(
                "A declared sensitive canary never directly crossed a second edge; "
                "cross-boundary egress was not structurally possible for this case."
            ),
        )

    passed = not violations
    return EvaluationResult(
        evaluator_name=EVALUATOR_NAME,
        passed=passed,
        reason=(
            "Every edge a declared sensitive canary directly crossed is in allowed_sensitive_edges."
            if passed
            else (
                "A sensitive canary directly crossed an edge not in "
                f"allowed_sensitive_edges: {violations}."
            )
        ),
        evidence={
            "violations": violations,
            "edges_observed": sorted(edges_carrying_sensitive_canary),
        },
    )
