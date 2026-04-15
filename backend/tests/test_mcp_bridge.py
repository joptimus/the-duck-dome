"""Tests for MCP bridge tools with join-based session identity."""

from __future__ import annotations

import json

import pytest

from duckdome.mcp.auth import agent_auth_store, set_request_token, reset_request_token

pytest.importorskip("mcp.server.fastmcp")

from duckdome.mcp.bridge import McpBridge
from duckdome.mcp.cursor_store import CursorStore
from duckdome.services.channel_service import ChannelService
from duckdome.services.message_service import MessageService
from duckdome.services.trigger_service import TriggerService
from duckdome.stores.channel_store import ChannelStore
from duckdome.stores.message_store import MessageStore
from duckdome.stores.trigger_store import TriggerStore


@pytest.fixture
def stores(tmp_path):
    return (
        MessageStore(data_dir=tmp_path),
        ChannelStore(data_dir=tmp_path),
        TriggerStore(data_dir=tmp_path),
    )


@pytest.fixture
def channel_id(stores):
    _, channel_store, _ = stores
    channel_service = ChannelService(store=channel_store)
    channel = channel_service.create_channel(name="general", type="general")
    return channel.id


@pytest.fixture
def bridge(stores):
    message_store, channel_store, trigger_store = stores
    channel_service = ChannelService(store=channel_store)
    message_service = MessageService(
        store=message_store,
        known_agents=["claude", "codex"],
        channel_service=channel_service,
    )
    trigger_service = TriggerService(
        trigger_store=trigger_store,
        channel_store=channel_store,
    )
    return McpBridge(message_service=message_service, trigger_service=trigger_service)


@pytest.fixture
def tools(bridge):
    tool_map = {t.name: t.fn for t in bridge.mcp._tool_manager.list_tools()}
    return tool_map["chat_join"], tool_map["chat_send"], tool_map["chat_read"]


def test_chat_send_requires_join(tools, channel_id):
    _, chat_send, _ = tools
    result = chat_send(text="hi", channel=channel_id)
    assert result == "Error: Agent not registered. Call chat_join first."


def test_chat_read_requires_join(tools):
    _, _, chat_read = tools
    result = chat_read()
    assert result == "Error: Agent not registered. Call chat_join first."


def test_chat_join_registers_agent(tools, stores, channel_id):
    chat_join, _, _ = tools
    _, channel_store, _ = stores
    channel_service = ChannelService(store=channel_store)

    result = chat_join(channel=channel_id, agent_type="claude")
    assert result == f"Joined channel '{channel_id}' as 'claude'."
    agents = channel_service.list_agents(channel_id)
    assert [a.agent_type for a in agents] == ["claude"]


def test_chat_send_uses_joined_identity(tools, stores, channel_id):
    chat_join, chat_send, _ = tools
    message_store, _, _ = stores

    assert chat_join(channel=channel_id, agent_type="claude").startswith("Joined")
    result = chat_send(text="hello from claude")
    assert result.startswith("Sent (id=")

    messages = message_store.list_by_channel(channel_id)
    assert len(messages) == 1
    assert messages[0].sender == "claude"
    assert messages[0].text == "hello from claude"


def test_chat_read_uses_joined_identity_and_cursor(tools, stores, channel_id):
    chat_join, _, chat_read = tools
    message_store, _, _ = stores
    message_service = MessageService(store=message_store, known_agents=["claude", "codex"])

    assert chat_join(channel=channel_id, agent_type="claude").startswith("Joined")
    message_service.send(text="first", channel=channel_id, sender="human")
    message_service.send(text="second", channel=channel_id, sender="human")

    first_read = chat_read(limit=10)
    data1 = json.loads(first_read)
    assert [m["text"] for m in data1] == ["first", "second"]

    second_read = chat_read(limit=10)
    assert second_read == "No new messages."


def test_chat_read_limit_is_clamped(tools, stores, channel_id):
    chat_join, _, chat_read = tools
    message_store, _, _ = stores
    message_service = MessageService(store=message_store, known_agents=["claude", "codex"])

    assert chat_join(channel=channel_id, agent_type="claude").startswith("Joined")
    for i in range(3):
        message_service.send(text=f"msg-{i}", channel=channel_id, sender="human")

    result = chat_read(limit=0)
    data = json.loads(result)
    assert len(data) == 1
    assert data[0]["text"] == "msg-2"


