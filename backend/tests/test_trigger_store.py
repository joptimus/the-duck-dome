import pytest
from duckdome.models.trigger import Trigger, TriggerStatus
from duckdome.stores.trigger_store import TriggerStore


@pytest.fixture
def store(tmp_path):
    return TriggerStore(data_dir=tmp_path)


def _make_trigger(channel_id="ch-1", agent="claude", msg_id="msg-1"):
    return Trigger(
        channel_id=channel_id,
        target_agent_type=agent,
        source_message_id=msg_id,
    )


def test_add_and_get(store):
    t = _make_trigger()
    store.add(t)
    retrieved = store.get(t.id)
    assert retrieved is not None
    assert retrieved.id == t.id


def test_get_nonexistent(store):
    assert store.get("nonexistent") is None


def test_dedupe_prevents_duplicate(store):
    t1 = _make_trigger()
    t2 = _make_trigger()  # same dedupe_key
    result1 = store.add(t1)
    result2 = store.add(t2)
    assert result1.id == result2.id  # returns existing


def test_different_agents_not_deduped(store):
    t1 = _make_trigger(agent="claude")
    t2 = _make_trigger(agent="codex")
    store.add(t1)
    store.add(t2)
    assert len(store.list_by_channel("ch-1")) == 2


def test_list_by_channel(store):
    store.add(_make_trigger(channel_id="ch-1", msg_id="m1"))
    store.add(_make_trigger(channel_id="ch-1", msg_id="m2"))
    store.add(_make_trigger(channel_id="ch-2", msg_id="m3"))
    assert len(store.list_by_channel("ch-1")) == 2
    assert len(store.list_by_channel("ch-2")) == 1


def test_list_by_channel_with_status(store):
    t = _make_trigger()
    store.add(t)
    assert len(store.list_by_channel("ch-1", status="pending")) == 1
    assert len(store.list_by_channel("ch-1", status="claimed")) == 0


def test_list_by_agent(store):
    store.add(_make_trigger(channel_id="ch-1", agent="claude", msg_id="m1"))
    store.add(_make_trigger(channel_id="ch-1", agent="codex", msg_id="m2"))
    assert len(store.list_by_agent("ch-1:claude")) == 1
    assert len(store.list_by_agent("ch-1:codex")) == 1


def test_update(store):
    t = _make_trigger()
    store.add(t)
    t.status = TriggerStatus.CLAIMED
    t.claimed_at = 1234567890.0
    store.update(t.id, t)
    retrieved = store.get(t.id)
    assert retrieved.status == TriggerStatus.CLAIMED
    assert retrieved.claimed_at == 1234567890.0


def test_update_rejects_id_mismatch(store):
    t = _make_trigger()
    store.add(t)
    other = _make_trigger(msg_id="other")
    with pytest.raises(ValueError, match="mismatch"):
        store.update(t.id, other)


def test_persistence(tmp_path):
    store1 = TriggerStore(data_dir=tmp_path)
    t = _make_trigger()
    store1.add(t)

    store2 = TriggerStore(data_dir=tmp_path)
    assert store2.get(t.id) is not None
    assert store2.find_by_dedupe_key(t.dedupe_key) is not None


def test_find_by_dedupe_key(store):
    t = _make_trigger()
    store.add(t)
    found = store.find_by_dedupe_key(t.dedupe_key)
    assert found is not None
    assert found.id == t.id
    assert store.find_by_dedupe_key("nonexistent") is None
