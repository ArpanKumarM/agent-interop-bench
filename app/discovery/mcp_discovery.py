"""Discovers and normalizes tool definitions from a connected MCP session."""

from __future__ import annotations

from mcp import ClientSession

from app.models.tools import ToolDefinition


async def discover_tools(session: ClientSession) -> list[ToolDefinition]:
    """List tools from an already-initialized MCP client session.

    Normalizes each MCP ``Tool`` into a ``ToolDefinition`` with a required-
    arguments list derived from its JSON input schema.
    """
    result = await session.list_tools()
    return [
        ToolDefinition.from_mcp_tool(
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_schema,
            destructive_hint=tool.annotations.destructive_hint if tool.annotations else None,
        )
        for tool in result.tools
    ]
