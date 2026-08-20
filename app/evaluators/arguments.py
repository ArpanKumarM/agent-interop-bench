"""Evaluates argument correctness and JSON-schema validity of selected arguments."""

from __future__ import annotations

from typing import Any

import jsonschema

from app.evaluators.base import Evaluator
from app.models.benchmark import BenchmarkCase
from app.models.evaluation import EvaluationResult
from app.models.execution import RunResult
from app.models.tools import ToolDefinition


def _matches(matcher: str, expected_value, actual_value, terms: list[str] | None) -> bool:
    if matcher == "contains_substrings":
        if not isinstance(actual_value, str):
            return False
        lowered = actual_value.lower()
        return all(term.lower() in lowered for term in terms or ())
    return actual_value == expected_value


class ArgumentCorrectnessEvaluator(Evaluator):
    """Compares selected arguments against ``expected_arguments``.

    Every argument is matched with exact equality (``==``) by default. A case
    may opt a specific argument into a looser, still-deterministic matcher via
    ``argument_match_rules`` (see ``app.models.benchmark.ArgumentMatchRule``)
    — this is never inferred from observed model behavior, only from a
    benchmark author's explicit declaration on the case.
    """

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

        expected = case.expected_arguments
        selected = result.selected_arguments or {}
        rules = case.argument_match_rules

        extra_keys = sorted(set(selected) - set(expected))
        missing_keys = sorted(set(expected) - set(selected))

        matchers_used: dict[str, str] = {}
        mismatches: dict[str, dict[str, Any]] = {}
        for key, expected_value in expected.items():
            rule = rules.get(key)
            matcher = rule.matcher if rule else "exact"
            matchers_used[key] = matcher
            if key not in selected:
                continue
            actual_value = selected[key]
            terms = rule.terms if rule else None
            if not _matches(matcher, expected_value, actual_value, terms):
                mismatches[key] = {
                    "matcher": matcher,
                    "expected": terms if matcher == "contains_substrings" else expected_value,
                    "actual": actual_value,
                }

        passed = not extra_keys and not missing_keys and not mismatches
        evidence = {
            "expected_arguments": expected,
            "selected_arguments": selected,
            "matchers_used": matchers_used,
            "mismatches": mismatches,
            "extra_keys": extra_keys,
            "missing_keys": missing_keys,
        }
        if passed:
            reason = "Arguments match the expected arguments under each argument's matcher."
        else:
            parts = []
            if missing_keys:
                parts.append(f"missing argument(s) {missing_keys}")
            if extra_keys:
                parts.append(f"unexpected argument(s) {extra_keys}")
            if mismatches:
                parts.append(f"mismatched argument(s) {sorted(mismatches)}")
            reason = "Selected arguments differ from expected: " + "; ".join(parts) + "."
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
