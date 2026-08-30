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

HOST_ACTION_TOOLS_FOR_OPENAI: list[dict[str, Any]] = [
    {
        "type": "function",
        "name": "call_local_tool",
        "description": "Call a local (non-mutating or mutating-but-already-known-safe) MCP tool.",
        "parameters": {
            "type": "object",
            "properties": {
                "tool_name": {"type": "string"},
                "tool_arguments": {"type": "object"},
            },
            "required": ["tool_name", "tool_arguments"],
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
                "tool_arguments": {"type": "object"},
            },
            "required": ["tool_name", "tool_arguments"],
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


def host_action_schema_fingerprint() -> str:
    """A deterministic SHA-256 fingerprint of the fixed host-action schema,
    persisted in ``ComposedModelRunProvenance.tool_schema_sha256`` so a live
    run's exact action surface is auditable alongside the model/policy that
    produced it."""
    canonical = json.dumps(HOST_ACTION_TOOLS_FOR_OPENAI, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
