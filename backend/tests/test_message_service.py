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

def test_mark_delivered(service, store):
    msg = service.send(text="@claude test", channel="general", sender="human")
    updated = service.mark_delivered(msg.id, agent_name="claude")
    assert updated.delivery.state == DeliveryState.DELIVERED
    assert updated.delivery.delivered_at is not None
    # Persisted
    persisted = store.get(msg.id)
    assert persisted.delivery.state == DeliveryState.DELIVERED


def test_mark_delivered_multi_target(service):
    msg = service.send(text="@claude @codex test", channel="general", sender="human")
    updated = service.mark_delivered(msg.id, agent_name="claude")
    claude_d = next(d for d in updated.deliveries if d.target == "claude")
    codex_d = next(d for d in updated.deliveries if d.target == "codex")
    assert claude_d.state == DeliveryState.DELIVERED
    assert codex_d.state == DeliveryState.SENT


def test_mark_acknowledged(service):
    msg = service.send(text="@claude test", channel="general", sender="human")
    service.mark_delivered(msg.id, agent_name="claude")
    updated = service.mark_acknowledged(msg.id, agent_name="claude", response_id="resp-1")
    assert updated.delivery.state == DeliveryState.ACKNOWLEDGED
    assert updated.delivery.acknowledged_at is not None
    assert updated.delivery.response_id == "resp-1"


def test_mark_delivered_wrong_agent_is_noop(service):
    msg = service.send(text="@claude test", channel="general", sender="human")
    updated = service.mark_delivered(msg.id, agent_name="codex")
    assert updated is None


def test_cannot_acknowledge_before_delivered(service):
    msg = service.send(text="@claude test", channel="general", sender="human")
    result = service.mark_acknowledged(msg.id, agent_name="claude", response_id="r1")
    assert result is None


# --- Agent Read (cursor-based delivery detection) ---

def test_process_agent_read_marks_delivered(service):
    m1 = service.send(text="@claude first", channel="general", sender="human")
    m2 = service.send(text="@claude second", channel="general", sender="human")
    service.send(text="no mention", channel="general", sender="human")

    delivered = service.process_agent_read(
        agent_name="claude", channel="general", read_up_to_id=m2.id
    )
    assert len(delivered) == 2
    for msg in delivered:
        assert msg.delivery.state == DeliveryState.DELIVERED


# --- Agent Response (acknowledgment detection) ---

def test_process_agent_response_marks_acknowledged(service):
    m1 = service.send(text="@claude review", channel="general", sender="human")
    service.mark_delivered(m1.id, agent_name="claude")

    ack_msgs = service.process_agent_response(
        agent_name="claude", channel="general", response_id="resp-1"
    )
    assert len(ack_msgs) == 1
    assert ack_msgs[0].delivery.state == DeliveryState.ACKNOWLEDGED
    assert ack_msgs[0].delivery.response_id == "resp-1"
