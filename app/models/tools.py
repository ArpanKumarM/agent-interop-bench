"""Normalized representations of MCP tool definitions discovered from a server."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ToolDefinition(BaseModel):
    """A tool as discovered from an MCP server, normalized for evaluation use."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    required_arguments: list[str] = Field(default_factory=list)
    is_mutating: bool = False

    def model_visible_dump(self) -> dict[str, Any]:
        """The projection a host MODEL may see: name, neutral functional
        description, and the input schema only. ``is_mutating`` -- the
        benchmark's trusted classification -- and any other evaluation-side
        field are excluded, so a real model never receives a
        mutating/read-only signal about a tool (Phase 6B model-blindness
        rule). The host/gate reads ``is_mutating`` separately, server-side."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "required_arguments": list(self.required_arguments),
        }

    @classmethod
    def from_mcp_tool(
        cls,
        name: str,
        description: str | None,
        input_schema: dict[str, Any],
        destructive_hint: bool | None = None,
    ) -> ToolDefinition:
        required = list(input_schema.get("required", []))
        return cls(
            name=name,
            description=description or "",
            input_schema=input_schema,
            required_arguments=required,
            is_mutating=bool(destructive_hint),
        )
