"""Tool-schema translation (MCP -> OpenAI function tool), tested against
representative schemas actually discovered from the real mock MCP server
(see conftest fixtures below, captured via `transport.list_tools()`), not
hand-simplified stand-ins.
"""

from __future__ import annotations

import pytest

from app.models.tools import ToolDefinition
from app.runner.tool_schema_openai import (
    ToolSchemaTranslationError,
    tool_schema_fingerprint,
    translate_tool_for_openai,
    translate_tools_for_openai,
)

# Captured verbatim from `await transport.list_tools()` against the real
# mock_servers/github_mock.py server — these are the actual discovered
# schemas, `failure_mode` included, exactly as OpenAIResponsesAdapter would
# receive them from suite_execution.
SEARCH_ISSUES = ToolDefinition(
    name="search_issues",
    description="Search issues in a repository by query string.",
    input_schema={
        "properties": {
            "repo": {"title": "Repo", "type": "string"},
            "query": {"title": "Query", "type": "string"},
            "failure_mode": {"$ref": "#/$defs/FailureMode", "default": "normal"},
        },
        "required": ["repo", "query"],
        "type": "object",
        "$defs": {
            "FailureMode": {
                "description": "Failure conditions the mock MCP server can simulate.",
                "enum": ["normal", "timeout", "exception", "malformed", "prompt_injection"],
                "title": "FailureMode",
                "type": "string",
            }
        },
        "title": "search_issuesArguments",
    },
    required_arguments=["repo", "query"],
    is_mutating=False,
)

CREATE_COMMENT = ToolDefinition(
    name="create_comment",
    description="Create a comment on an issue. This is a MUTATING operation.",
    input_schema={
        "properties": {
            "repo": {"title": "Repo", "type": "string"},
            "issue_number": {"title": "Issue Number", "type": "integer"},
            "body": {"title": "Body", "type": "string"},
            "failure_mode": {"$ref": "#/$defs/FailureMode", "default": "normal"},
        },
        "required": ["repo", "issue_number", "body"],
        "type": "object",
        "$defs": {
            "FailureMode": {
                "description": "Failure conditions the mock MCP server can simulate.",
                "enum": ["normal", "timeout", "exception", "malformed", "prompt_injection"],
                "title": "FailureMode",
                "type": "string",
            }
        },
        "title": "create_commentArguments",
    },
    required_arguments=["repo", "issue_number", "body"],
    is_mutating=True,
)

CALCULATE_SUM = ToolDefinition(
    name="calculate_sum",
    description="Add two numbers together.",
    input_schema={
        "properties": {
            "a": {"title": "A", "type": "number"},
            "b": {"title": "B", "type": "number"},
            "failure_mode": {"$ref": "#/$defs/FailureMode", "default": "normal"},
        },
        "required": ["a", "b"],
        "type": "object",
        "$defs": {"FailureMode": {"type": "string"}},
        "title": "calculate_sumArguments",
    },
    required_arguments=["a", "b"],
    is_mutating=False,
)


def test_translated_tool_has_top_level_openai_function_shape():
    translated = translate_tool_for_openai(SEARCH_ISSUES)
    assert set(translated.keys()) == {"type", "name", "description", "parameters", "strict"}
    assert translated["type"] == "function"
    assert translated["strict"] is True


def test_tool_name_and_description_are_unchanged():
    translated = translate_tool_for_openai(SEARCH_ISSUES)
    assert translated["name"] == "search_issues"
    assert translated["description"] == "Search issues in a repository by query string."


def test_failure_mode_is_stripped_from_properties_and_required():
    translated = translate_tool_for_openai(SEARCH_ISSUES)
    params = translated["parameters"]
    assert "failure_mode" not in params["properties"]
    assert "failure_mode" not in params["required"]
    # Nothing else references FailureMode/$defs anymore, so it isn't carried over.
    assert "$defs" not in params


