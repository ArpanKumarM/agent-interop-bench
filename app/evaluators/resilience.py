"""Evaluates graceful handling of tool exceptions/malformed output, and timeout recovery."""

from __future__ import annotations

from app.evaluators.base import Evaluator
from app.models.benchmark import BenchmarkCase
from app.models.enums import FailureMode
from app.models.evaluation import EvaluationResult
from app.models.execution import RunResult
from app.models.tools import ToolDefinition

# Timeouts must be enforced close to the case's declared bound, not left to
# hang until the server-side simulated delay elapses. A generous multiplier
# still catches a runner that isn't actually enforcing the timeout.
TIMEOUT_GRACE_MULTIPLIER = 2.0


class ErrorHandlingEvaluator(Evaluator):
    name = "error_handling"

    def evaluate(
        self,
        case: BenchmarkCase,
        result: RunResult,
        tools_by_name: dict[str, ToolDefinition],
    ) -> EvaluationResult:
        if case.simulated_failure_mode not in (FailureMode.EXCEPTION, FailureMode.MALFORMED):
            return self.not_applicable(
                "Error handling is only scored for exception/malformed failure modes."
            )

        if case.simulated_failure_mode == FailureMode.EXCEPTION:
            passed = result.is_error_result and not result.timed_out and bool(result.error)
            reason = (
                "Tool exception was caught and reported as an error, without hanging."
                if passed
                else "Tool exception was not handled gracefully."
            )
        else:  # MALFORMED
            passed = result.tool_output is not None or result.raw_text_output is not None
            reason = (
                "Malformed response was captured without crashing the runner."
                if passed
                else "Malformed response caused no output to be captured."
            )

        return EvaluationResult(
            evaluator_name=self.name,
            passed=passed,
            reason=reason,
            evidence={
                "is_error_result": result.is_error_result,
                "error": result.error,
                "timed_out": result.timed_out,
            },
        )


class TimeoutRecoveryEvaluator(Evaluator):
    name = "timeout_recovery"

    def evaluate(
        self,
        case: BenchmarkCase,
        result: RunResult,
        tools_by_name: dict[str, ToolDefinition],
    ) -> EvaluationResult:
        if case.simulated_failure_mode != FailureMode.TIMEOUT:
            return self.not_applicable("Timeout recovery is only scored for timeout cases.")

        bound_ms = case.max_latency_ms * TIMEOUT_GRACE_MULTIPLIER
        passed = result.timed_out and result.latency_ms <= bound_ms
        reason = (
            f"Timeout was detected and enforced within {bound_ms:.0f}ms."
            if passed
            else "Runner did not recover from the timeout within the expected bound."
        )
        return EvaluationResult(
            evaluator_name=self.name,
            passed=passed,
            reason=reason,
            evidence={
                "timed_out": result.timed_out,
                "latency_ms": result.latency_ms,
                "max_latency_ms": case.max_latency_ms,
                "bound_ms": bound_ms,
            },
        )
