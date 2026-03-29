import pytest
from duckdome.models.channel import Channel, ChannelType, AgentInstance
from duckdome.models.trigger import TriggerStatus
from duckdome.services.trigger_service import TriggerService
from duckdome.stores.channel_store import ChannelStore
from duckdome.stores.trigger_store import TriggerStore


@pytest.fixture
def stores(tmp_path):
    return ChannelStore(data_dir=tmp_path), TriggerStore(data_dir=tmp_path)


@pytest.fixture
def channel_store(stores):
    return stores[0]


@pytest.fixture
def service(stores):
    cs, ts = stores
    return TriggerService(trigger_store=ts, channel_store=cs)


@pytest.fixture
def channel_with_agent(channel_store):
    ch = Channel(name="general", type=ChannelType.GENERAL)
    channel_store.add_channel(ch)
    channel_store.add_agent(AgentInstance(channel_id=ch.id, agent_type="claude"))
    return ch


@pytest.fixture
def channel_with_idle_agent(channel_store):
    """Channel with an idle (claimable) agent."""
    ch = Channel(name="general", type=ChannelType.GENERAL)
    channel_store.add_channel(ch)
    channel_store.add_agent(AgentInstance(
        channel_id=ch.id, agent_type="claude", status="idle",
    ))
    return ch


# --- Trigger creation ---

def test_create_trigger(service, channel_with_agent):
    ch = channel_with_agent
    t = service.create_trigger(
        channel_id=ch.id,
        target_agent_type="claude",
        source_message_id="msg-1",
    )
    assert t.channel_id == ch.id
    assert t.target_agent_type == "claude"
    assert t.status == TriggerStatus.PENDING
    assert t.dedupe_key == f"{ch.id}:claude:msg-1"


def test_create_trigger_invalid_channel(service):
    with pytest.raises(ValueError, match="Channel not found"):
        service.create_trigger(
            channel_id="nonexistent",
            target_agent_type="claude",
            source_message_id="msg-1",
        )


def test_create_trigger_unregistered_agent(service, channel_store):
    ch = Channel(name="general", type=ChannelType.GENERAL)
    channel_store.add_channel(ch)
    with pytest.raises(ValueError, match="not registered"):
        service.create_trigger(
            channel_id=ch.id,
            target_agent_type="claude",
            source_message_id="msg-1",
        )


def test_dedupe_same_trigger(service, channel_with_agent):
    ch = channel_with_agent
    t1 = service.create_trigger(ch.id, "claude", "msg-1")
    t2 = service.create_trigger(ch.id, "claude", "msg-1")
    assert t1.id == t2.id


# --- Trigger claim ---

def test_claim_trigger(service, channel_with_idle_agent, channel_store):
    ch = channel_with_idle_agent
    service.create_trigger(ch.id, "claude", "msg-1")
    claimed = service.claim_trigger(ch.id, "claude")
    assert claimed is not None
    assert claimed.status == TriggerStatus.CLAIMED
    assert claimed.claimed_at is not None

    # Agent should be working
    agent = channel_store.get_agent(f"{ch.id}:claude")
    assert agent.status == "working"
    assert agent.current_task == "msg-1"


def test_claim_returns_none_when_empty(service, channel_with_agent):
    assert service.claim_trigger(channel_with_agent.id, "claude") is None


def test_claim_rejected_when_agent_offline(service, channel_with_agent, channel_store):
    ch = channel_with_agent
    service.create_trigger(ch.id, "claude", "msg-1")
    # Agent is offline by default (not registered via register_agent)
    agent = channel_store.get_agent(f"{ch.id}:claude")
    assert agent.status == "offline"
    assert service.claim_trigger(ch.id, "claude") is None


