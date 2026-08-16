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
