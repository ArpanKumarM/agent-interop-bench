"""Shared enumerations used across benchmark definitions, execution, and scoring."""

from __future__ import annotations

from enum import StrEnum


class FailureMode(StrEnum):
    """Failure conditions the mock MCP server can be told to simulate for a tool call."""

    NORMAL = "normal"
    TIMEOUT = "timeout"
    EXCEPTION = "exception"
    MALFORMED = "malformed"
    PROMPT_INJECTION = "prompt_injection"


class BenchmarkCategory(StrEnum):
    """Classification of what a benchmark case is designed to exercise."""

    CORRECT_TOOL_SELECTION = "correct_tool_selection"
    INCORRECT_TOOL_SELECTION = "incorrect_tool_selection"
    VALID_ARGUMENTS = "valid_arguments"
    MISSING_REQUIRED_ARGUMENT = "missing_required_argument"
    INCORRECT_ARGUMENT_TYPE = "incorrect_argument_type"
    HALLUCINATED_TOOL = "hallucinated_tool"
    TIMEOUT_BEHAVIOR = "timeout_behavior"
    TOOL_EXCEPTION = "tool_exception"
    MALFORMED_RESPONSE = "malformed_response"
    PROMPT_INJECTION = "prompt_injection"
    UNSAFE_MUTATION = "unsafe_mutation"


class ExpectedOutcome(StrEnum):
    """The ground-truth outcome a correctly behaving agent + platform should reach."""

    SUCCESS = "success"
    GRACEFUL_FAILURE = "graceful_failure"
    BLOCKED_UNSAFE = "blocked_unsafe"
    REFUSAL = "refusal"
    RECOVERED = "recovered"
