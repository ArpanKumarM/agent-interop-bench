"""A dedicated, local MCP tool server for the composed (cross-protocol)
suite's provenance experiments.

Deliberately separate from ``mock_servers/github_mock.py`` (the 29-case MCP
suite's server, left completely unmodified): the composed suite's
propagation case requires a tool whose RESULT independently contains a
declared provenance canary, without the canary ever being *echoed* from the
request -- unlike ``search_issues``, which simply reflects its ``query``
argument back into its output. A caller passes ``canary_name`` (a plain
label, e.g. ``"local-secret-1"``); the tool computes and embeds that
canary's actual deterministic token itself
(``app.models.composed.canary_token``), so the token exists nowhere in the
request the caller sent -- only in the response this server independently
produces.

Never contacts a real network. Run standalone for manual testing:

    uv run python -m mock_servers.composed_tool_mock
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from app.models.composed import canary_token

server = MCPServer(
    name="agent-interop-mock-composed-tool",
    version="0.1.0",
    instructions=(
        "Mock local tool server for Agent Interop Bench's composed cross-protocol "
        "provenance experiments. Local only."
    ),
)


@server.tool(
    name="get_deployment_status",
    description="Fetch deployment status for a case (composed-suite provenance fixture tool).",
)
async def get_deployment_status(case_id: str, canary_name: str | None = None) -> dict:
    """Return a deployment-status message. If ``canary_name`` is given, the
    corresponding canary token is computed and embedded here, independently
    of anything in the request -- the request never contains the token
    itself, only the canary's plain label."""
    status_text = "Deployment status: healthy."
    if canary_name is not None:
        status_text = f"{status_text} {canary_token(case_id, canary_name)}"
    return {"status": status_text}


def main() -> None:
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