def test_required_arguments_remain_required_and_match_originals():
    translated = translate_tool_for_openai(CREATE_COMMENT)
    params = translated["parameters"]
    assert set(params["required"]) == {"repo", "issue_number", "body"}
    assert set(params["properties"]) == {"repo", "issue_number", "body"}


def test_strict_mode_sets_additional_properties_false():
    translated = translate_tool_for_openai(CALCULATE_SUM)
    assert translated["parameters"]["additionalProperties"] is False


def test_no_additional_capability_is_introduced():
    """The translated schema exposes exactly the tool's real, non-harness
    properties — nothing invented, nothing from another tool."""
    translated = translate_tool_for_openai(CALCULATE_SUM)
    assert set(translated["parameters"]["properties"]) == {"a", "b"}


def test_a_model_cannot_be_offered_a_tool_that_was_not_supplied():
    translated = translate_tools_for_openai([SEARCH_ISSUES, CALCULATE_SUM])
    names = {t["name"] for t in translated}
    assert names == {"search_issues", "calculate_sum"}
    assert "create_comment" not in names


def test_property_type_and_enum_semantics_are_preserved_where_present():
    translated = translate_tool_for_openai(CREATE_COMMENT)
    props = translated["parameters"]["properties"]
    assert props["issue_number"]["type"] == "integer"
    assert props["repo"]["type"] == "string"
    assert props["body"]["type"] == "string"


def test_translation_rejects_a_tool_with_a_genuinely_optional_argument():
    """If a future tool has a real optional argument (not the harness-only
    failure_mode), strict-mode translation must refuse rather than silently
    mislabeling it required or dropping strict mode — see the module
    docstring's documented decision."""
    tool_with_optional_arg = ToolDefinition(
        name="hypothetical_tool",
        description="A tool with a genuinely optional argument.",
        input_schema={
            "properties": {
                "required_arg": {"type": "string"},
                "optional_arg": {"type": "string"},
            },
            "required": ["required_arg"],
            "type": "object",
        },
        required_arguments=["required_arg"],
        is_mutating=False,
    )
    with pytest.raises(ToolSchemaTranslationError, match="optional_arg"):
        translate_tool_for_openai(tool_with_optional_arg)


def test_nested_object_properties_pass_through_structurally_unchanged():
    """A tool with a nested object argument (none of this project's real
    tools currently have one, but the translator must not mangle one if a
    future tool does) must keep the nested schema intact — not flattened,
    not stripped, not silently altered — as long as every top-level
    property remains required."""
    tool_with_nested_object = ToolDefinition(
        name="hypothetical_nested_tool",
        description="A tool with a nested object argument.",
        input_schema={
            "properties": {
                "filters": {
                    "type": "object",
                    "properties": {
                        "min_stars": {"type": "integer"},
                        "labels": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["min_stars", "labels"],
                },
            },
            "required": ["filters"],
            "type": "object",
        },
        required_arguments=["filters"],
        is_mutating=False,
    )
    translated = translate_tool_for_openai(tool_with_nested_object)
    filters_schema = translated["parameters"]["properties"]["filters"]
    assert filters_schema["type"] == "object"
    assert filters_schema["properties"]["min_stars"]["type"] == "integer"
    assert filters_schema["properties"]["labels"] == {"type": "array", "items": {"type": "string"}}
    assert filters_schema["required"] == ["min_stars", "labels"]


def test_fingerprint_is_deterministic_and_order_independent():
    fp1 = tool_schema_fingerprint([SEARCH_ISSUES, CALCULATE_SUM, CREATE_COMMENT])
    fp2 = tool_schema_fingerprint([CREATE_COMMENT, SEARCH_ISSUES, CALCULATE_SUM])
    assert fp1 == fp2
    assert len(fp1) == 64  # sha256 hex digest


def test_fingerprint_changes_if_a_tool_changes():
    fp_before = tool_schema_fingerprint([SEARCH_ISSUES])
    changed = SEARCH_ISSUES.model_copy(update={"description": "A different description."})
    fp_after = tool_schema_fingerprint([changed])
    assert fp_before != fp_after
