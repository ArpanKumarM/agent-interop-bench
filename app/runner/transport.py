"""Transport abstraction between the runner and an MCP server.

Phase 1 ships a stdio subprocess transport, matching the standard local MCP
client-server pattern: no ports or service discovery, a clean server process
per run, and easy control over failure injection. The abstract base class
keeps discovery/runner/evaluators transport-agnostic so a Streamable HTTP
transport can be added later (for a remote mock server or a real deployment)
without touching any of those layers.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from contextlib import AsyncExitStack
from typing import Any

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel, Field

from app.discovery.mcp_discovery import discover_tools
from app.models.tools import ToolDefinition


class ToolCallOutcome(BaseModel):
    """Normalized result of calling a tool through a transport, error paths included."""

    is_error: bool
    timed_out: bool = False
    tool_not_found: bool = False
    text_output: str | None = None
    structured_output: Any | None = None
    error_message: str | None = None
    latency_ms: float = Field(default=0.0)


class MCPTransport(ABC):
    """Abstract connection to an MCP server: discover tools, call tools."""

    async def __aenter__(self) -> MCPTransport:
        await self.connect()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.close()

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...

    @abstractmethod
    async def list_tools(self) -> list[ToolDefinition]: ...

    @abstractmethod
    async def call_tool(
        self, name: str, arguments: dict[str, Any], timeout_seconds: float
    ) -> ToolCallOutcome: ...


class StdioMCPTransport(MCPTransport):
    """Runs the MCP server as a stdio subprocess for the lifetime of the transport.

    Startup, the initialize handshake, and shutdown (including killing the
    child process if it crashes, hangs, or a call times out) are all handled
    here via an ``AsyncExitStack`` so callers never need to manage the
    subprocess directly.
    """

    def __init__(self, command: str, args: list[str], env: dict[str, str] | None = None) -> None:
        self._params = StdioServerParameters(command=command, args=args, env=env)
        self._exit_stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def connect(self) -> None:
        self._exit_stack = AsyncExitStack()
        try:
            read, write = await self._exit_stack.enter_async_context(stdio_client(self._params))
            self._session = await self._exit_stack.enter_async_context(ClientSession(read, write))
            await self._session.initialize()
        except BaseException:
            await self.close()
            raise

    async def close(self) -> None:
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._session = None

    def _require_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError("Transport is not connected. Use 'async with transport:'.")
        return self._session

    async def list_tools(self) -> list[ToolDefinition]:
        return await discover_tools(self._require_session())

    async def call_tool(
        self, name: str, arguments: dict[str, Any], timeout_seconds: float
    ) -> ToolCallOutcome:
        session = self._require_session()
        started = time.perf_counter()
        try:
            with anyio.fail_after(timeout_seconds):
                result = await session.call_tool(name, arguments)
        except TimeoutError:
            latency_ms = (time.perf_counter() - started) * 1000
            return ToolCallOutcome(
                is_error=True,
                timed_out=True,
                error_message=f"Tool call '{name}' exceeded timeout of {timeout_seconds}s",
                latency_ms=latency_ms,
            )
        except Exception as exc:  # noqa: BLE001 - transport-boundary catch is intentional
            latency_ms = (time.perf_counter() - started) * 1000
            return ToolCallOutcome(
                is_error=True,
                error_message=f"{type(exc).__name__}: {exc}",
                latency_ms=latency_ms,
            )

        latency_ms = (time.perf_counter() - started) * 1000
        text_output = (
            "\n".join(
                block.text for block in result.content if getattr(block, "type", None) == "text"
            )
            or None
        )

        tool_not_found = bool(
            result.is_error and text_output and text_output.startswith("Unknown tool")
        )

        structured_output = result.structured_content
        if structured_output is None and text_output is not None and not result.is_error:
            try:
                structured_output = json.loads(text_output)
            except (json.JSONDecodeError, TypeError):
                structured_output = None

        return ToolCallOutcome(
            is_error=result.is_error,
            tool_not_found=tool_not_found,
            text_output=text_output,
            structured_output=structured_output,
            error_message=text_output if result.is_error else None,
            latency_ms=latency_ms,
        )
