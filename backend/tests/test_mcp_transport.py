"""Tests for MCP HTTP transport setup."""

import os
from unittest.mock import patch, MagicMock

from duckdome.mcp.transport import get_mcp_port
from duckdome.mcp.bridge import McpBridge
from duckdome.services.message_service import MessageService
from duckdome.stores.message_store import MessageStore


def test_default_port():
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("DUCKDOME_MCP_PORT", None)
        assert get_mcp_port() == 8200


def test_custom_port():
    with patch.dict(os.environ, {"DUCKDOME_MCP_PORT": "9000"}):
        assert get_mcp_port() == 9000


def test_bridge_creates_streamable_http_app(tmp_path):
    store = MessageStore(data_dir=tmp_path)
    svc = MessageService(store=store, known_agents=["claude"])
    bridge = McpBridge(message_service=svc)
    mcp_app = bridge.mcp.streamable_http_app()
    # Should return a Starlette app
    assert mcp_app is not None
    assert callable(mcp_app)
