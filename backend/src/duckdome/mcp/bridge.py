"""MCP bridge — exposes chat tools for agent connectivity.

This feature replaces legacy MCP identity+chat behavior from
``agentchattr/apps/server/src/mcp_bridge.py``.
Differences from legacy behavior:
  - Session identity is established by ``chat_join`` with a lightweight
    ``chat_claim`` compatibility alias for Claude-style workflows.
  - ``chat_join`` also accepts ``channel_id`` as a compatibility alias for
    clients that infer the REST naming convention instead of the MCP tool name.
  - No job-scoped reads/sends (jobs are separate).
  - No image attachments, choices, or reply_to.
  - Cursor store is in-memory only (no persistence to disk yet).
"""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger(__name__)

from mcp.server.fastmcp import FastMCP

from duckdome.mcp.auth import agent_auth_store, get_request_token
from duckdome.mcp.cursor_store import CursorStore
from duckdome.mcp.identity import SessionIdentityStore
from duckdome.services.message_service import MessageService
from duckdome.services.rule_service import RuleService
from duckdome.services.trigger_service import TriggerService

_MCP_INSTRUCTIONS = (
    "duckdome — a shared chat channel for coordinating development between AI agents and humans. "
    "Use chat_send to post messages. Use chat_read to check recent messages. "
    "Use chat_join when you start a session to announce your presence. "
    "When you are addressed in chat, do the work first and then reply in chat. "
    "Messages belong to channels. Read and reply in the same channel. "
    "Claude compatibility: prompts may say 'mcp read #channel - you were mentioned, take appropriate action'. "
    "Interpret that as: use DuckDome chat tools to read the channel, perform the task, and respond in chat."
)


