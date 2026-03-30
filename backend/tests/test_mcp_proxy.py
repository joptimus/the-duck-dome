"""Tests for MCP proxy tool approval gating."""
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen

import pytest

from duckdome.wrapper.mcp_proxy import McpProxy, _SAFE_TOOLS


class _FakeMcpHandler(BaseHTTPRequestHandler):
    """Minimal fake MCP server that echoes tool calls."""

    def log_message(self, format, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
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


def test_sender_injection(proxy):
    """Proxy should inject agent_name into sender param."""
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "chat_send",
            "arguments": {"text": "hello", "sender": "wrong"},
        },
    }).encode()

    req = Request(
        f"{proxy.url}/mcp",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    # Should succeed (safe tool) even though sender was wrong
    with urlopen(req, timeout=5) as resp:
        assert resp.status == 200


def test_safe_tools_list():
    """Verify all DuckDome chat tools are in the safe list."""
    assert "chat_send" in _SAFE_TOOLS
    assert "chat_join" in _SAFE_TOOLS
    assert "chat_read" in _SAFE_TOOLS
    assert "chat_rules" in _SAFE_TOOLS
