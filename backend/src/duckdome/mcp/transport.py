"""MCP HTTP transport — serves MCP bridge over HTTP for external agent connectivity.

Starts a Starlette app on a configurable port (default 8200) that serves the
MCP streamable-http transport. External agents (Claude Code, Codex, Gemini)
connect to http://localhost:8200/mcp to use chat_send, chat_read, chat_rules.

Config: DUCKDOME_MCP_PORT env var (default: 8200).
"""

from __future__ import annotations

import os

import uvicorn

from duckdome.mcp.bridge import McpBridge


def get_mcp_port() -> int:
    return int(os.environ.get("DUCKDOME_MCP_PORT", "8200"))


def run_mcp_server(bridge: McpBridge, host: str = "127.0.0.1") -> None:
    """Run the MCP HTTP transport. Blocks until shutdown.

    Intended to be called in a background thread so it doesn't block
    the main FastAPI server.
    """
    port = get_mcp_port()
    mcp_app = bridge.mcp.streamable_http_app()
    uvicorn.run(mcp_app, host=host, port=port, log_level="warning")
