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

import logging
import threading
from contextlib import asynccontextmanager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi import FastAPI

from duckdome.app import create_app as _create_app
from duckdome.mcp.bridge import McpBridge
from duckdome.mcp.transport import run_mcp_server


@asynccontextmanager
async def _lifespan(application: FastAPI):
    """Start MCP transport and agent processes on app startup."""
    bridge = McpBridge(
        message_service=application.state.message_service,
        trigger_service=application.state.trigger_service,
        rule_service=application.state.rule_service,
    )
    mcp_thread = threading.Thread(
        target=run_mcp_server,
        args=(bridge,),
        daemon=True,
    )
    mcp_thread.start()

    # Start persistent agent processes (skip agents not installed)
    import shutil
    wrapper_service = application.state.wrapper_service
    for agent_type in ["claude", "codex", "gemini"]:
        if shutil.which(agent_type):
            wrapper_service.start_agent(agent_type)
        else:
            logging.getLogger(__name__).info("Skipping %s: CLI not found in PATH", agent_type)

    yield

    # Cleanup
    wrapper_service.stop_all()


_base_app = _create_app()
_base_app.router.lifespan_context = _lifespan
app = _base_app
