"""Tests for MCP bridge — chat_send and chat_read tools."""

import json

import pytest

from duckdome.mcp.bridge import McpBridge
from duckdome.mcp.cursor_store import CursorStore
from duckdome.services.message_service import MessageService
from duckdome.stores.message_store import MessageStore


@pytest.fixture
def message_service(tmp_path):
    store = MessageStore(data_dir=tmp_path)
    return MessageService(store=store, known_agents=["claude", "codex"])


@pytest.fixture
def bridge(message_service):
    """Create a fresh McpBridge for each test."""
    return McpBridge(message_service)


@pytest.fixture
def tools(bridge):
    """Return chat_send and chat_read tool callables from the bridge."""
    tool_map = {t.name: t.fn for t in bridge.mcp._tool_manager.list_tools()}
    return tool_map["chat_send"], tool_map["chat_read"]


# --- chat_send tests ---


def test_chat_send_returns_id(tools):
    chat_send, _ = tools
    result = chat_send(text="hello world", channel="general", agent_name="claude")
    assert result.startswith("Sent (id=")


def test_chat_send_message_persisted(message_service, tools):
    chat_send, _ = tools
    chat_send(text="persisted msg", channel="general", agent_name="claude")
    msgs = message_service.list_messages("general")
    assert len(msgs) == 1
    assert msgs[0].text == "persisted msg"
    assert msgs[0].sender == "claude"
    assert msgs[0].channel == "general"


def test_chat_send_empty_text_rejected(tools):
    chat_send, _ = tools
    result = chat_send(text="   ", channel="general", agent_name="claude")
    assert "Error" in result
    assert "empty" in result.lower()


def test_chat_send_empty_channel_rejected(tools):
    chat_send, _ = tools
    result = chat_send(text="hi", channel="", agent_name="claude")
    assert "Error" in result
    assert "channel" in result.lower()


def test_chat_send_empty_agent_name_rejected(tools):
    chat_send, _ = tools
    result = chat_send(text="hi", channel="general", agent_name="")
    assert "Error" in result
    assert "agent_name" in result.lower()


def test_chat_send_strips_whitespace(message_service, tools):
    chat_send, _ = tools
    chat_send(text="  trimmed  ", channel="  general  ", agent_name="  claude  ")
    msgs = message_service.list_messages("general")
    assert len(msgs) == 1
    assert msgs[0].text == "trimmed"
    assert msgs[0].sender == "claude"


# --- chat_read tests ---


def test_chat_read_returns_messages(message_service, tools):
    _, chat_read = tools
    message_service.send(text="msg1", channel="general", sender="user")
    message_service.send(text="msg2", channel="general", sender="user")

    result = chat_read(channel="general", agent_name="claude")
    data = json.loads(result)
    assert len(data) == 2
    assert data[0]["text"] == "msg1"
    assert data[1]["text"] == "msg2"


def test_chat_read_no_messages(tools):
    _, chat_read = tools
    result = chat_read(channel="general", agent_name="claude")
    assert result == "No new messages."


def test_chat_read_cursor_advances(message_service, tools):
    _, chat_read = tools
    message_service.send(text="first", channel="general", sender="user")

    result1 = chat_read(channel="general", agent_name="claude")
    data1 = json.loads(result1)
    assert len(data1) == 1

    result2 = chat_read(channel="general", agent_name="claude")
    assert result2 == "No new messages."

    message_service.send(text="second", channel="general", sender="user")
    result3 = chat_read(channel="general", agent_name="claude")
    data3 = json.loads(result3)
    assert len(data3) == 1
    assert data3[0]["text"] == "second"


def test_chat_read_per_agent_cursors(message_service, tools):
    _, chat_read = tools
    message_service.send(text="shared msg", channel="general", sender="user")

    result_claude = chat_read(channel="general", agent_name="claude")
    data_claude = json.loads(result_claude)
    assert len(data_claude) == 1

    result_codex = chat_read(channel="general", agent_name="codex")
    data_codex = json.loads(result_codex)
    assert len(data_codex) == 1
    assert data_codex[0]["text"] == "shared msg"


