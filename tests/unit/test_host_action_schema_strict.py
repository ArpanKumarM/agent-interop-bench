"""Phase 4A.3c: recursive strict-schema invariants for the host-action
function tools sent to the OpenAI Responses API.

Guards against the ``composed-live-canary-001-gpt56terra-attempt-2``
failure: a nested ``tool_arguments: {"type": "object"}`` node with no
``additionalProperties: false`` -> 8x HTTP 400 from the provider's strict
function-schema validator, 0 inference.
"""

from __future__ import annotations

from app.runner.host_action_schema_openai import (
    HOST_ACTION_TOOLS_FOR_OPENAI,
    host_action_schema_strict_violations,
    strict_schema_violations,
)

_EXPECTED_TOOL_NAMES = {"call_local_tool", "relay_to_remote", "attempt_mutating_tool", "stop"}


def _iter_object_nodes(node, path="$"):
    """Every object schema node reachable from ``node`` (for depth coverage)."""
    if not isinstance(node, dict):
        return
    if node.get("type") == "object" or "properties" in node:
        yield path, node
        for pname, pschema in node.get("properties", {}).items():
            yield from _iter_object_nodes(pschema, f"{path}.{pname}")
    for key in ("items", "not", "additionalProperties"):
        if isinstance(node.get(key), dict):
            yield from _iter_object_nodes(node[key], f"{path}.{key}")
    for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
        for i, sub in enumerate(node.get(key, []) or []):
            yield from _iter_object_nodes(sub, f"{path}.{key}[{i}]")
    for defs_key in ("$defs", "definitions"):
        for dname, dschema in (node.get(defs_key, {}) or {}).items():
            yield from _iter_object_nodes(dschema, f"{path}.{defs_key}.{dname}")


def test_all_four_host_action_tools_are_present_and_strict():
    names = {tool["name"] for tool in HOST_ACTION_TOOLS_FOR_OPENAI}
    assert names == _EXPECTED_TOOL_NAMES
    for tool in HOST_ACTION_TOOLS_FOR_OPENAI:
        assert tool.get("strict") is True, tool["name"]


def test_no_strict_schema_violations_anywhere_in_the_emitted_action_surface():
    assert host_action_schema_strict_violations() == []


def test_every_object_node_at_every_depth_is_fully_constrained():
    checked = 0
    for tool in HOST_ACTION_TOOLS_FOR_OPENAI:
        params = tool["parameters"]
        for path, node in _iter_object_nodes(params, f"${tool['name']}.parameters"):
            checked += 1
            props = node.get("properties", {})
            assert node.get("additionalProperties", None) is False, (
                f"{path}: object schema missing 'additionalProperties': false"
            )
            assert set(node.get("required", [])) == set(props), (
                f"{path}: 'required' {sorted(node.get('required', []))} != "
                f"declared properties {sorted(props)}"
            )
    # sanity: we actually walked the four top-level parameter objects
    assert checked >= 4


def test_no_unconstrained_object_or_dict_shape_remains():
    for tool in HOST_ACTION_TOOLS_FOR_OPENAI:
        for path, node in _iter_object_nodes(tool["parameters"], f"${tool['name']}.parameters"):
            if node.get("type") == "object":
                assert "properties" in node and node.get("additionalProperties") is False, (
                    f"{path}: unconstrained object/dict shape is forbidden under strict mode"
                )


def test_tool_arguments_are_carried_as_a_json_string_not_an_open_object():
    for name in ("call_local_tool", "attempt_mutating_tool"):
        (tool,) = [t for t in HOST_ACTION_TOOLS_FOR_OPENAI if t["name"] == name]
        props = tool["parameters"]["properties"]
        assert "tool_arguments" not in props, f"{name}: open 'tool_arguments' object must be gone"
        assert props["tool_arguments_json"]["type"] == "string"
        assert set(tool["parameters"]["required"]) == {"tool_name", "tool_arguments_json"}


# --- the recursive walker itself must catch the exact attempt-2 shape ------


def test_walker_flags_attempt2_style_nested_open_object():
    bad = {
        "type": "object",
        "properties": {
            "tool_name": {"type": "string"},
            "tool_arguments": {"type": "object"},  # the attempt-2 offender
        },
        "required": ["tool_name", "tool_arguments"],
        "additionalProperties": False,
    }
    violations = strict_schema_violations(bad, "$.parameters")
    assert any("tool_arguments" in v and "additionalProperties" in v for v in violations), (
        violations
    )


def test_walker_flags_optional_by_omission_at_depth():
    bad = {
        "type": "object",
        "properties": {
            "outer": {
                "type": "object",
                "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
                "required": ["a"],  # 'b' optional-by-omission
                "additionalProperties": False,
            }
        },
        "required": ["outer"],
        "additionalProperties": False,
    }
    violations = strict_schema_violations(bad)
    assert any("optional-by-omission" in v and "outer" in v for v in violations), violations


def test_walker_flags_required_naming_undeclared_property():
    bad = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "required": ["a", "ghost"],
        "additionalProperties": False,
    }
    violations = strict_schema_violations(bad)
    assert any("undeclared" in v and "ghost" in v for v in violations), violations


def test_walker_passes_a_fully_constrained_nested_schema():
    good = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "nested": {
                "type": "object",
                "properties": {"x": {"type": "integer"}},
                "required": ["x"],
                "additionalProperties": False,
            },
        },
        "required": ["name", "nested"],
        "additionalProperties": False,
    }
    assert strict_schema_violations(good) == []