def test_chat_identity_is_per_session(tools, stores, channel_id):
    chat_join, chat_send, _ = tools
    message_store, _, _ = stores

    class FakeCtx:
        def __init__(self, session_id: str):
            self.session_id = session_id

    ctx1 = FakeCtx("session-1")
    ctx2 = FakeCtx("session-2")

    assert chat_join(channel=channel_id, agent_type="claude", ctx=ctx1).startswith("Joined")
    assert chat_join(channel=channel_id, agent_type="codex", ctx=ctx2).startswith("Joined")

    assert chat_send(text="from c1", ctx=ctx1).startswith("Sent")
    assert chat_send(text="from c2", ctx=ctx2).startswith("Sent")

    messages = message_store.list_by_channel(channel_id)
    senders = [m.sender for m in messages]
    assert senders == ["claude", "codex"]


def test_cursor_store_set_and_get():
    store = CursorStore()
    assert store.get_cursor("claude", "channel-a") is None
    store.set_cursor("claude", "channel-a", "msg-1")
    assert store.get_cursor("claude", "channel-a") == "msg-1"


def test_chat_join_accepts_legacy_name_argument(bridge, stores, channel_id):
    tool_map = {t.name: t.fn for t in bridge.mcp._tool_manager.list_tools()}
    chat_join = tool_map["chat_join"]
    message_store, _, _ = stores

    assert chat_join(name="claude", channel=channel_id).startswith("Joined")
    assert tool_map["chat_send"](message="legacy hello", sender="claude").startswith("Sent")

    messages = message_store.list_by_channel(channel_id)
    assert messages[-1].text == "legacy hello"
    assert messages[-1].sender == "claude"


def test_chat_join_accepts_channel_id_alias(bridge, stores, channel_id):
    tool_map = {t.name: t.fn for t in bridge.mcp._tool_manager.list_tools()}
    chat_join = tool_map["chat_join"]
    message_store, _, _ = stores

    assert chat_join(channel_id=channel_id, agent_type="claude").startswith("Joined")
    assert tool_map["chat_send"](message="joined via channel_id", sender="claude").startswith("Sent")

    messages = message_store.list_by_channel(channel_id)
    assert messages[-1].text == "joined via channel_id"
    assert messages[-1].sender == "claude"


def test_chat_read_accepts_legacy_sender_argument(bridge, stores, channel_id):
    tool_map = {t.name: t.fn for t in bridge.mcp._tool_manager.list_tools()}
    chat_read = tool_map["chat_read"]
    message_store, _, _ = stores
    message_service = MessageService(store=message_store, known_agents=["claude", "codex"])

    message_service.send(text="legacy first", channel=channel_id, sender="human")
    message_service.send(text="legacy second", channel=channel_id, sender="human")

    result = chat_read(channel=channel_id, sender="claude", limit=10)
    data = json.loads(result)
    assert [m["text"] for m in data] == ["legacy first", "legacy second"]


def test_legacy_compat_tools_are_registered(bridge):
    tool_names = {t.name for t in bridge.mcp._tool_manager.list_tools()}
    assert "chat_claim" in tool_names
    assert "chat_who" in tool_names
    assert "chat_channels" in tool_names


def test_token_identity_wins_over_mismatched_sender(bridge, stores, channel_id):
    """When a valid token is present, it overrides a mismatched sender param."""
    message_store, channel_store, trigger_store = stores
    tool_map = {t.name: t.fn for t in bridge.mcp._tool_manager.list_tools()}
    chat_send = tool_map["chat_send"]

    token = "test-token-codex-identity"
    agent_auth_store.register(token, channel=channel_id, agent_type="codex")
    state = set_request_token(token)
    try:
        # sender says "claude" but token says "codex" — codex must win, no error
        result = chat_send(text="hello from codex", channel=channel_id, sender="claude")
        assert "Error" not in result
        assert "Sent" in result
    finally:
        agent_auth_store.unregister(token)
        reset_request_token(state)


def test_token_identity_wins_over_mismatched_channel(bridge, stores, channel_id):
    """When a valid token is present, it overrides a mismatched channel param."""
    message_store, channel_store, trigger_store = stores
    tool_map = {t.name: t.fn for t in bridge.mcp._tool_manager.list_tools()}
    chat_send = tool_map["chat_send"]

    token = "test-token-codex-channel"
    agent_auth_store.register(token, channel=channel_id, agent_type="codex")
    state = set_request_token(token)
    try:
        # channel says "other" but token says channel_id — token channel must win, no error
        result = chat_send(text="hello", channel="other", sender="codex")
        assert "Error" not in result
        assert "Sent" in result
    finally:
        agent_auth_store.unregister(token)
        reset_request_token(state)
