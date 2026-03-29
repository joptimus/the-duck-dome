import time
from duckdome.models.message import Message, Delivery, DeliveryState


def test_message_without_delivery():
    msg = Message(text="hello world", channel="general", sender="human")
    assert msg.id is not None
    assert msg.delivery is None
    assert msg.deliveries == []


def test_message_with_single_delivery():
    msg = Message(
        text="@claude review this",
        channel="general",
        sender="human",
        delivery=Delivery(target="claude"),
    )
    assert msg.delivery is not None
    assert msg.delivery.target == "claude"
    assert msg.delivery.state == DeliveryState.SENT
    assert msg.delivery.sent_at is not None
    assert msg.delivery.delivered_at is None
    assert msg.delivery.acknowledged_at is None
    assert msg.delivery.response_id is None


def test_message_with_multiple_deliveries():
    msg = Message(
        text="@claude @codex review this",
        channel="general",
        sender="human",
        deliveries=[
            Delivery(target="claude"),
            Delivery(target="codex"),
        ],
    )
    assert len(msg.deliveries) == 2
    assert msg.deliveries[0].target == "claude"
    assert msg.deliveries[1].target == "codex"


def test_delivery_state_transitions():
    d = Delivery(target="claude")
    assert d.state == DeliveryState.SENT

    d.state = DeliveryState.DELIVERED
    d.delivered_at = time.time()
    assert d.state == DeliveryState.DELIVERED

    d.state = DeliveryState.ACKNOWLEDGED
    d.acknowledged_at = time.time()
    d.response_id = "resp-123"
    assert d.state == DeliveryState.ACKNOWLEDGED


def test_message_serialization_roundtrip():
    msg = Message(
        text="@claude test",
        channel="general",
        sender="human",
        delivery=Delivery(target="claude"),
    )
    data = msg.model_dump()
    restored = Message(**data)
    assert restored.id == msg.id
    assert restored.delivery.target == "claude"
    assert restored.delivery.state == DeliveryState.SENT
