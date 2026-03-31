"""Tests for MCP proxy tool approval gating."""
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen

import pytest

from duckdome.wrapper.mcp_proxy import McpProxy, _SAFE_TOOLS
from duckdome.wrapper.safe_tools import DUCKDOME_STARTUP_SAFE_TOOLS


class _FakeMcpHandler(BaseHTTPRequestHandler):
    """Minimal fake MCP server that captures and echoes tool calls."""

    last_body: bytes = b""

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        _FakeMcpHandler.last_body = body
        # Echo back a success JSON-RPC response
        resp = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"content": [{"type": "text", "text": "ok"}]},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(resp)))
        self.end_headers()
        self.wfile.write(resp)

    def do_GET(self):
        self.send_response(200)
        self.end_headers()

    def do_DELETE(self):
        self.send_response(200)
        self.end_headers()


@pytest.fixture
def fake_mcp():
    """Start a fake upstream MCP server."""
    server = HTTPServer(("127.0.0.1", 0), _FakeMcpHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture
def proxy(fake_mcp):
    """Start a proxy pointing at the fake MCP server."""
    port = fake_mcp.server_address[1]
    p = McpProxy(
        upstream_url=f"http://127.0.0.1:{port}/mcp",
        agent_name="claude",
        app_port=9999,  # doesn't matter for safe tool tests
    )
    assert p.start()
    yield p
    p.stop()


def test_proxy_starts_and_has_port(proxy):
    assert proxy.port > 0
    assert "127.0.0.1" in proxy.url


def test_safe_tools_pass_through(proxy):
    """Safe tools (chat_send, etc.) should forward to upstream without approval."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "chat_send",
            "arguments": {"text": "hello", "sender": "test"},
        },
    }).encode()

    req = Request(
        f"{proxy.url}/mcp",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read())

    assert data["result"]["content"][0]["text"] == "ok"

    # Verify the proxy forwarded the request with the correct sender injection
    forwarded = json.loads(_FakeMcpHandler.last_body)
    assert forwarded["params"]["arguments"]["sender"] == "claude"


def test_chat_join_agent_type_injection():
    proxy = McpProxy(
        upstream_url="http://127.0.0.1:9999/mcp",
        agent_name="claude",
        app_port=9999,
    )
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "chat_join",
            "arguments": {"channel": "general", "agent_type": "wrong"},
        },
    }).encode()

    rewritten = json.loads(proxy._rewrite_tool_arguments(payload))
    assert rewritten["params"]["arguments"]["agent_type"] == "claude"


def test_chat_send_arguments_are_not_mutated():
    proxy = McpProxy(
        upstream_url="http://127.0.0.1:9999/mcp",
        agent_name="claude",
        app_port=9999,
    )
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "chat_send",
            "arguments": {"text": "hello"},
        },
    }).encode()

    rewritten = json.loads(proxy._rewrite_tool_arguments(payload))
    assert rewritten["params"]["arguments"] == {"text": "hello", "sender": "claude"}


def test_chat_read_sender_is_injected_for_legacy_compat():
    proxy = McpProxy(
        upstream_url="http://127.0.0.1:9999/mcp",
        agent_name="claude",
        app_port=9999,
    )
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "chat_read",
            "arguments": {"channel": "general"},
        },
    }).encode()

    rewritten = json.loads(proxy._rewrite_tool_arguments(payload))
    assert rewritten["params"]["arguments"]["sender"] == "claude"


def test_safe_tools_list():
    """Verify all DuckDome chat tools are in the safe list."""
    assert _SAFE_TOOLS == set(DUCKDOME_STARTUP_SAFE_TOOLS)


def test_chat_join_sets_channel_context():
    proxy = McpProxy(
        upstream_url="http://127.0.0.1:9999/mcp",
        agent_name="claude",
        app_port=9999,
    )

    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "chat_join",
            "arguments": {"channel": "channel-123", "agent_type": "claude"},
        },
    }).encode()
    proxy._extract_tool_calls(payload)
    assert proxy._get_joined_channel() == "channel-123"


def test_extract_tool_calls_falls_back_to_joined_channel():
    proxy = McpProxy(
        upstream_url="http://127.0.0.1:9999/mcp",
        agent_name="claude",
        app_port=9999,
    )
    proxy._set_joined_channel("channel-123")

    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "exec_command",
            "arguments": {"cmd": "pwd"},
        },
    }).encode()

    calls = proxy._extract_tool_calls(payload)

    assert len(calls) == 1
    assert calls[0]["channel"] == "channel-123"
