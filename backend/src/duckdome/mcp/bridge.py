"""MCP bridge — exposes chat_join/chat_send/chat_read tools for agent connectivity.

This feature replaces legacy MCP identity+chat behavior from
``agentchattr/apps/server/src/mcp_bridge.py``.
Differences from legacy behavior:
  - Session identity is established by ``chat_join`` (no ``chat_claim`` reclaim flow).
  - No job-scoped reads/sends (jobs are separate).
  - No image attachments, choices, or reply_to.
  - Cursor store is in-memory only (no persistence to disk yet).
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from duckdome.mcp.cursor_store import CursorStore
from duckdome.mcp.identity import SessionIdentityStore
from duckdome.services.message_service import MessageService
from duckdome.services.trigger_service import TriggerService


class McpBridge:
    """Encapsulates MCP tools and their dependencies.

    Avoids module-level mutable globals by holding state in an instance.
    """

    def __init__(
        self,
        message_service: MessageService,
        trigger_service: TriggerService,
    ) -> None:
        self._message_service = message_service
        self._trigger_service = trigger_service
        self._cursor_store = CursorStore()
        self._identity_store = SessionIdentityStore()
        self._mcp = FastMCP("duckdome")
        self._register_tools()

    @property
    def mcp(self) -> FastMCP:
        return self._mcp

    def _register_tools(self) -> None:
        def _identity_or_error(ctx: Any | None) -> tuple[str, str] | tuple[None, str]:
            identity = self._identity_store.get(ctx)
            if identity is None:
                return None, "Error: Agent not registered. Call chat_join first."
            return identity.agent_type, identity.channel

        @self._mcp.tool()
        def chat_join(channel: str, agent_type: str, ctx: Any | None = None) -> str:
            """Register this MCP session as an agent in a channel."""
            ch = channel.strip()
            agent = agent_type.strip().lower()
            if not ch:
                return "Error: channel is required."
            if not agent:
                return "Error: agent_type is required."

            try:
                self._trigger_service.register_agent(channel_id=ch, agent_type=agent)
            except ValueError as e:
                return f"Error: {e}"
            self._identity_store.set(ctx, channel=ch, agent_type=agent)
            return f"Joined channel '{ch}' as '{agent}'."

        @self._mcp.tool()
        def chat_send(text: str, channel: str = "", ctx: Any | None = None) -> str:
            """Send a message to a channel.

            Args:
                text: The message text to send.
                channel: Optional channel override (defaults to channel from chat_join).
            """
            agent_name, joined_channel = _identity_or_error(ctx)
            if agent_name is None:
                return joined_channel

            if not text.strip():
                return "Error: empty message, not sent."
            effective_channel = channel.strip() if channel.strip() else joined_channel

            msg = self._message_service.send(
                text=text.strip(),
                channel=effective_channel,
                sender=agent_name,
            )
            return f"Sent (id={msg.id})"

        @self._mcp.tool()
        def chat_read(
            channel: str = "",
            limit: int = 20,
            ctx: Any | None = None,
        ) -> str:
            """Read recent messages from a channel. Returns messages since last read cursor.

            Args:
                channel: Optional channel override (defaults to channel from chat_join).
                limit: Maximum number of messages to return (default 20, max 100).
            """
            agent_name, joined_channel = _identity_or_error(ctx)
            if agent_name is None:
                return joined_channel

            limit = max(1, min(limit, 100))
            agent = agent_name
            ch = channel.strip() if channel.strip() else joined_channel

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
