import os
import pytest
from duckdome.models.message import Message, Delivery
from duckdome.stores.message_store import MessageStore


@pytest.fixture
def store(tmp_path):
    return MessageStore(data_dir=tmp_path)


def test_add_and_get_message(store):
    msg = Message(text="hello", channel="general", sender="human")
    store.add(msg)
    retrieved = store.get(msg.id)
    assert retrieved is not None
    assert retrieved.id == msg.id
    assert retrieved.text == "hello"


def test_get_nonexistent_returns_none(store):
    assert store.get("nonexistent") is None


def test_list_messages_by_channel(store):
    store.add(Message(text="one", channel="general", sender="human"))
    store.add(Message(text="two", channel="general", sender="human"))
    store.add(Message(text="three", channel="random", sender="human"))
    msgs = store.list_by_channel("general")
    assert len(msgs) == 2


def test_list_messages_with_after_id(store):
    m1 = Message(text="one", channel="general", sender="human")
    m2 = Message(text="two", channel="general", sender="human")
    m3 = Message(text="three", channel="general", sender="human")
    store.add(m1)
    store.add(m2)
    store.add(m3)
    msgs = store.list_by_channel("general", after_id=m1.id)
    assert len(msgs) == 2
    assert msgs[0].id == m2.id


def test_update_delivery_state(store):
    msg = Message(
        text="@claude test",
        channel="general",
        sender="human",
        delivery=Delivery(target="claude"),
    )
    store.add(msg)
    store.update(msg.id, msg)
    retrieved = store.get(msg.id)
    assert retrieved.delivery.target == "claude"


def test_persistence_across_instances(tmp_path):
    store1 = MessageStore(data_dir=tmp_path)
    msg = Message(text="persist me", channel="general", sender="human")
    store1.add(msg)

    store2 = MessageStore(data_dir=tmp_path)
    retrieved = store2.get(msg.id)
    assert retrieved is not None
    assert retrieved.text == "persist me"


def test_list_by_delivery_state(store):
    m1 = Message(
        text="@claude one",
        channel="general",
        sender="human",
        delivery=Delivery(target="claude"),
    )
    m2 = Message(text="no mention", channel="general", sender="human")
    m3 = Message(
        text="@codex two",
        channel="general",
        sender="human",
        delivery=Delivery(target="codex"),
    )
    store.add(m1)
    store.add(m2)
    store.add(m3)
    pending = store.list_by_delivery_state("sent")
    assert len(pending) == 2
    assert all(m.delivery.state == "sent" for m in pending)
