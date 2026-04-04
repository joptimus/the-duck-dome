from __future__ import annotations

from duckdome.mcp.identity import SessionIdentityStore


def test_identity_store_default_session():
    store = SessionIdentityStore()

    identity = store.set(None, channel="channel-1", agent_type="claude")
    assert identity.channel == "channel-1"
    assert identity.agent_type == "claude"

    loaded = store.get_by_agent("claude", "channel-1")
    assert loaded is not None
    assert loaded.channel == "channel-1"
    assert loaded.agent_type == "claude"


def test_identity_store_isolated_by_session_id():
    store = SessionIdentityStore()

    store.set(None, channel="channel-a", agent_type="claude")
    store.set(None, channel="channel-b", agent_type="codex")

    one = store.get_by_agent("claude", "channel-a")
    two = store.get_by_agent("codex", "channel-b")

    assert one is not None
    assert two is not None
    assert one.channel == "channel-a"
    assert one.agent_type == "claude"
    assert two.channel == "channel-b"
    assert two.agent_type == "codex"
