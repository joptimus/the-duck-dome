"""Per-agent MCP proxy with tool approval gating.

Sits between an agent CLI and the real DuckDome MCP server.
Intercepts tool calls and:
  - Auto-approves safe tools (chat_send, chat_join, chat_read, etc.)
  - Gates unknown/sensitive tools through the tool approval API
  - Injects agent identity into tool call arguments

Each agent gets its own proxy on an OS-assigned port.

Ported from agentchattr/apps/server/src/mcp_proxy.py.
"""
from __future__ import annotations

import json
import logging
import re
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from duckdome.wrapper.safe_tools import DUCKDOME_STARTUP_SAFE_TOOLS

logger = logging.getLogger(__name__)

# MCP tools and which parameter should be forced by the proxy.
# Most DuckDome chat tools use session identity from chat_join and do not take
# an explicit sender/name argument anymore.
_TOOL_IDENTITY_PARAMS: dict[str, str | None] = {
    "chat_send": "sender",
    "chat_read": "sender",
    "chat_join": "agent_type",
    "chat_claim": "sender",
    "chat_who": None,
    "chat_channels": None,
    "chat_rules": None,
}

# Tools that are always safe to execute without approval.
_SAFE_TOOLS = set(DUCKDOME_STARTUP_SAFE_TOOLS)

_APPROVAL_POLL_INTERVAL = 1.0  # seconds
_APPROVAL_TIMEOUT = 120  # seconds


def _is_benign_disconnect(exc: BaseException | None) -> bool:
    """Return True for normal client disconnects that shouldn't spam logs."""
    if isinstance(exc, (BrokenPipeError, ConnectionResetError,
                        ConnectionAbortedError, TimeoutError)):
        return True
    if isinstance(exc, OSError):
        return getattr(exc, "winerror", None) in {64, 995, 10053, 10054}
    return False


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        exc = sys.exc_info()[1]
        if _is_benign_disconnect(exc):
            return
        super().handle_error(request, client_address)


