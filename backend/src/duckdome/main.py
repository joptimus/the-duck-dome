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
import time
from contextlib import asynccontextmanager
from urllib.error import URLError
from urllib.request import Request, urlopen

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)

from fastapi import FastAPI

logger = logging.getLogger(__name__)

from duckdome.app import create_app as _create_app
from duckdome.mcp.bridge import McpBridge
from duckdome.mcp.transport import run_mcp_server


def _wait_for_mcp(port: int = 8200, timeout: float = 10.0) -> None:
    """Block until the MCP server is accepting connections."""
    import json
    deadline = time.time() + timeout
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 0, "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26", "capabilities": {},
            "clientInfo": {"name": "healthcheck", "version": "0"},
        },
    }).encode()

    while time.time() < deadline:
        try:
            req = Request(
                f"http://127.0.0.1:{port}/mcp",
                data=payload, method="POST",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            with urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    logger.info("MCP server ready on port %d", port)
                    return
        except (URLError, OSError):
            pass
        time.sleep(0.3)
    logger.warning("MCP server not ready after %.0fs — starting agents anyway", timeout)


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

    # Wait for MCP server to be ready before starting agents.
    # Claude Code connects to MCP on startup — if it fails, it marks
    # the server as "failed" and never retries.
    _wait_for_mcp(port=8200)

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
