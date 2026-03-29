"""DuckDome entrypoint — starts FastAPI (REST + WebSocket) and MCP (HTTP transport).

Startup flow:
  1. FastAPI on :8000 (REST + WebSocket)
  2. MCP on :8200 (HTTP transport, in background thread)

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

from duckdome.app import create_app
from duckdome.mcp.bridge import McpBridge
from duckdome.mcp.transport import run_mcp_server

app = create_app()

# Create MCP bridge with services from the app
# Services are initialized during create_app, access them via route modules
from duckdome.routes import messages as messages_mod
from duckdome.routes import rules as rules_mod

_bridge = McpBridge(
    message_service=messages_mod._service,
    rule_service=rules_mod._service,
)

# Start MCP server in background thread
_mcp_thread = threading.Thread(
    target=run_mcp_server,
    args=(_bridge,),
    daemon=True,
)
_mcp_thread.start()
