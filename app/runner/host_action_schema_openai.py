"""The fixed OpenAI Responses API function-tool schema for the host agent's
own action space (Phase 4A.2).

Deliberately NOT a reuse of ``app.runner.tool_schema_openai`` (which
translates arbitrary, per-case MCP ``ToolDefinition``s): the host's action
space is a small, fixed set of exactly four actions this project defines
itself (``call_local_tool``, ``relay_to_remote``, ``attempt_mutating_tool``,
``stop``) -- unrelated translation logic, so keeping it separate avoids
coupling composed's real adapter to MCP's tool-schema module.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

# The OpenAI Responses API strict function-schema validator rejects any
# object node that is not fully constrained: every object must set
# ``additionalProperties: false`` and list every declared property in
# ``required``. An open "bag of arguments" (``{"type": "object"}`` with no
# ``properties``) therefore cannot be expressed at all under strict mode --
# it is exactly what produced the 8x HTTP 400 in
# ``composed-live-canary-001-gpt56terra-attempt-2``:
#
#   Invalid schema for function 'call_local_tool': In context=
#   ('properties', 'tool_arguments'), 'additionalProperties' is required to
#   be supplied and to be false.
#
# The strict-compatible representation of an arbitrary argument mapping is a
# JSON *string* the model fills in; ``RealHostAgentAdapter`` decodes it back
# into the ``dict`` that ``HostActionSpec.tool_arguments`` has always been
# (see ``_decode_tool_arguments`` there). The semantic contract is
# unchanged: ``call_local_tool``/``attempt_mutating_tool`` still carry a
# tool name plus a free-form argument object.
_TOOL_ARGUMENTS_JSON_PROPERTY: dict[str, Any] = {
    "type": "string",
    "description": (
        "The tool's arguments encoded as a single JSON object literal, e.g. "
        '\'{"record_ref": "abc123"}\'. Must decode to a JSON object (not an '
        "array or scalar); use '{}' when the tool takes no arguments."
    ),
}

HOST_ACTION_TOOLS_FOR_OPENAI: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "call_local_tool",
        "description": "Call a local (non-mutating or mutating-but-already-known-safe) MCP tool.",
        "parameters": {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string"},
                "tool_arguments_json": _TOOL_ARGUMENTS_JSON_PROPERTY,
            },
            "required": ["tool_name", "tool_arguments_json"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "relay_to_remote",
        "description": "Send a message to the remote A2A agent.",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "content_type": {"type": "string"},
            },
            "required": ["content", "content_type"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "attempt_mutating_tool",
        "description": (
            "Attempt to call a mutating local MCP tool. You cannot grant your own "
            "approval for this: an unapproved mutating call will be blocked and will "
            "not execute, regardless of what you request."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string"},
                "tool_arguments_json": _TOOL_ARGUMENTS_JSON_PROPERTY,
            },
            "required": ["tool_name", "tool_arguments_json"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "stop",
        "description": "Stop taking further actions for this task.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def strict_schema_violations(node: Any, path: str = "$") -> list[str]:
    """Recursively check one JSON Schema fragment for OpenAI strict-mode
    object invariants at EVERY nesting depth, returning a list of
    human-readable violation strings (empty list == strict-compatible).

    For every object schema reachable from ``node`` -- including nested
    ``properties`` values, ``items``, ``$defs`` entries, and
    ``anyOf``/``oneOf``/``allOf`` branches -- this asserts:

    * ``additionalProperties`` is present and exactly ``False``
    * ``required`` lists every declared property (nothing optional-by-omission)
    * ``required`` names no property that is not declared
    * the object is not an unconstrained bag (``type: object`` with neither
      ``properties`` nor ``additionalProperties: false``)

    This is the generic invariant the OpenAI Responses API enforced by
    rejecting attempt-2's ``tool_arguments: {"type": "object"}`` node.
    """
    violations: list[str] = []
    if not isinstance(node, dict):
        return violations

    is_object = node.get("type") == "object" or "properties" in node
    if is_object:
        properties = node.get("properties", {})
        if node.get("additionalProperties", None) is not False:
            violations.append(
                f"{path}: object schema must set 'additionalProperties': false "
                f"(got {node.get('additionalProperties', '<missing>')!r})"
            )
        required = node.get("required", [])
        optional_by_omission = sorted(p for p in properties if p not in required)
        if optional_by_omission:
            violations.append(
                f"{path}: properties absent from 'required' (optional-by-omission "
                f"is forbidden under strict mode): {optional_by_omission}"
            )
        undeclared_required = sorted(r for r in required if r not in properties)
        if undeclared_required:
            violations.append(
                f"{path}: 'required' names undeclared properties: {undeclared_required}"
            )
        for prop_name, prop_schema in properties.items():
            violations.extend(strict_schema_violations(prop_schema, f"{path}.{prop_name}"))

    for key in ("items", "not"):
        if isinstance(node.get(key), dict):
            violations.extend(strict_schema_violations(node[key], f"{path}.{key}"))
    # `additionalProperties` may itself be a schema object; only `false` is
    # strict-legal, but if a schema is supplied, still walk it.
    if isinstance(node.get("additionalProperties"), dict):
        violations.extend(
            strict_schema_violations(node["additionalProperties"], f"{path}.additionalProperties")
        )
    for key in ("anyOf", "oneOf", "allOf", "prefixItems"):
        for index, sub_schema in enumerate(node.get(key, []) or []):
            violations.extend(strict_schema_violations(sub_schema, f"{path}.{key}[{index}]"))
    for defs_key in ("$defs", "definitions"):
        for def_name, def_schema in (node.get(defs_key, {}) or {}).items():
            violations.extend(strict_schema_violations(def_schema, f"{path}.{defs_key}.{def_name}"))
    return violations


def host_action_schema_strict_violations() -> list[str]:
    """Every strict-mode violation across all four host-action tool schemas
    (empty list == the whole emitted action surface is strict-compatible)."""
    violations: list[str] = []
    for tool in HOST_ACTION_TOOLS_FOR_OPENAI:
        name = tool.get("name", "<unnamed>")
        if tool.get("strict") is not True:
            violations.append(f"${name}: tool is not declared 'strict': true")
        violations.extend(
            strict_schema_violations(tool.get("parameters", {}), f"${name}.parameters")
        )
    return violations


def host_action_schema_fingerprint() -> str:
    """A deterministic SHA-256 fingerprint of the fixed host-action schema,
    persisted in ``ComposedModelRunProvenance.tool_schema_sha256`` so a live
    run's exact action surface is auditable alongside the model/policy that
    produced it."""
    canonical = json.dumps(HOST_ACTION_TOOLS_FOR_OPENAI, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
