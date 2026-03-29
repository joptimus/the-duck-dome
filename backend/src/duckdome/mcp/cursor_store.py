"""Per-agent, per-channel read cursor tracking.

Tracks each agent's last-read message ID per channel so that
chat_read returns only new messages on subsequent calls.
"""

from __future__ import annotations

import threading


class CursorStore:
    """Tracks per-agent, per-channel read position (in-memory)."""

    def __init__(self) -> None:
        self._cursors: dict[str, dict[str, str]] = {}
        self._lock = threading.Lock()

    def get_cursor(self, agent: str, channel: str) -> str | None:
        """Return the last-read message ID for this agent+channel, or None."""
        with self._lock:
            return self._cursors.get(agent, {}).get(channel)

    def set_cursor(self, agent: str, channel: str, msg_id: str) -> None:
        """Update the read cursor for this agent+channel."""
        with self._lock:
            if agent not in self._cursors:
                self._cursors[agent] = {}
            self._cursors[agent][channel] = msg_id
