"""DuckDome entrypoint — starts FastAPI (REST + WebSocket) and MCP (HTTP transport).

Startup flow:
  1. FastAPI on :8000 (REST + WebSocket)
  2. MCP on :8200 (HTTP transport, in background thread — started via lifespan)

Agent config snippet (for Claude Code ~/.claude.json):
  {
    "mcpServers": {
      "duckdome": {
        "url": "http://localhost:8200/mcp"
      }
    }
  }
"""

from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from duckdome.app import create_app as _create_app
from duckdome.mcp.bridge import McpBridge
from duckdome.mcp.transport import run_mcp_server


@asynccontextmanager
async def _lifespan(application: FastAPI):
    """Start MCP transport on app startup, not on import."""
    bridge = McpBridge(
        message_service=application.state.message_service,
        rule_service=application.state.rule_service,
    )
    mcp_thread = threading.Thread(
        target=run_mcp_server,
        args=(bridge,),
        daemon=True,
    )
    mcp_thread.start()
    yield


_base_app = _create_app()
_base_app.router.lifespan_context = _lifespan
app = _base_app
