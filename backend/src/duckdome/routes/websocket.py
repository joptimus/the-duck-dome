"""WebSocket endpoint for real-time event broadcasting.

This replaces the legacy ``/ws`` endpoint in
agentchattr/apps/server/src/app.py (lines 1274-1673).

Differences from legacy behavior:
- No authentication on connect (legacy checked session tokens).
- No initial state dump on connect (settings, agents, history).
  The frontend fetches initial state via REST, then receives live updates.
- No inbound command handling (legacy parsed client messages for
  typing indicators, channel switches, etc.).
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from duckdome.ws.manager import ConnectionManager

router = APIRouter()

_manager: ConnectionManager | None = None


def init(manager: ConnectionManager) -> None:
    global _manager
    _manager = manager


def _get_manager() -> ConnectionManager:
    assert _manager is not None
    return _manager


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    manager = _get_manager()
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive
    except WebSocketDisconnect:
        manager.disconnect(websocket)
