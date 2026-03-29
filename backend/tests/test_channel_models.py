import pytest
from duckdome.models.channel import Channel, ChannelType, AgentInstance


def test_general_channel():
    ch = Channel(name="planning", type=ChannelType.GENERAL)
    assert ch.id is not None
    assert ch.name == "planning"
    assert ch.type == ChannelType.GENERAL
    assert ch.repo_path is None
    assert ch.created_at is not None


def test_repo_channel():
    ch = Channel(
        name="my-app",
        type=ChannelType.REPO,
        repo_path="/Users/james/repos/my-app",
    )
    assert ch.type == ChannelType.REPO
    assert ch.repo_path == "/Users/james/repos/my-app"


def test_repo_channel_requires_repo_path():
    with pytest.raises(ValueError, match="repo_path"):
        Channel(name="bad", type=ChannelType.REPO)


def test_general_channel_rejects_repo_path():
    with pytest.raises(ValueError, match="repo_path"):
        Channel(name="bad", type=ChannelType.GENERAL, repo_path="/some/path")


def test_agent_instance():
    inst = AgentInstance(channel_id="ch-1", agent_type="claude")
    assert inst.id == "ch-1:claude"
    assert inst.status == "offline"
    assert inst.last_heartbeat is None
    assert inst.last_response is None
    assert inst.current_task is None
    assert inst.last_error is None


def test_agent_instance_serialization_roundtrip():
    inst = AgentInstance(channel_id="ch-1", agent_type="claude", status="working")
    data = inst.model_dump()
    restored = AgentInstance(**data)
    assert restored.id == "ch-1:claude"
    assert restored.status == "working"


def test_channel_serialization_roundtrip():
    ch = Channel(name="general", type=ChannelType.GENERAL)
    data = ch.model_dump()
    restored = Channel(**data)
    assert restored.id == ch.id
    assert restored.type == ChannelType.GENERAL
