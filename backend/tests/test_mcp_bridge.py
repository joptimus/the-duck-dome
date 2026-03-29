"""Tests for MCP bridge — chat_send and chat_read tools."""

import json

import pytest

from duckdome.mcp.bridge import chat_send, chat_read, init, _cursor_store
from duckdome.mcp.cursor_store import CursorStore
from duckdome.services.message_service import MessageService
from duckdome.stores.message_store import MessageStore


@pytest.fixture
def message_service(tmp_path):
    store = MessageStore(data_dir=tmp_path)
    return MessageService(store=store, known_agents=["claude", "codex"])


@pytest.fixture(autouse=True)
def wire_bridge(message_service):
    """Wire the MCP bridge to a fresh message service for each test."""
    init(message_service)
    # Reset cursor store between tests
    _cursor_store._cursors.clear()
    yield


# --- chat_send tests ---


def test_chat_send_returns_id(message_service):
    result = chat_send(text="hello world", channel="general", agent_name="claude")
    assert result.startswith("Sent (id=")


def test_chat_send_message_persisted(message_service):
    chat_send(text="persisted msg", channel="general", agent_name="claude")
    msgs = message_service.list_messages("general")
    assert len(msgs) == 1
    assert msgs[0].text == "persisted msg"
    assert msgs[0].sender == "claude"
    assert msgs[0].channel == "general"


def test_chat_send_empty_text_rejected():
    result = chat_send(text="   ", channel="general", agent_name="claude")
    assert "Error" in result
    assert "empty" in result.lower()


def test_chat_send_empty_channel_rejected():
    result = chat_send(text="hi", channel="", agent_name="claude")
    assert "Error" in result
    assert "channel" in result.lower()


def test_chat_send_empty_agent_name_rejected():
    result = chat_send(text="hi", channel="general", agent_name="")
    assert "Error" in result
    assert "agent_name" in result.lower()


def test_chat_send_strips_whitespace(message_service):
    chat_send(text="  trimmed  ", channel="  general  ", agent_name="  claude  ")
    msgs = message_service.list_messages("general")
    assert len(msgs) == 1
    assert msgs[0].text == "trimmed"
    assert msgs[0].sender == "claude"


# --- chat_read tests ---


def test_chat_read_returns_messages(message_service):
    message_service.send(text="msg1", channel="general", sender="user")
    message_service.send(text="msg2", channel="general", sender="user")

    result = chat_read(channel="general", agent_name="claude")
    data = json.loads(result)
    assert len(data) == 2
    assert data[0]["text"] == "msg1"
    assert data[1]["text"] == "msg2"


def test_chat_read_no_messages():
    result = chat_read(channel="general", agent_name="claude")
    assert result == "No new messages."


def test_chat_read_cursor_advances(message_service):
    message_service.send(text="first", channel="general", sender="user")

    # First read gets the message
    result1 = chat_read(channel="general", agent_name="claude")
    data1 = json.loads(result1)
    assert len(data1) == 1

    # Second read with no new messages
    result2 = chat_read(channel="general", agent_name="claude")
    assert result2 == "No new messages."

    # New message appears
    message_service.send(text="second", channel="general", sender="user")
    result3 = chat_read(channel="general", agent_name="claude")
    data3 = json.loads(result3)
    assert len(data3) == 1
    assert data3[0]["text"] == "second"


def test_chat_read_per_agent_cursors(message_service):
    message_service.send(text="shared msg", channel="general", sender="user")

    # Claude reads
    result_claude = chat_read(channel="general", agent_name="claude")
    data_claude = json.loads(result_claude)
    assert len(data_claude) == 1

    # Codex hasn't read yet — should see the same message
    result_codex = chat_read(channel="general", agent_name="codex")
    data_codex = json.loads(result_codex)
    assert len(data_codex) == 1
    assert data_codex[0]["text"] == "shared msg"


def test_chat_read_per_channel_cursors(message_service):
    message_service.send(text="general msg", channel="general", sender="user")
    message_service.send(text="dev msg", channel="dev", sender="user")

    # Read general
    result1 = chat_read(channel="general", agent_name="claude")
    data1 = json.loads(result1)
    assert len(data1) == 1
    assert data1[0]["text"] == "general msg"

    # Dev channel should still have unread messages
    result2 = chat_read(channel="dev", agent_name="claude")
    data2 = json.loads(result2)
    assert len(data2) == 1
    assert data2[0]["text"] == "dev msg"


def test_chat_read_respects_limit(message_service):
    for i in range(10):
        message_service.send(text=f"msg-{i}", channel="general", sender="user")

    result = chat_read(channel="general", agent_name="claude", limit=3)
    data = json.loads(result)
    assert len(data) == 3
    # Should get the last 3 messages
    assert data[0]["text"] == "msg-7"
    assert data[2]["text"] == "msg-9"


def test_chat_read_empty_channel_rejected():
    result = chat_read(channel="", agent_name="claude")
    assert "Error" in result
    assert "channel" in result.lower()


def test_chat_read_empty_agent_name_rejected():
    result = chat_read(channel="general", agent_name="")
    assert "Error" in result
    assert "agent_name" in result.lower()


def test_chat_read_message_fields(message_service):
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


def test_send_then_read(message_service):
    chat_send(text="hello from claude", channel="general", agent_name="claude")

    result = chat_read(channel="general", agent_name="codex")
    data = json.loads(result)
    assert len(data) == 1
    assert data[0]["sender"] == "claude"
    assert data[0]["text"] == "hello from claude"
