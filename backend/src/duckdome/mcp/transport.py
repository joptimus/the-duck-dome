"""MCP HTTP transport — serves MCP bridge over HTTP for external agent connectivity.

Starts a Starlette app on a configurable port (default 8200) that serves the
MCP streamable-http transport. External agents (Claude Code, Codex, Gemini)
connect to http://localhost:8200/mcp to use chat_send, chat_read, chat_rules.

Config: DUCKDOME_MCP_PORT env var (default: 8200).
"""

from __future__ import annotations

import logging
import os

import uvicorn

from duckdome.mcp.bridge import McpBridge

logger = logging.getLogger(__name__)


def get_mcp_port() -> int:
    raw = os.environ.get("DUCKDOME_MCP_PORT", "8200")
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid DUCKDOME_MCP_PORT=%r, using default 8200", raw)
        return 8200


def run_mcp_server(bridge: McpBridge, host: str = "127.0.0.1") -> None:
    """Run the MCP HTTP transport. Blocks until shutdown.

    Intended to be called in a background thread so it doesn't block
    the main FastAPI server.
    """
    port = get_mcp_port()
    mcp_app = bridge.mcp.streamable_http_app()
    try:
        logger.info("MCP transport starting on %s:%d", host, port)
        uvicorn.run(mcp_app, host=host, port=port, log_level="warning")
    except OSError as e:
        logger.error("MCP transport failed to start on port %d: %s", port, e)
