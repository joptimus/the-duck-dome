import pytest
from duckdome.models.trigger import Trigger, TriggerStatus


def test_trigger_defaults():
    t = Trigger(
        channel_id="ch-1",
        target_agent_type="claude",
        source_message_id="msg-1",
    )
    assert t.id is not None
    assert t.status == TriggerStatus.PENDING
    assert t.target_agent_instance_id == "ch-1:claude"
    assert t.dedupe_key == "ch-1:claude:msg-1"
    assert t.created_at is not None
    assert t.claimed_at is None
    assert t.completed_at is None
    assert t.last_error is None


def test_trigger_serialization_roundtrip():
    t = Trigger(
        channel_id="ch-1",
        target_agent_type="claude",
        source_message_id="msg-1",
    )
    data = t.model_dump()
    restored = Trigger(**data)
    assert restored.id == t.id
    assert restored.dedupe_key == t.dedupe_key
    assert restored.target_agent_instance_id == t.target_agent_instance_id


def test_dedupe_key_deterministic():
    t1 = Trigger(
        channel_id="ch-1",
        target_agent_type="claude",
        source_message_id="msg-1",
    )
    t2 = Trigger(
        channel_id="ch-1",
        target_agent_type="claude",
        source_message_id="msg-1",
    )
    assert t1.dedupe_key == t2.dedupe_key


def test_different_channels_different_dedupe():
    t1 = Trigger(
        channel_id="ch-1",
        target_agent_type="claude",
        source_message_id="msg-1",
    )
    t2 = Trigger(
        channel_id="ch-2",
        target_agent_type="claude",
        source_message_id="msg-1",
    )
    assert t1.dedupe_key != t2.dedupe_key
