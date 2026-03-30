"""Tests for MCP HTTP transport setup."""

import os
from unittest.mock import patch, MagicMock

import pytest

pytest.importorskip("mcp")

from duckdome.mcp.transport import get_mcp_port, run_mcp_server
from duckdome.mcp.bridge import McpBridge
from duckdome.services.message_service import MessageService
from duckdome.stores.message_store import MessageStore


def test_default_port():
    with patch.dict(os.environ, {}, clear=True):
        assert get_mcp_port() == 8200


def test_custom_port():
    with patch.dict(os.environ, {"DUCKDOME_MCP_PORT": "9000"}):
        assert get_mcp_port() == 9000


def test_invalid_port_falls_back_to_default():
    with patch.dict(os.environ, {"DUCKDOME_MCP_PORT": "abc"}):
        assert get_mcp_port() == 8200


def test_port_out_of_range_high():
    with patch.dict(os.environ, {"DUCKDOME_MCP_PORT": "70000"}):
        assert get_mcp_port() == 8200


def test_port_out_of_range_zero():
    with patch.dict(os.environ, {"DUCKDOME_MCP_PORT": "0"}):
        assert get_mcp_port() == 8200


def test_bridge_creates_streamable_http_app(tmp_path):
    store = MessageStore(data_dir=tmp_path)
    svc = MessageService(store=store, known_agents=["claude"])
    bridge = McpBridge(message_service=svc, trigger_service=MagicMock())
    mcp_app = bridge.mcp.streamable_http_app()
    assert mcp_app is not None
    assert callable(mcp_app)


@patch("duckdome.mcp.transport.uvicorn")
def test_run_mcp_server_calls_uvicorn(mock_uvicorn, tmp_path):
    store = MessageStore(data_dir=tmp_path)
    svc = MessageService(store=store, known_agents=["claude"])
    bridge = McpBridge(message_service=svc, trigger_service=MagicMock())

    with patch.dict(os.environ, {"DUCKDOME_MCP_PORT": "9999"}):
        run_mcp_server(bridge, host="0.0.0.0")

    mock_uvicorn.run.assert_called_once()
    call_kwargs = mock_uvicorn.run.call_args
    assert call_kwargs[1]["host"] == "0.0.0.0"
    assert call_kwargs[1]["port"] == 9999
    assert call_kwargs[1]["log_level"] == "warning"


@patch("duckdome.mcp.transport.uvicorn")
def test_run_mcp_server_handles_port_conflict(mock_uvicorn, tmp_path):
    store = MessageStore(data_dir=tmp_path)
    svc = MessageService(store=store, known_agents=["claude"])
    bridge = McpBridge(message_service=svc, trigger_service=MagicMock())

    mock_uvicorn.run.side_effect = OSError("Address already in use")
    # Should not raise — error is logged
    run_mcp_server(bridge)