def test_claim_is_channel_scoped(service, channel_store):
    ch1 = Channel(name="ch-a", type=ChannelType.GENERAL)
    ch2 = Channel(name="ch-b", type=ChannelType.GENERAL)
    channel_store.add_channel(ch1)
    channel_store.add_channel(ch2)
    channel_store.add_agent(AgentInstance(channel_id=ch1.id, agent_type="claude", status="idle"))
    channel_store.add_agent(AgentInstance(channel_id=ch2.id, agent_type="claude", status="idle"))

    service.create_trigger(ch1.id, "claude", "msg-1")

    # ch2's claude should NOT see ch1's trigger
    assert service.claim_trigger(ch2.id, "claude") is None
    # ch1's claude should see it
    assert service.claim_trigger(ch1.id, "claude") is not None


# --- Trigger complete ---

def test_complete_trigger(service, channel_with_idle_agent, channel_store):
    ch = channel_with_idle_agent
    service.create_trigger(ch.id, "claude", "msg-1")
    claimed = service.claim_trigger(ch.id, "claude")
    completed = service.complete_trigger(claimed.id)
    assert completed.status == TriggerStatus.COMPLETED
    assert completed.completed_at is not None

    agent = channel_store.get_agent(f"{ch.id}:claude")
    assert agent.status == "idle"
    assert agent.last_response is not None
    assert agent.current_task is None


def test_complete_unclaimed_returns_none(service, channel_with_agent):
    ch = channel_with_agent
    t = service.create_trigger(ch.id, "claude", "msg-1")
    assert service.complete_trigger(t.id) is None


# --- Trigger fail ---

def test_fail_trigger(service, channel_with_idle_agent, channel_store):
    ch = channel_with_idle_agent
    service.create_trigger(ch.id, "claude", "msg-1")
    claimed = service.claim_trigger(ch.id, "claude")
    failed = service.fail_trigger(claimed.id, "agent crashed")
    assert failed.status == TriggerStatus.FAILED
    assert failed.last_error == "agent crashed"

    agent = channel_store.get_agent(f"{ch.id}:claude")
    assert agent.status == "idle"
    assert agent.last_error == "agent crashed"
    assert agent.current_task is None


# --- List triggers ---

def test_list_triggers_by_channel(service, channel_with_agent):
    ch = channel_with_agent
    service.create_trigger(ch.id, "claude", "msg-1")
    service.create_trigger(ch.id, "claude", "msg-2")
    assert len(service.list_triggers(ch.id)) == 2
    assert len(service.list_triggers(ch.id, status="pending")) == 2


# --- Agent runtime ---

def test_register_agent(service, channel_store):
    ch = Channel(name="general", type=ChannelType.GENERAL)
    channel_store.add_channel(ch)
    agent = service.register_agent(ch.id, "claude")
    assert agent.status == "idle"
    assert agent.last_heartbeat is not None


def test_register_existing_agent_updates_status(service, channel_with_agent, channel_store):
    ch = channel_with_agent
    # Manually set offline
    agent = channel_store.get_agent(f"{ch.id}:claude")
    agent.status = "offline"
    channel_store.update_agent(agent.id, agent)

    registered = service.register_agent(ch.id, "claude")
    assert registered.status == "idle"
    assert registered.last_heartbeat is not None


def test_register_invalid_channel(service):
    with pytest.raises(ValueError, match="Channel not found"):
        service.register_agent("nonexistent", "claude")


def test_heartbeat(service, channel_with_agent):
    ch = channel_with_agent
    service.register_agent(ch.id, "claude")
    result = service.heartbeat(ch.id, "claude")
    assert result is not None
    assert result.last_heartbeat is not None


def test_heartbeat_unregistered_returns_none(service, channel_with_agent):
    assert service.heartbeat(channel_with_agent.id, "codex") is None


def test_deregister_agent(service, channel_with_agent, channel_store):
    ch = channel_with_agent
    service.register_agent(ch.id, "claude")
    result = service.deregister_agent(ch.id, "claude")
    assert result.status == "offline"


def test_deregister_unregistered_returns_none(service, channel_with_agent):
    assert service.deregister_agent(channel_with_agent.id, "codex") is None