class McpProxy:
    """Local HTTP proxy that gates MCP tool calls through approval.

    Args:
        upstream_url: Full URL of the real MCP server, e.g. "http://127.0.0.1:8200/mcp"
        agent_name: Agent type identifier (e.g. "claude", "codex")
        app_port: Port of the DuckDome backend API (default 8300)
        auto_approve: If True, skip all approval checks
    """

    def __init__(
        self,
        upstream_url: str,
        agent_name: str,
        app_port: int = 8000,
        auto_approve: bool = False,
    ) -> None:
        # Split upstream_url into base + path
        # e.g. "http://127.0.0.1:8200/mcp" -> base="http://127.0.0.1:8200", path="/mcp"
        from urllib.parse import urlparse
        parsed = urlparse(upstream_url)
        self._upstream_base = f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"
        self._upstream_path = parsed.path or "/mcp"
        self._agent_name = agent_name
        self._app_port = app_port
        self._auto_approve = auto_approve
        self._server: _ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._joined_channel = "general"
        self._has_joined = False
        self._state_lock = threading.Lock()

    @property
    def port(self) -> int:
        if self._server:
            return self._server.server_address[1]
        return 0

    @property
    def url(self) -> str:
        """Base URL of the proxy (clients add /mcp themselves)."""
        return f"http://127.0.0.1:{self.port}"

    @property
    def mcp_url(self) -> str:
        """Full MCP endpoint URL through the proxy."""
        return f"{self.url}{self._upstream_path}"

    def _app_url(self, path: str) -> str:
        return f"http://127.0.0.1:{self._app_port}{path}"

    def _set_joined_channel(self, channel: str) -> None:
        normalized = str(channel).strip() or "general"
        with self._state_lock:
            self._joined_channel = normalized
            self._has_joined = True

    def _get_joined_channel(self) -> str:
        with self._state_lock:
            return self._joined_channel

    def _has_joined_channel(self) -> bool:
        with self._state_lock:
            return self._has_joined

    def _remember_channel_from_tool_args(self, tool_name: str, args: dict) -> None:
        if tool_name != "chat_join" or not isinstance(args, dict):
            return
        channel = str(args.get("channel", "")).strip()
        if channel:
            self._set_joined_channel(channel)

    def _rewrite_tool_arguments(self, raw: bytes) -> bytes:
        """Normalize tool arguments to the DuckDome MCP bridge contract."""
        if not raw:
            return raw
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return raw

        messages = data if isinstance(data, list) else [data]
        modified = False

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            if msg.get("method") != "tools/call":
                continue

            params = msg.get("params", {})
            tool_name = str(params.get("name", "")).strip()
            args = params.get("arguments", {})
            if not isinstance(args, dict):
                args = {}

            identity_key = _TOOL_IDENTITY_PARAMS.get(tool_name)
            if identity_key is not None and args.get(identity_key) != self._agent_name:
                args[identity_key] = self._agent_name
                params["arguments"] = args
                modified = True

            self._remember_channel_from_tool_args(tool_name, args)

        if modified:
            return json.dumps(data).encode("utf-8")
        return raw

    def _extract_tool_calls(self, raw: bytes) -> list[dict]:
        """Extract tool calls and attach the best-known channel context."""
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except Exception:
            return []
        messages = data if isinstance(data, list) else [data]
        result = []
        for msg in messages:
            if not isinstance(msg, dict):
                continue
            if msg.get("method") != "tools/call":
                continue
            params = msg.get("params", {}) or {}
            args = params.get("arguments", {}) or {}
            tool_name = str(params.get("name", "")).strip()
            self._remember_channel_from_tool_args(tool_name, args)
            channel = str(args.get("channel", "")).strip() or self._get_joined_channel()
            result.append({
                "id": msg.get("id"),
                "name": tool_name,
                "args": args if isinstance(args, dict) else {},
                "channel": channel,
            })
        return result

    def _requires_approval(self, tool_name: str, args: dict) -> bool:
        if self._auto_approve:
            return False
        if tool_name in _SAFE_TOOLS:
            return False
        # Unknown/future tools default to gated
        return True

    def _request_tool_approval(
        self, tool_name: str, args: dict, channel: str = "general"
    ) -> tuple[bool, str]:
        """Request approval from the backend and poll until resolved.

        Returns (approved, reason).
        """
        payload = {
            "agent": self._agent_name,
            "tool": tool_name,
            "arguments": args or {},
            "channel": channel or "general",
        }
        req = Request(
            self._app_url("/api/tool_approvals/request"),
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read() or b"{}")
        except Exception as exc:
            logger.warning("tool approval request failed for %s: %s", tool_name, exc)
            return False, "approval request failed"

        status = str(data.get("status", "")).lower()
        if status == "approved":
            return True, "policy approved"
        if status == "denied":
            return False, "policy denied"
        if status != "pending":
            return False, "invalid approval status"

        approval_id = str(data.get("approval_id", "")).strip()
        if not approval_id:
            return False, "missing approval id"

        # Poll until resolved or timeout
        deadline = time.time() + _APPROVAL_TIMEOUT
        poll_url = self._app_url(f"/api/tool_approvals/{approval_id}")
        while time.time() < deadline:
            time.sleep(_APPROVAL_POLL_INTERVAL)
            poll_req = Request(poll_url, method="GET")
            try:
                with urlopen(poll_req, timeout=8) as poll_resp:
                    item = json.loads(poll_resp.read() or b"{}")
            except Exception:
                continue

            item_status = str(item.get("status", "")).lower()
            if item_status in ("approved", "denied"):
                return item_status == "approved", item_status

        return False, "approval timeout"

    def start(self) -> bool:
        """Start the proxy server in a daemon thread. Returns True on success."""
        proxy = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # silence per-request logs

            def _upstream_url(self, path: str | None = None) -> str:
                p = path if path else self.path
                return f"{proxy._upstream_base}{p}"

            def _forward_headers(self, resp_headers):
                for key in ("Content-Type", "Mcp-Session-Id", "mcp-session-id",
                            "Cache-Control", "X-Accel-Buffering", "Connection"):
                    val = resp_headers.get(key)
                    if val:
                        self.send_header(key, val)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(length) if length else b""

                # Inject agent identity into tool calls
                body = self._maybe_inject_sender(raw)

                # Check if any tool call in the request needs approval.
                # _extract_tool_calls returns all tools/call entries in the batch.
                all_tool_calls = proxy._extract_tool_calls(body)
                calls_needing_approval = [
                    tc for tc in all_tool_calls
                    if proxy._requires_approval(tc["name"], tc["args"])
                ]
                if calls_needing_approval:
                    if len(calls_needing_approval) > 1:
                        # Can't safely partial-approve a batch with multiple gated calls.
                        self._send_jsonrpc_batch_denied(
                            all_tool_calls,
                            "batch contains multiple tool calls requiring approval",
                        )
                        return
                    tc = calls_needing_approval[0]
                    approved, reason = proxy._request_tool_approval(
                        tc["name"],
                        tc["args"],
                        channel=tc.get("channel", "general"),
                    )
                    if not approved:
                        self._send_jsonrpc_batch_denied(all_tool_calls, reason)
                        return

                # Forward to upstream
                try:
                    req = Request(self._upstream_url(), data=body, method="POST")
                    for hdr, val in self.headers.items():
                        if hdr.lower() not in ("content-length", "host"):
                            req.add_header(hdr, val)
                    resp = urlopen(req, timeout=30)
                    status = resp.status
                    resp_body = resp.read()
                    resp_headers = resp.headers
                except HTTPError as e:
                    status = e.code
                    resp_body = e.read()
                    resp_headers = e.headers
                except (URLError, OSError) as e:
                    self.send_error(502, f"Upstream error: {e}")
                    return

                self.send_response(status)
                self._forward_headers(resp_headers)
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)

            def do_GET(self):
                """Forward GET — handles streamable-http and SSE streams."""
                try:
                    req = Request(self._upstream_url(), method="GET")
                    for hdr, val in self.headers.items():
                        if hdr.lower() != "host":
                            req.add_header(hdr, val)
                    resp = urlopen(req, timeout=300)
                except HTTPError as e:
                    self.send_response(e.code)
                    self._forward_headers(e.headers)
                    body = e.read()
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    if body:
                        self.wfile.write(body)
                    return
                except BrokenPipeError:
                    return
                except (URLError, OSError) as e:
                    self.send_error(502, f"Upstream error: {e}")
                    return

                self.send_response(resp.status)
                self._forward_headers(resp.headers)
                self.end_headers()

                try:
                    for line in resp:
                        # Rewrite SSE endpoint URLs to route through proxy
                        if line.startswith(b"data:"):
                            line = self._rewrite_sse_endpoint(line)
                        self.wfile.write(line)
                        self.wfile.flush()
                except BrokenPipeError:
                    pass

            def do_DELETE(self):
                try:
                    req = Request(self._upstream_url(), method="DELETE")
                    for hdr in ("Mcp-Session-Id",):
                        val = self.headers.get(hdr)
                        if val:
                            req.add_header(hdr, val)
                    resp = urlopen(req, timeout=10)
                    self.send_response(resp.status)
                    self.end_headers()
                except Exception:
                    self.send_error(502)

            def _rewrite_sse_endpoint(self, line: bytes) -> bytes:
                """Rewrite upstream URLs in SSE data so clients POST through proxy."""
                try:
                    text = line.decode("utf-8")
                    rewritten = re.sub(
                        r"data:\s*http://127\.0\.0\.1:\d+/",
                        f"data: {proxy.url}/",
                        text,
                    )
                    return rewritten.encode("utf-8")
                except Exception:
                    return line

            def _maybe_inject_sender(self, raw: bytes) -> bytes:
                """Normalize tool calls before forwarding to the upstream MCP app."""
                return proxy._rewrite_tool_arguments(raw)

            def _send_jsonrpc_denied(self, req_id, reason: str):
                """Send a JSON-RPC error response for a single denied tool call."""
                payload = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {
                        "code": -32001,
                        "message": f"Tool call denied: {reason}",
                    },
                }
                body = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _send_jsonrpc_batch_denied(self, tool_calls: list[dict], reason: str):
                """Send JSON-RPC error responses for all calls in a denied batch."""
                errors = [
                    {
                        "jsonrpc": "2.0",
                        "id": tc.get("id"),
                        "error": {
                            "code": -32001,
                            "message": f"Tool call denied: {reason}",
                        },
                    }
                    for tc in tool_calls
                ]
                body = json.dumps(errors).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        try:
            self._server = _ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        except OSError:
            logger.error("Failed to start MCP proxy for %s", self._agent_name)
            return False

        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name=f"mcp-proxy-{self._agent_name}",
        )
        self._thread.start()
        logger.info(
            "MCP proxy for %s on port %d -> %s",
            self._agent_name, self.port, self._upstream_base,
        )
        return True

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
