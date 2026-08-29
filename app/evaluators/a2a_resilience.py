"""A2A remote-failure and capability-negotiation evaluators.

``capability_compatibility`` scores the client's *request* for compliance
with the target's declared ``AgentCard`` capabilities -- it is independent
of ``remote_error_handling``, which scores whether a resulting protocol
error (of any kind, capability-related or not) was handled gracefully. A
case can fail the first while passing the second: sending an unsupported
content type is a client-behavior defect (FAIL), while cleanly stopping
after the resulting rejection is correct infrastructure-facing behavior
(PASS) -- the two questions are answered independently, never conflated
into one evaluator.
"""

from __future__ import annotations

from app.models.a2a import A2ABenchmarkCase, A2AInteractionRecord
from app.models.evaluation import EvaluationResult

_REMOTE_FAILURE_MODES = {"remote_task_failure", "unavailable", "malformed"}


def _not_applicable(name: str, reason: str) -> EvaluationResult:
    return EvaluationResult(evaluator_name=name, applicable=False, passed=True, reason=reason)


class RemoteErrorHandlingEvaluator:
    name = "remote_error_handling"

    def evaluate(
        self, case: A2ABenchmarkCase, interactions: list[A2AInteractionRecord]
    ) -> EvaluationResult:
        applicable_modes = _REMOTE_FAILURE_MODES | {"unsupported_content_type"}
        if case.failure_mode not in applicable_modes:
            return _not_applicable(
                self.name, "remote_error_handling is only scored for failure-mode cases."
            )

        last = interactions[-1] if interactions else None
        graceful = last is not None and last.termination_classification in (
            "failed",
            "rejected",
            "stopped",
        )
        within_budget = len(interactions) <= case.max_interaction_steps
        passed = graceful and within_budget
        return EvaluationResult(
            evaluator_name=self.name,
            passed=passed,
            reason=(
                "The failure/rejection was observed and the client terminated cleanly, "
                "without hanging or exceeding its interaction-step budget."
                if passed
                else "The client did not terminate gracefully after the failure/rejection."
            ),
            evidence={
                "termination_classification": last.termination_classification if last else None,
                "step_count": len(interactions),
                "max_interaction_steps": case.max_interaction_steps,
            },
        )


class CapabilityCompatibilityEvaluator:
    name = "capability_compatibility"

    def evaluate(
        self, case: A2ABenchmarkCase, interactions: list[A2AInteractionRecord]
    ) -> EvaluationResult:
        if case.failure_mode != "unsupported_content_type":
            return _not_applicable(
                self.name,
                "capability_compatibility is only scored for unsupported_content_type cases.",
            )

        violation = next(
            (
                r
                for r in interactions
                if r.protocol_error
                and r.protocol_error.get("reason") == "CONTENT_TYPE_NOT_SUPPORTED"
            ),
            None,
        )
        passed = violation is None
        return EvaluationResult(
            evaluator_name=self.name,
            passed=passed,
            reason=(
                "Client never requested a content type outside the target's declared "
                "defaultInputModes."
                if passed
                else "Client requested a content type the target's AgentCard never declared "
                "support for."
            ),
            evidence={
                "declared_input_modes": case.target_agent_card.default_input_modes,
                "violating_step": violation.step_index if violation else None,
                "protocol_error": violation.protocol_error if violation else None,
            },
        )
