import os
import pytest
from duckdome.models.channel import ChannelType
from duckdome.services.channel_service import ChannelService
from duckdome.stores.channel_store import ChannelStore


@pytest.fixture
def store(tmp_path):
    return ChannelStore(data_dir=tmp_path)


@pytest.fixture
def service(store):
    return ChannelService(store=store)


# --- Channel CRUD ---

def test_create_general_channel(service):
    ch = service.create_channel(name="planning", type="general")
    assert ch.name == "planning"
    assert ch.type == ChannelType.GENERAL
    assert ch.repo_path is None


def test_create_repo_channel(service, tmp_path):
    repo = tmp_path / "my-repo"
    repo.mkdir()
    ch = service.create_channel(name="my-repo", type="repo", repo_path=str(repo))
    assert ch.type == ChannelType.REPO
    assert ch.repo_path == str(repo)


def test_create_repo_channel_validates_path_exists(service):
    with pytest.raises(ValueError, match="does not exist"):
        service.create_channel(name="bad", type="repo", repo_path="/nonexistent/path")


def test_get_channel(service):
    ch = service.create_channel(name="general", type="general")
    retrieved = service.get_channel(ch.id)
    assert retrieved.id == ch.id


def test_list_channels(service):
    service.create_channel(name="general", type="general")
    service.create_channel(name="planning", type="general")
    assert len(service.list_channels()) == 2


# --- Agent Management ---

def test_add_agent_to_channel(service):
    ch = service.create_channel(name="general", type="general")
    inst = service.add_agent(channel_id=ch.id, agent_type="claude")
    assert inst.channel_id == ch.id
    assert inst.agent_type == "claude"
    assert inst.id == f"{ch.id}:claude"


def test_add_agent_to_nonexistent_channel(service):
    with pytest.raises(ValueError, match="Channel not found"):
        service.add_agent(channel_id="nonexistent", agent_type="claude")


def test_duplicate_agent_type_per_channel(service):
    ch = service.create_channel(name="general", type="general")
    service.add_agent(channel_id=ch.id, agent_type="claude")
    inst2 = service.add_agent(channel_id=ch.id, agent_type="claude")
    agents = service.list_agents(ch.id)
    assert len(agents) == 1
    assert agents[0].id == inst2.id


def test_same_agent_type_different_channels(service):
    ch1 = service.create_channel(name="general", type="general")
    ch2 = service.create_channel(name="planning", type="general")
    i1 = service.add_agent(channel_id=ch1.id, agent_type="claude")
    i2 = service.add_agent(channel_id=ch2.id, agent_type="claude")
    assert i1.id != i2.id
    assert len(service.list_agents(ch1.id)) == 1
    assert len(service.list_agents(ch2.id)) == 1


def test_list_agents(service):
    ch = service.create_channel(name="general", type="general")
    service.add_agent(channel_id=ch.id, agent_type="claude")
    service.add_agent(channel_id=ch.id, agent_type="codex")
    agents = service.list_agents(ch.id)
    assert len(agents) == 2


# --- Channel-aware validation ---

def test_validate_channel_exists(service):
    ch = service.create_channel(name="general", type="general")
    assert service.validate_channel(ch.id) is True


def test_validate_channel_not_exists(service):
    assert service.validate_channel("nonexistent") is False


def test_get_agents_for_channel(service):
    ch = service.create_channel(name="general", type="general")
    service.add_agent(channel_id=ch.id, agent_type="claude")
    service.add_agent(channel_id=ch.id, agent_type="codex")
    agent_types = service.get_agent_types(ch.id)
    assert set(agent_types) == {"claude", "codex"}
