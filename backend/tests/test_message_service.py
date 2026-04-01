import pytest
from duckdome.models.message import DeliveryState
from duckdome.services.message_service import MessageService
from duckdome.stores.message_store import MessageStore


@pytest.fixture
def store(tmp_path):
    return MessageStore(data_dir=tmp_path)


@pytest.fixture
def service(store):
    return MessageService(store=store, known_agents=["claude", "codex", "gemini"])


# --- Mention Detection ---

def test_send_with_single_mention(service):
    msg = service.send(text="@claude review this", channel="general", sender="human")
    assert msg.delivery is not None
    assert msg.delivery.target == "claude"
    assert msg.delivery.state == DeliveryState.SENT


def test_send_with_multiple_mentions(service):
    msg = service.send(text="@claude @codex review this", channel="general", sender="human")
    assert msg.delivery is None
    assert len(msg.deliveries) == 2
    targets = {d.target for d in msg.deliveries}
    assert targets == {"claude", "codex"}


def test_send_without_mention(service):
    msg = service.send(text="just a message", channel="general", sender="human")
    assert msg.delivery is None
    assert msg.deliveries == []


def test_send_with_reply_to(service):
    original = service.send(text="base", channel="general", sender="human")
    reply = service.send(text="reply", channel="general", sender="human", reply_to=original.id)
    assert reply.reply_to == original.id


def test_mention_detection_case_insensitive(service):
    msg = service.send(text="@Claude help", channel="general", sender="human")
    assert msg.delivery is not None
    assert msg.delivery.target == "claude"


def test_mention_must_match_known_agent(service):
    msg = service.send(text="@unknown help", channel="general", sender="human")
    assert msg.delivery is None


def test_mention_word_boundary(service):
    msg = service.send(text="email@claude.com is not a mention", channel="general", sender="human")
    assert msg.delivery is None


# --- State Transitions ---

def test_mark_seen(service, store):
    msg = service.send(text="@claude test", channel="general", sender="human")
    updated = service.mark_seen(msg.id, agent_name="claude")
    assert updated.delivery.state == DeliveryState.SEEN
    assert updated.delivery.seen_at is not None
    # Persisted
    persisted = store.get(msg.id)
    assert persisted.delivery.state == DeliveryState.SEEN


def test_mark_seen_multi_target(service):
    msg = service.send(text="@claude @codex test", channel="general", sender="human")
    updated = service.mark_seen(msg.id, agent_name="claude")
    claude_d = next(d for d in updated.deliveries if d.target == "claude")
    codex_d = next(d for d in updated.deliveries if d.target == "codex")
    assert claude_d.state == DeliveryState.SEEN
    assert codex_d.state == DeliveryState.SENT


def test_mark_responded(service):
    msg = service.send(text="@claude test", channel="general", sender="human")
    service.mark_seen(msg.id, agent_name="claude")
    updated = service.mark_responded(msg.id, agent_name="claude", response_id="resp-1")
    assert updated.delivery.state == DeliveryState.RESPONDED
    assert updated.delivery.responded_at is not None
    assert updated.delivery.response_id == "resp-1"


def test_mark_seen_wrong_agent_is_noop(service):
    msg = service.send(text="@claude test", channel="general", sender="human")
    updated = service.mark_seen(msg.id, agent_name="codex")
    assert updated is None


def test_cannot_respond_before_seen(service):
    msg = service.send(text="@claude test", channel="general", sender="human")
    result = service.mark_responded(msg.id, agent_name="claude", response_id="r1")
    assert result is None


# --- Agent Read (cursor-based seen detection) ---

def test_process_agent_read_marks_seen(service):
    m1 = service.send(text="@claude first", channel="general", sender="human")
    m2 = service.send(text="@claude second", channel="general", sender="human")
    service.send(text="no mention", channel="general", sender="human")

    result = service.process_agent_read(
        agent_name="claude", channel="general", read_up_to_id=m2.id
    )
    assert len(result) == 2
    for msg in result:
        assert msg.delivery.state == DeliveryState.SEEN


# --- Agent Response ---

def test_process_agent_response_marks_responded(service):
    m1 = service.send(text="@claude review", channel="general", sender="human")
    service.mark_seen(m1.id, agent_name="claude")

    result = service.process_agent_response(
        agent_name="claude", channel="general", response_id="resp-1"
    )
    assert len(result) == 1
    assert result[0].delivery.state == DeliveryState.RESPONDED
    assert result[0].delivery.response_id == "resp-1"


# --- Response after timeout ---

def test_respond_after_timeout(service, store):
    msg = service.send(text="@claude test", channel="general", sender="human")
    service.mark_seen(msg.id, agent_name="claude")
    # Simulate timeout (directly set state)
    persisted = store.get(msg.id)
    persisted.delivery.state = DeliveryState.TIMEOUT
    store.update(msg.id, persisted)

    updated = service.mark_responded(msg.id, agent_name="claude", response_id="late-resp")
    assert updated is not None
    assert updated.delivery.state == DeliveryState.RESPONDED
    assert updated.delivery.response_id == "late-resp"


# --- Idempotency ---

def test_duplicate_send_is_idempotent(store):
    from duckdome.models.message import Message
    msg = Message(text="hello", channel="general", sender="human")
    store.add(msg)
    store.add(msg)  # duplicate
    msgs = store.list_by_channel("general")
    assert len(msgs) == 1


def test_delete_message(service, store):
    msg = service.send(text="remove me", channel="general", sender="human")
    deleted = service.delete_message(msg.id)
    assert deleted is not None
    assert deleted.id == msg.id
    assert store.get(msg.id) is None
