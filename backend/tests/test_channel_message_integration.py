import pytest
from duckdome.services.channel_service import ChannelService
from duckdome.services.message_service import MessageService
from duckdome.stores.channel_store import ChannelStore
from duckdome.stores.message_store import MessageStore


@pytest.fixture
def stores(tmp_path):
    return MessageStore(data_dir=tmp_path), ChannelStore(data_dir=tmp_path)


@pytest.fixture
def channel_service(stores):
    _, channel_store = stores
    return ChannelService(store=channel_store)


@pytest.fixture
def message_service(stores, channel_service):
    message_store, _ = stores
    return MessageService(
        store=message_store,
        known_agents=["claude", "codex", "gemini"],
        channel_service=channel_service,
    )


def test_send_to_valid_channel(message_service, channel_service):
    ch = channel_service.create_channel(name="general", type="general")
    channel_service.add_agent(channel_id=ch.id, agent_type="claude")
    msg = message_service.send(text="hello", channel=ch.id, sender="human")
    assert msg.channel == ch.id


def test_send_to_invalid_channel_raises(message_service):
    with pytest.raises(ValueError, match="Invalid channel"):
        message_service.send(text="hello", channel="nonexistent", sender="human")


def test_mention_resolves_only_channel_agents(message_service, channel_service):
    ch = channel_service.create_channel(name="general", type="general")
    channel_service.add_agent(channel_id=ch.id, agent_type="claude")
    # codex is NOT added to this channel
    msg = message_service.send(
        text="@claude @codex review this", channel=ch.id, sender="human"
    )
    # Only claude should be targeted
    assert msg.delivery is not None
    assert msg.delivery.target == "claude"
    assert msg.deliveries == []


def test_mention_with_all_channel_agents(message_service, channel_service):
    ch = channel_service.create_channel(name="general", type="general")
    channel_service.add_agent(channel_id=ch.id, agent_type="claude")
    channel_service.add_agent(channel_id=ch.id, agent_type="codex")
    msg = message_service.send(
        text="@claude @codex review this", channel=ch.id, sender="human"
    )
    assert msg.delivery is None
    assert len(msg.deliveries) == 2


def test_no_cross_channel_routing(message_service, channel_service):
    ch1 = channel_service.create_channel(name="channel-a", type="general")
    ch2 = channel_service.create_channel(name="channel-b", type="general")
    channel_service.add_agent(channel_id=ch1.id, agent_type="claude")
    channel_service.add_agent(channel_id=ch2.id, agent_type="codex")

    # Mention codex in ch1 — codex is not in ch1
    msg = message_service.send(
        text="@codex help", channel=ch1.id, sender="human"
    )
    assert msg.delivery is None
    assert msg.deliveries == []
