"""Compile the ONE provider-neutral canonical host-action schema
(``app.runner.host_action_schema_openai.canonical_action_schema``) into the
Anthropic Messages API tool format (Phase 6C).

The Anthropic wire shape differs from OpenAI's:

* OpenAI (Responses): ``{"type": "function", "name", "description",
  "parameters": {<JSON schema>, "additionalProperties": false}, "strict":
  true}``
* Anthropic (Messages): ``{"name", "description", "input_schema": {<JSON
  schema>}}`` -- no ``strict`` flag, no mandatory ``additionalProperties``.

But the SEMANTICS are identical and are asserted by
``tests/unit/test_cross_provider_equivalence.py``:

* the same action names (``call_tool`` / ``relay_to_remote`` / ``stop``),
* the same required arguments in the same order,
* the same property types,
* and -- after parsing -- the SAME ``HostActionSpec`` via the shared
  ``app.runner.real_host_adapter.build_host_action_spec``.

``arguments_json`` / ``tool_arguments_json`` stay a JSON *string* on the
Anthropic wire too (decoded and validated post-parse exactly as for
OpenAI), so the two providers carry byte-identical argument semantics.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.runner.host_action_schema_openai import canonical_action_schema

__all__ = [
    "compile_canonical_actions_for_anthropic",
    "anthropic_wire_tool_schema_sha256",
]


def _to_anthropic_tool(openai_tool: dict[str, Any]) -> dict[str, Any]:
    """One canonical action -> one Anthropic ``ToolParam``. Renames
    ``parameters`` -> ``input_schema`` (the JSON-schema body --
    ``type``/``properties``/``required``/``additionalProperties: false`` --
    is carried through verbatim) and sets ``strict: true`` (Phase 6C.1):
    Anthropic then "guarantees schema validation on tool names and inputs",
    the same enforcement OpenAI's ``strict: true`` gives. The OpenAI-only
    outer ``type: "function"`` key is dropped."""
    params = dict(openai_tool.get("parameters", {}))
    return {
        "name": openai_tool["name"],
        "description": openai_tool.get("description", ""),
        "input_schema": params,
        "strict": True,
    }


def compile_canonical_actions_for_anthropic(
    canonical_actions: tuple[str, ...],
) -> list[dict[str, Any]]:
    """The Anthropic ``tools`` list for exactly ``canonical_actions`` (a
    subset of the canonical host-action surface). Order follows
    ``canonical_action_schema`` (canonical, deterministic)."""
    return [_to_anthropic_tool(tool) for tool in canonical_action_schema(canonical_actions)]


def anthropic_wire_tool_schema_sha256(canonical_actions: tuple[str, ...]) -> str:
    """Deterministic SHA-256 of the exact Anthropic wire tool schema for
    ``canonical_actions`` -- folded into the provider-config hash so a
    change to the compiled wire schema changes the execution fingerprint."""
    canonical = json.dumps(
        compile_canonical_actions_for_anthropic(canonical_actions),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
