"""MCP session identity tracking.

This feature replaces legacy MCP identity claim behavior from
``agentchattr/apps/server/src/mcp_bridge.py:chat_claim``.

Differences from legacy behavior:
- Uses a simple session-bound identity set by ``chat_join``.
- No multi-instance reclaim flow in this PR.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class AgentIdentity:
    channel: str
    agent_type: str


class SessionIdentityStore:
    """Tracks agent identity per MCP session."""

    def __init__(self) -> None:
        self._identity_by_session: dict[str, AgentIdentity] = {}
        self._lock = Lock()

    def _session_key(self, ctx: Any | None) -> str:
        if ctx is None:
            return "__default__"

        candidates = [
            getattr(ctx, "session_id", None),
            getattr(ctx, "session", None),
            getattr(ctx, "client_id", None),
        ]
        request_ctx = getattr(ctx, "request_context", None)
        if request_ctx is not None:
            candidates.extend(
                [
                    getattr(request_ctx, "session_id", None),
                    getattr(request_ctx, "session", None),
                ]
            )

        for candidate in candidates:
            if candidate is None:
                continue
            value = str(candidate).strip()
            if value:
                return value

        return f"ctx:{id(ctx)}"

    def set(self, ctx: Any | None, channel: str, agent_type: str) -> AgentIdentity:
        identity = AgentIdentity(channel=channel, agent_type=agent_type)
        key = self._session_key(ctx)
        with self._lock:
            self._identity_by_session[key] = identity
        return identity

    def get(self, ctx: Any | None) -> AgentIdentity | None:
        key = self._session_key(ctx)
        with self._lock:
            return self._identity_by_session.get(key)