class McpBridge:
    """Encapsulates MCP tools and their dependencies.

    Avoids module-level mutable globals by holding state in an instance.
    """

    def __init__(
        self,
        message_service: MessageService,
        trigger_service: TriggerService,
        rule_service: RuleService | None = None,
    ) -> None:
        self._message_service = message_service
        self._trigger_service = trigger_service
        self._rule_service = rule_service
        self._cursor_store = CursorStore()
        self._identity_store = SessionIdentityStore()
        self._mcp = FastMCP("duckdome", instructions=_MCP_INSTRUCTIONS)
        self._register_tools()

    @property
    def mcp(self) -> FastMCP:
        return self._mcp

    @staticmethod
    def _ctx_repr(ctx: Any | None) -> str:
        token = get_request_token()
        token_part = f" token={'set' if token else 'none'}"
        if ctx is None:
            return f"ctx=None{token_part}"
        session_id = getattr(ctx, "session_id", None)
        client_id = getattr(ctx, "client_id", None)
        if session_id or client_id:
            return f"ctx=session_id={session_id!r} client_id={client_id!r}{token_part}"
        return f"ctx={type(ctx).__name__}{token_part}"

    def _register_tools(self) -> None:
        def _identity_or_error(ctx: Any | None, channel: str = "", sender: str = "") -> tuple[str, str] | tuple[None, str]:
            """Resolve agent identity from sender, channel, or session."""
            s = sender.strip().lower()
            ch = channel.strip()
            # Try explicit sender + channel
            if s:
                identity = self._identity_store.get_by_agent(s, ch)
                if identity:
                    return identity.agent_type, ch or identity.channel
            # Try finding any agent for this channel
            if ch:
                identity = self._identity_store.find_by_channel(ch)
                if identity:
                    return identity.agent_type, identity.channel
            return None, "Error: Agent not registered. Call chat_join first."

        def _resolve_join_identity(
            *,
            channel: str,
            channel_id: str,
            agent_type: str,
            name: str,
        ) -> tuple[str | None, str | None, str | None]:
            ch = channel.strip() or channel_id.strip() or "general"
            agent = (agent_type.strip() or name.strip()).lower()
            if not agent:
                return None, None, "Error: agent_type is required."
            bound = agent_auth_store.get(get_request_token())
            if bound is not None:
                if agent != bound.agent_type:
                    return None, None, (
                        f"Error: agent_type '{agent}' does not match bound agent '{bound.agent_type}'."
                    )
                if ch != bound.channel:
                    return None, None, (
                        f"Error: channel '{ch}' does not match bound channel '{bound.channel}'."
                    )
            return ch, agent, None

        def _ensure_identity(
            *,
            ctx: Any | None,
            channel: str,
            sender: str = "",
        ) -> tuple[str | None, str | None]:
            bound = agent_auth_store.get(get_request_token())
            if bound is not None:
                requested_channel = channel.strip()
                requested_sender = sender.strip().lower()
                if requested_sender and requested_sender != bound.agent_type:
                    return None, (
                        f"Error: sender '{requested_sender}' does not match bound agent '{bound.agent_type}'."
                    )
                if requested_channel and requested_channel != bound.channel:
                    return None, (
                        f"Error: channel '{requested_channel}' does not match bound channel '{bound.channel}'."
                    )
                return bound.agent_type, bound.channel

            s = sender.strip().lower()
            ch = channel.strip()

            # 1. Explicit sender — proxy-injected (Codex) or passed directly
            if s:
                identity = self._identity_store.get_by_agent(s, ch)
                if identity is not None:
                    effective_channel = ch or identity.channel
                    return identity.agent_type, effective_channel
                # Sender known but no prior chat_join — register on the fly.
                effective_channel = ch or "general"
                try:
                    self._trigger_service.register_agent(channel_id=effective_channel, agent_type=s)
                except (ValueError, Exception):
                    log.warning("[bridge] auto-registration failed for %s in %s", s, effective_channel)
                self._identity_store.set(ctx, channel=effective_channel, agent_type=s)
                return s, effective_channel

            # 2. No sender — look up by channel (Claude direct connection)
            if ch:
                identity = self._identity_store.find_by_channel(ch)
                if identity is not None:
                    return identity.agent_type, identity.channel

            return None, "Error: Agent not registered. Call chat_join first."

        @self._mcp.tool()
        def chat_join(
            channel: str = "",
            channel_id: str = "",
            agent_type: str = "",
            name: str = "",
            ctx: Any | None = None,
        ) -> str:
            """Register this MCP session as an agent in a channel.

            Supports DuckDome style ``agent_type`` and legacy Claude style ``name``.
            Also accepts ``channel_id`` as an alias for ``channel``.
            """
            ch, agent, err = _resolve_join_identity(
                channel=channel,
                channel_id=channel_id,
                agent_type=agent_type,
                name=name,
            )
            if err:
                log.warning(
                    "[mcp] chat_join rejected: %s channel=%r channel_id=%r agent_type=%r name=%r %s",
                    err,
                    channel,
                    channel_id,
                    agent_type,
                    name,
                    self._ctx_repr(ctx),
                )
                return err

            try:
                log.info(
                    "[mcp] chat_join start channel=%s agent=%s %s",
                    ch,
                    agent,
                    self._ctx_repr(ctx),
                )
                self._trigger_service.register_agent(channel_id=ch, agent_type=agent)
            except ValueError as e:
                log.warning(
                    "[mcp] chat_join register failed: channel=%s agent=%s error=%s %s",
                    ch,
                    agent,
                    e,
                    self._ctx_repr(ctx),
                )
                return f"Error: {e}"
            self._identity_store.set(ctx, channel=ch, agent_type=agent)
            log.info(
                "[mcp] chat_join success channel=%s agent=%s %s",
                ch,
                agent,
                self._ctx_repr(ctx),
            )
            return f"Joined channel '{ch}' as '{agent}'."

        @self._mcp.tool()
        def chat_send(
            text: str = "",
            message: str = "",
            channel: str = "",
            sender: str = "",
            ctx: Any | None = None,
        ) -> str:
            """Send a message to a channel.

            Args:
                text: The message text to send.
                message: Legacy alias for text.
                channel: Optional channel override (defaults to channel from chat_join).
                sender: Legacy compatibility field for Claude/agentchattr workflows.
            """
            agent_name, effective_channel = _ensure_identity(ctx=ctx, channel=channel, sender=sender)
            if agent_name is None:
                log.warning(
                    "[mcp] chat_send rejected: %s sender=%r channel=%r %s",
                    effective_channel,
                    sender,
                    channel,
                    self._ctx_repr(ctx),
                )
                return effective_channel

            body = text.strip() or message.strip()
            if not body:
                log.warning(
                    "[mcp] chat_send empty body sender=%s channel=%s %s",
                    agent_name,
                    effective_channel,
                    self._ctx_repr(ctx),
                )
                return "Error: empty message, not sent."

            log.info(
                "[mcp] chat_send start sender=%s channel=%s text_len=%d %s",
                agent_name,
                effective_channel,
                len(body),
                self._ctx_repr(ctx),
            )
            try:
                msg = self._message_service.send(
                    text=body,
                    channel=effective_channel,
                    sender=agent_name,
                )
            except Exception:
                log.exception(
                    "[mcp] chat_send failed sender=%s channel=%s %s",
                    agent_name,
                    effective_channel,
                    self._ctx_repr(ctx),
                )
                raise
            log.info(
                "[mcp] chat_send success sender=%s channel=%s msg_id=%s %s",
                agent_name,
                effective_channel,
                msg.id,
                self._ctx_repr(ctx),
            )
            return f"Sent (id={msg.id})"

        @self._mcp.tool()
        def chat_read(
            channel: str = "",
            limit: int = 20,
            sender: str = "",
            ctx: Any | None = None,
        ) -> str:
            """Read recent messages from a channel. Returns messages since last read cursor.

            Args:
                channel: Optional channel override (defaults to channel from chat_join).
                limit: Maximum number of messages to return (default 20, max 100).
                sender: Legacy compatibility field for Claude/agentchattr workflows.
            """
            agent_name, joined_channel = _ensure_identity(ctx=ctx, channel=channel, sender=sender)
            if agent_name is None:
                log.warning(
                    "[mcp] chat_read rejected: %s sender=%r channel=%r %s",
                    joined_channel,
                    sender,
                    channel,
                    self._ctx_repr(ctx),
                )
                return joined_channel

            limit = max(1, min(limit, 100))
            agent = agent_name
            ch = joined_channel
            log.info(
                "[mcp] chat_read start agent=%s channel=%s limit=%d %s",
                agent,
                ch,
                limit,
                self._ctx_repr(ctx),
            )

            cursor = self._cursor_store.get_cursor(agent, ch)
            messages = self._message_service.list_messages(ch, after_id=cursor)
            messages = messages[-limit:]

            if not messages:
                log.info(
                    "[mcp] chat_read empty agent=%s channel=%s cursor=%r %s",
                    agent,
                    ch,
                    cursor,
                    self._ctx_repr(ctx),
                )
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

            payload = json.dumps(result, ensure_ascii=False)
            log.info(
                "[mcp] chat_read success agent=%s channel=%s cursor_before=%r last_msg=%s count=%d %s",
                agent,
                ch,
                cursor,
                last_msg.id,
                len(messages),
                self._ctx_repr(ctx),
            )
            return payload

        @self._mcp.tool()
        def chat_claim(sender: str, name: str = "", ctx: Any | None = None) -> str:
            """Legacy compatibility alias used by agentchattr-style Claude sessions."""
            chosen = (name.strip() or sender.strip()).lower()
            if not chosen:
                log.warning("[mcp] chat_claim rejected: empty sender/name %s", self._ctx_repr(ctx))
                return "Error: sender is required."
            identity = self._identity_store.get(ctx)
            channel = identity.channel if identity is not None else "general"
            self._identity_store.set(ctx, channel=channel, agent_type=chosen)
            try:
                self._trigger_service.register_agent(channel_id=channel, agent_type=chosen)
            except (ValueError, Exception):
                pass  # best-effort
            log.info(
                "[mcp] chat_claim success sender=%s channel=%s %s",
                chosen,
                channel,
                self._ctx_repr(ctx),
            )
            return json.dumps({"confirmed_name": chosen}, ensure_ascii=False)

        @self._mcp.tool()
        def chat_who() -> str:
            """List currently known agent types from channel membership."""
            agents = sorted(
                {
                    agent.agent_type
                    for channel in self._trigger_service._channels.list_channels()
                    for agent in self._trigger_service._channels.list_agents(channel.id)
                }
            )
            result = f"Online: {', '.join(agents)}" if agents else "Nobody online."
            log.info("[mcp] chat_who result=%s", result)
            return result

        @self._mcp.tool()
        def chat_channels() -> str:
            """List available channels."""
            channels = self._trigger_service._channels.list_channels()
            result = json.dumps([channel.id for channel in channels], ensure_ascii=False)
            log.info("[mcp] chat_channels count=%d", len(channels))
            return result

        @self._mcp.tool()
        def chat_rules() -> str:
            """List active rules. Agents should check and follow these."""
            if self._rule_service is None:
                log.warning("[mcp] chat_rules unavailable")
                return "Error: rules service not available."
            rules = self._rule_service.list_active()
            if not rules:
                log.info("[mcp] chat_rules empty")
                return "No active rules."
            result = []
            for rule in rules:
                result.append({
                    "id": rule.id,
                    "text": rule.text,
                    "author": rule.author,
                    "status": rule.status,
                })
            payload = json.dumps(result, ensure_ascii=False)
            log.info("[mcp] chat_rules count=%d", len(rules))
            return payload
