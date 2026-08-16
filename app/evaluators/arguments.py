"""Evaluates argument correctness and JSON-schema validity of selected arguments."""

from __future__ import annotations

import jsonschema

from app.evaluators.base import Evaluator
from app.models.benchmark import BenchmarkCase
from app.models.evaluation import EvaluationResult
from app.models.execution import RunResult
from app.models.tools import ToolDefinition


class ArgumentCorrectnessEvaluator(Evaluator):
    name = "argument_correctness"

    def evaluate(
        self,
        case: BenchmarkCase,
        result: RunResult,
        tools_by_name: dict[str, ToolDefinition],
    ) -> EvaluationResult:
        if case.expected_tool is None or result.selected_tool != case.expected_tool:
            return self.not_applicable(
                "Argument correctness is only scored when the expected tool was selected."
            )

        passed = result.selected_arguments == case.expected_arguments
        evidence = {
            "expected_arguments": case.expected_arguments,
            "selected_arguments": result.selected_arguments,
        }
        reason = (
            "Arguments match the expected arguments exactly."
            if passed
            else "Selected arguments differ from the expected arguments."
        )
        return EvaluationResult(
            evaluator_name=self.name, passed=passed, reason=reason, evidence=evidence
        )


class SchemaValidityEvaluator(Evaluator):
    name = "schema_validity"

    def evaluate(
        self,
        case: BenchmarkCase,
        result: RunResult,
        tools_by_name: dict[str, ToolDefinition],
    ) -> EvaluationResult:
        if result.selected_tool is None or result.tool_not_found:
            return self.not_applicable("No known tool was selected; nothing to validate.")

        tool_def = tools_by_name.get(result.selected_tool)
        if tool_def is None:
            return self.not_applicable("Selected tool is not a discovered tool.")

        try:
            jsonschema.validate(instance=result.selected_arguments, schema=tool_def.input_schema)
        except jsonschema.ValidationError as exc:
            return EvaluationResult(
                evaluator_name=self.name,
                passed=False,
                reason=f"Arguments violate the tool's input schema: {exc.message}",
                evidence={"validation_error": exc.message},
            )

        return EvaluationResult(
            evaluator_name=self.name,
            passed=True,
            reason="Arguments conform to the tool's declared input schema.",
        )
