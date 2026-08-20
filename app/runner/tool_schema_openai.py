"""Translates MCP tool schemas (``ToolDefinition``) into OpenAI Responses API
function-tool definitions.

Kept isolated here, used only by ``OpenAIResponsesAdapter``, so no
OpenAI-specific shape leaks into MCP transport, discovery, the runner, or
evaluators.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.models.tools import ToolDefinition

# Internal, harness-only argument injected by BenchmarkRunner itself (see
# app/runner/engine.py's `{**decision.arguments, "failure_mode": ...}`) to
# deterministically trigger fault injection in the mock MCP server. It must
# never be exposed to a real model: doing so would leak the deterministic
# test harness's fault-injection mechanism to a live model — and the runner
# overwrites whatever value a decision supplies unconditionally anyway, so a
# model could never meaningfully use it even if it saw it.
_HARNESS_ONLY_PROPERTIES = frozenset({"failure_mode"})


class ToolSchemaTranslationError(ValueError):
    """Raised when a tool's schema cannot be losslessly translated to a
    strict OpenAI function-tool schema without changing argument semantics."""


def translate_tool_for_openai(tool: ToolDefinition) -> dict[str, Any]:
    """Build one OpenAI Responses API function-tool definition for an MCP tool.

    Uses strict mode (``strict: true``), which requires every property to be
    listed in ``required`` and ``additionalProperties: false``. Every tool in
    this project (after stripping the harness-only ``failure_mode``
    property) already has every remaining property required, so strict mode
    applies losslessly here: no optional argument is made falsely required,
    and no required argument is loosened — see
    ``tests/unit/test_tool_schema_openai.py`` for a mechanical check against
    the real mock server's discovered schemas.

    If a future tool genuinely has an optional (non-required) argument, this
    raises ``ToolSchemaTranslationError`` rather than silently misrepresenting
    it as required (or silently dropping strict mode, which would change
    argument-validation behavior a model could exploit) — Phase 2C only
    implements the lossless required-only case; extending it is future work.
    """
    schema = tool.input_schema
    properties = {
        name: value
        for name, value in schema.get("properties", {}).items()
        if name not in _HARNESS_ONLY_PROPERTIES
    }
    required = [name for name in schema.get("required", []) if name not in _HARNESS_ONLY_PROPERTIES]

    if set(properties) != set(required):
        optional = sorted(set(properties) - set(required))
        raise ToolSchemaTranslationError(
            f"Tool '{tool.name}' has optional (non-required) argument(s) {optional}; "
            "translate_tool_for_openai only supports tools where every "
            "argument is required, to avoid silently altering valid/invalid "
            "argument semantics for strict mode."
        )

    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
        "strict": True,
    }


def translate_tools_for_openai(tools: list[ToolDefinition]) -> list[dict[str, Any]]:
    return [translate_tool_for_openai(tool) for tool in tools]


def tool_schema_fingerprint(tools: list[ToolDefinition]) -> str:
    """A deterministic SHA-256 fingerprint of the translated tool schemas,
    persisted in ``ModelRunProvenance.tool_schema_hash`` so a live run's
    exact tool surface is auditable alongside the model and policy that
    produced it."""
    translated = translate_tools_for_openai(sorted(tools, key=lambda t: t.name))
    canonical = json.dumps(translated, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