def test_chat_read_per_channel_cursors(message_service, tools):
    _, chat_read = tools
    message_service.send(text="general msg", channel="general", sender="user")
    message_service.send(text="dev msg", channel="dev", sender="user")

    result1 = chat_read(channel="general", agent_name="claude")
    data1 = json.loads(result1)
    assert len(data1) == 1
    assert data1[0]["text"] == "general msg"

    result2 = chat_read(channel="dev", agent_name="claude")
    data2 = json.loads(result2)
    assert len(data2) == 1
    assert data2[0]["text"] == "dev msg"


def test_chat_read_respects_limit(message_service, tools):
    _, chat_read = tools
    for i in range(10):
        message_service.send(text=f"msg-{i}", channel="general", sender="user")

    result = chat_read(channel="general", agent_name="claude", limit=3)
    data = json.loads(result)
    assert len(data) == 3
    assert data[0]["text"] == "msg-7"
    assert data[2]["text"] == "msg-9"


def test_chat_read_limit_clamped(message_service, tools):
    _, chat_read = tools
    message_service.send(text="msg", channel="general", sender="user")
    # limit=0 should be clamped to 1
    result = chat_read(channel="general", agent_name="claude", limit=0)
    data = json.loads(result)
    assert len(data) == 1


def test_chat_read_negative_limit_clamped(message_service, tools):
    _, chat_read = tools
    message_service.send(text="msg", channel="general", sender="user")
    result = chat_read(channel="general", agent_name="claude", limit=-5)
    data = json.loads(result)
    assert len(data) == 1


def test_chat_read_empty_channel_rejected(tools):
    _, chat_read = tools
    result = chat_read(channel="", agent_name="claude")
    assert "Error" in result
    assert "channel" in result.lower()


def test_chat_read_empty_agent_name_rejected(tools):
    _, chat_read = tools
    result = chat_read(channel="general", agent_name="")
    assert "Error" in result
    assert "agent_name" in result.lower()


def test_chat_read_message_fields(message_service, tools):
    _, chat_read = tools
    message_service.send(text="field check", channel="general", sender="user")

    result = chat_read(channel="general", agent_name="claude")
    data = json.loads(result)
    msg = data[0]
    assert "id" in msg
    assert "sender" in msg
    assert "text" in msg
    assert "channel" in msg
    assert "time" in msg


# --- CursorStore unit tests ---


def test_cursor_store_get_returns_none_initially():
    store = CursorStore()
    assert store.get_cursor("claude", "general") is None


def test_cursor_store_set_and_get():
    store = CursorStore()
    store.set_cursor("claude", "general", "msg-123")
    assert store.get_cursor("claude", "general") == "msg-123"


def test_cursor_store_per_agent():
    store = CursorStore()
    store.set_cursor("claude", "general", "msg-1")
    store.set_cursor("codex", "general", "msg-2")
    assert store.get_cursor("claude", "general") == "msg-1"
    assert store.get_cursor("codex", "general") == "msg-2"


def test_cursor_store_per_channel():
    store = CursorStore()
    store.set_cursor("claude", "general", "msg-a")
    store.set_cursor("claude", "dev", "msg-b")
    assert store.get_cursor("claude", "general") == "msg-a"
    assert store.get_cursor("claude", "dev") == "msg-b"


def test_cursor_store_overwrites():
    store = CursorStore()
    store.set_cursor("claude", "general", "msg-1")
    store.set_cursor("claude", "general", "msg-2")
    assert store.get_cursor("claude", "general") == "msg-2"


# --- Integration: chat_send then chat_read ---


def test_send_then_read(message_service, tools):
    chat_send, chat_read = tools
    chat_send(text="hello from claude", channel="general", agent_name="claude")

    result = chat_read(channel="general", agent_name="codex")
    data = json.loads(result)
    assert len(data) == 1
    assert data[0]["sender"] == "claude"
    assert data[0]["text"] == "hello from claude"
