"""ConnectionManager tracks connected WebSocket clients and broadcasts events.

This replaces the legacy global ``ws_clients`` set + ``broadcast()`` helpers
in agentchattr/apps/server/src/app.py (lines 47, 1097-1115).

Differences from legacy behavior:
- Encapsulated in a class instead of module-level globals.
- Uses a list (order-preserving) instead of a set.
- Dead connections are pruned on each broadcast (same as legacy).
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import WebSocket

log = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections and broadcasts events."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._connections.append(ws)
        # Capture the event loop so sync callers can schedule broadcasts.
        if self._loop is None:
            self._loop = asyncio.get_running_loop()

    def disconnect(self, ws: WebSocket) -> None:
        try:
            self._connections.remove(ws)
        except ValueError:
            pass

    async def broadcast(self, event: dict) -> None:
        """Send *event* as JSON to every connected client.

        Silently removes connections that fail to send.
        """
        data = json.dumps(event)
        dead: list[WebSocket] = []
        for conn in list(self._connections):
            try:
                await conn.send_text(data)
            except Exception:
                dead.append(conn)
        for conn in dead:
            self.disconnect(conn)

    def broadcast_sync(self, event: dict) -> None:
        """Schedule a broadcast from synchronous code.

        Uses the event loop captured during the first WebSocket connect.
        If no event loop is available (no clients connected), the call
        is silently skipped.
        """
        if self._loop is None or self._loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(event), self._loop)

    @property
    def active_connections(self) -> int:
        return len(self._connections)
