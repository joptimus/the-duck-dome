import pytest
from duckdome.models.channel import Channel, ChannelType, AgentInstance
from duckdome.stores.channel_store import ChannelStore


@pytest.fixture
def store(tmp_path):
    return ChannelStore(data_dir=tmp_path)


# --- Channel CRUD ---

def test_add_and_get_channel(store):
    ch = Channel(name="general", type=ChannelType.GENERAL)
    store.add_channel(ch)
    retrieved = store.get_channel(ch.id)
    assert retrieved is not None
    assert retrieved.id == ch.id
    assert retrieved.name == "general"


def test_get_nonexistent_channel(store):
    assert store.get_channel("nonexistent") is None


def test_list_channels(store, tmp_path):
    repo = tmp_path / "my-app"
    repo.mkdir()
    store.add_channel(Channel(name="general", type=ChannelType.GENERAL))
    store.add_channel(Channel(name="my-app", type=ChannelType.REPO, repo_path=str(repo)))
    channels = store.list_channels()
    assert len(channels) == 2


def test_duplicate_channel_id_is_idempotent(store):
    ch = Channel(name="general", type=ChannelType.GENERAL)
    store.add_channel(ch)
    store.add_channel(ch)
    assert len(store.list_channels()) == 1


def test_channel_persistence(tmp_path):
    store1 = ChannelStore(data_dir=tmp_path)
    ch = Channel(name="general", type=ChannelType.GENERAL)
    store1.add_channel(ch)

    store2 = ChannelStore(data_dir=tmp_path)
    assert store2.get_channel(ch.id) is not None


# --- Agent Instance CRUD ---

def test_add_and_get_agent(store):
    ch = Channel(name="general", type=ChannelType.GENERAL)
    store.add_channel(ch)
    inst = AgentInstance(channel_id=ch.id, agent_type="claude")
    store.add_agent(inst)
    retrieved = store.get_agent(inst.id)
    assert retrieved is not None
    assert retrieved.agent_type == "claude"


def test_list_agents_by_channel(store):
    ch = Channel(name="general", type=ChannelType.GENERAL)
    store.add_channel(ch)
    store.add_agent(AgentInstance(channel_id=ch.id, agent_type="claude"))
    store.add_agent(AgentInstance(channel_id=ch.id, agent_type="codex"))
    agents = store.list_agents(ch.id)
    assert len(agents) == 2
    types = {a.agent_type for a in agents}
    assert types == {"claude", "codex"}


def test_agents_do_not_cross_channels(store, tmp_path):
    repo = tmp_path / "my-app"
    repo.mkdir()
    ch1 = Channel(name="general", type=ChannelType.GENERAL)
    ch2 = Channel(name="my-app", type=ChannelType.REPO, repo_path=str(repo))
    store.add_channel(ch1)
    store.add_channel(ch2)
    store.add_agent(AgentInstance(channel_id=ch1.id, agent_type="claude"))
    store.add_agent(AgentInstance(channel_id=ch2.id, agent_type="claude"))
    assert len(store.list_agents(ch1.id)) == 1
    assert len(store.list_agents(ch2.id)) == 1
    assert store.list_agents(ch1.id)[0].id != store.list_agents(ch2.id)[0].id


def test_update_agent(store):
    ch = Channel(name="general", type=ChannelType.GENERAL)
    store.add_channel(ch)
    inst = AgentInstance(channel_id=ch.id, agent_type="claude")
    store.add_agent(inst)
    inst.status = "working"
    inst.current_task = "reviewing PR"
    store.update_agent(inst.id, inst)
    retrieved = store.get_agent(inst.id)
    assert retrieved.status == "working"
    assert retrieved.current_task == "reviewing PR"


def test_agent_persistence(tmp_path):
    store1 = ChannelStore(data_dir=tmp_path)
    ch = Channel(name="general", type=ChannelType.GENERAL)
    store1.add_channel(ch)
    store1.add_agent(AgentInstance(channel_id=ch.id, agent_type="claude"))

    store2 = ChannelStore(data_dir=tmp_path)
    assert len(store2.list_agents(ch.id)) == 1
