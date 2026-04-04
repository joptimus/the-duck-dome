"""MCP HTTP transport — serves MCP bridge over HTTP for external agent connectivity.

Starts a Starlette app on a configurable port (default 8200) that serves the
MCP streamable-http transport. External agents (Claude Code, Codex, Gemini)
connect to http://localhost:8200/mcp to use chat_send, chat_read, chat_rules.

Config: DUCKDOME_MCP_PORT env var (default: 8200).
"""

from __future__ import annotations

import logging
import os
from urllib.parse import parse_qs

import uvicorn

from duckdome.mcp.auth import reset_request_token, set_request_token
from duckdome.mcp.bridge import McpBridge

logger = logging.getLogger(__name__)


class _TokenBoundMcpApp:
    def __init__(self, app) -> None:
        self._app = app

    async def __call__(self, scope, receive, send) -> None:
        token = None
        if scope.get("type") == "http":
            query = parse_qs((scope.get("query_string") or b"").decode("utf-8"))
            token = (query.get("duckdome_token") or [None])[0]
            if token is None:
                for raw_key, raw_val in scope.get("headers", []):
                    if raw_key.lower() != b"authorization":
                        continue
                    value = raw_val.decode("utf-8", errors="ignore").strip()
                    if value.lower().startswith("bearer "):
                        token = value[7:].strip()
                    break
        state = set_request_token(token)
        try:
            await self._app(scope, receive, send)
        finally:
            reset_request_token(state)


def get_mcp_port() -> int:
    raw = os.environ.get("DUCKDOME_MCP_PORT", "8200")
    try:
        port = int(raw)
    except ValueError:
        logger.warning("Invalid DUCKDOME_MCP_PORT=%r, using default 8200", raw)
        return 8200
    if not (1 <= port <= 65535):
        logger.warning("DUCKDOME_MCP_PORT=%d out of range (1-65535), using default 8200", port)
        return 8200
    return port


def run_mcp_server(bridge: McpBridge, host: str = "127.0.0.1") -> None:
    """Run the MCP HTTP transport. Blocks until shutdown.

    Intended to be called in a background thread so it doesn't block
    the main FastAPI server.
    """
    port = get_mcp_port()
    mcp_app = _TokenBoundMcpApp(bridge.mcp.streamable_http_app())
    try:
        logger.info("MCP transport starting on %s:%d", host, port)
        uvicorn.run(mcp_app, host=host, port=port, log_level="warning")
    except OSError as e:
        logger.error("MCP transport failed to start on port %d: %s", port, e)
