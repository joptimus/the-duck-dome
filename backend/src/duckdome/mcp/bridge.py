"""MCP bridge — exposes chat_send and chat_read tools for agent connectivity.

This feature replaces the legacy mcp_bridge.py chat_send/chat_read tools.
Differences from legacy behavior:
  - Agent identity comes from a required agent_name parameter (no session/token auth yet).
  - No job-scoped reads/sends (jobs are a separate PR).
  - No image attachments, choices, or reply_to.
  - No multi-instance identity resolution.
  - Cursor store is in-memory only (no persistence to disk yet).
  - Empty-read escalation hints are simplified.
"""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from duckdome.mcp.cursor_store import CursorStore
from duckdome.services.message_service import MessageService


class McpBridge:
    """Encapsulates MCP tools and their dependencies.

    Avoids module-level mutable globals by holding state in an instance.
    """

    def __init__(self, message_service: MessageService) -> None:
        self._message_service = message_service
        self._cursor_store = CursorStore()
        self._mcp = FastMCP("duckdome")
        self._register_tools()

    @property
    def mcp(self) -> FastMCP:
        return self._mcp

    def _register_tools(self) -> None:
        @self._mcp.tool()
        def chat_send(text: str, channel: str, agent_name: str) -> str:
            """Send a message to a channel.

            Args:
                text: The message text to send.
                channel: The channel to send to (e.g. 'general').
                agent_name: Your agent name (e.g. 'claude', 'codex').
            """
            if not text.strip():
                return "Error: empty message, not sent."
            if not channel.strip():
                return "Error: channel is required."
            if not agent_name.strip():
                return "Error: agent_name is required."

            msg = self._message_service.send(
                text=text.strip(),
                channel=channel.strip(),
                sender=agent_name.strip(),
            )
            return f"Sent (id={msg.id})"

        @self._mcp.tool()
        def chat_read(channel: str, agent_name: str, limit: int = 20) -> str:
            """Read recent messages from a channel. Returns messages since last read cursor.

            Args:
                channel: The channel to read from (e.g. 'general').
                agent_name: Your agent name (e.g. 'claude', 'codex').
                limit: Maximum number of messages to return (default 20, max 100).
            """
            if not channel.strip():
                return "Error: channel is required."
            if not agent_name.strip():
                return "Error: agent_name is required."

            limit = max(1, min(limit, 100))
            agent = agent_name.strip()
            ch = channel.strip()

            cursor = self._cursor_store.get_cursor(agent, ch)
            messages = self._message_service.list_messages(ch, after_id=cursor)
            messages = messages[-limit:]

            if not messages:
                return "No new messages."

            # Advance cursor to last message read
            last_msg = messages[-1]
            self._cursor_store.set_cursor(agent, ch, last_msg.id)

            # Mark deliveries as seen
            self._message_service.process_agent_read(agent, ch, last_msg.id)

            # Serialize for agent consumption
            result = []
            for msg in messages:
                result.append({
                    "id": msg.id,
                    "sender": msg.sender,
                    "text": msg.text,
                    "channel": msg.channel,
                    "time": msg.timestamp,
                })

            return json.dumps(result, ensure_ascii=False)
