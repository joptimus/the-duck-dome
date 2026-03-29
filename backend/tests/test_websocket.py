"""Tests for WebSocket endpoint and ConnectionManager."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from duckdome.ws.manager import ConnectionManager


# --- ConnectionManager unit tests ---


@pytest.mark.anyio
async def test_manager_connect_and_disconnect():
    manager = ConnectionManager()
    assert manager.active_connections == 0

    class FakeWS:
        accepted = False

        async def accept(self):
            self.accepted = True

    ws = FakeWS()
    await manager.connect(ws)
    assert ws.accepted
    assert manager.active_connections == 1

    manager.disconnect(ws)
    assert manager.active_connections == 0


@pytest.mark.anyio
async def test_manager_disconnect_unknown_is_safe():
    manager = ConnectionManager()

    class FakeWS:
        async def accept(self):
            pass

    # Disconnecting a ws that was never connected should not raise
    manager.disconnect(FakeWS())
    assert manager.active_connections == 0


@pytest.mark.anyio
async def test_manager_broadcast():
    manager = ConnectionManager()
    received: list[str] = []

    class FakeWS:
        async def accept(self):
            pass

        async def send_text(self, data: str):
            received.append(data)

    ws1 = FakeWS()
    ws2 = FakeWS()
    await manager.connect(ws1)
    await manager.connect(ws2)

    await manager.broadcast({"type": "test", "value": 42})

    assert len(received) == 2
    parsed = json.loads(received[0])
    assert parsed == {"type": "test", "value": 42}
    assert received[0] == received[1]


@pytest.mark.anyio
async def test_manager_broadcast_removes_dead_connections():
    manager = ConnectionManager()
    received: list[str] = []

    class GoodWS:
        async def accept(self):
            pass

        async def send_text(self, data: str):
            received.append(data)

    class DeadWS:
        async def accept(self):
            pass

        async def send_text(self, data: str):
            raise ConnectionError("gone")

    good = GoodWS()
    dead = DeadWS()
    await manager.connect(good)
    await manager.connect(dead)
    assert manager.active_connections == 2

    await manager.broadcast({"type": "ping"})

    # Dead connection should have been pruned
    assert manager.active_connections == 1
    assert len(received) == 1


# --- WebSocket endpoint integration tests ---


def test_ws_connect_and_receive(app):
    """Client can connect to /ws and the connection stays open."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            # Connection is open — send a keep-alive and it doesn't crash
            ws.send_text("ping")


def _create_channel(client: TestClient) -> str:
    """Create a general channel and return its ID."""
    r = client.post(
        "/api/channels",
        json={"name": "general", "type": "general"},
    )
    return r.json()["id"]


def test_ws_receives_broadcast_on_message_send(app):
    """Sending a message via REST broadcasts new_message over WebSocket."""
    with TestClient(app) as client:
        ch_id = _create_channel(client)

        with client.websocket_connect("/ws") as ws:
            # Send a message via REST
            resp = client.post(
                "/api/messages",
                json={
                    "text": "hello from test",
                    "channel": ch_id,
                    "sender": "human",
                },
            )
            assert resp.status_code == 201

            # WebSocket should receive the broadcast
            data = ws.receive_json()
            assert data["type"] == "new_message"
            assert data["message"]["text"] == "hello from test"
            assert data["message"]["sender"] == "human"
            assert data["message"]["channel"] == ch_id


def test_ws_multiple_clients_receive_broadcast(app):
    """Multiple WebSocket clients all receive the same broadcast."""
    with TestClient(app) as client:
        ch_id = _create_channel(client)

        with client.websocket_connect("/ws") as ws1:
            with client.websocket_connect("/ws") as ws2:
                client.post(
                    "/api/messages",
                    json={
                        "text": "broadcast test",
                        "channel": ch_id,
                        "sender": "human",
                    },
                )

                data1 = ws1.receive_json()
                data2 = ws2.receive_json()
                assert data1["type"] == "new_message"
                assert data2["type"] == "new_message"
                assert data1["message"]["text"] == "broadcast test"
                assert data2["message"]["text"] == "broadcast test"
