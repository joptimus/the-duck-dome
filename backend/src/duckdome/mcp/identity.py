"""MCP session identity tracking.

Maps agent_type + channel pairs so that chat_send/chat_read can
determine which agent is calling even when the MCP framework does
not provide usable session IDs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from threading import Lock
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentIdentity:
    channel: str
    agent_type: str


class SessionIdentityStore:
    """Tracks agent identity keyed by agent_type:channel."""

    def __init__(self) -> None:
        self._identities: dict[str, AgentIdentity] = {}
        self._lock = Lock()

    def set(self, ctx: Any | None, channel: str, agent_type: str) -> AgentIdentity:
        identity = AgentIdentity(channel=channel, agent_type=agent_type)
        key = f"{agent_type.lower()}:{channel}"
        log.info("[identity] SET key=%s", key)
        with self._lock:
            self._identities[key] = identity
        return identity

    def get_by_agent(self, agent_type: str, channel: str = "") -> AgentIdentity | None:
        """Look up identity by agent_type, optionally scoped to channel."""
        at = agent_type.lower()
        with self._lock:
            if channel:
                return self._identities.get(f"{at}:{channel}")
            # No channel specified — find the first match for this agent type.
            for key, identity in self._identities.items():
                if key.startswith(f"{at}:"):
                    return identity
        return None

    def find_by_channel(self, channel: str) -> AgentIdentity | None:
        """Find any agent identity for a given channel."""
        with self._lock:
            for identity in self._identities.values():
                if identity.channel == channel:
                    return identity
        return None

    def get(self, ctx: Any | None) -> AgentIdentity | None:
        """Legacy get — returns None since ctx is always None."""
        return None
