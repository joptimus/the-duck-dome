# Delivery State Tracking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Track delivery state (sent/delivered/acknowledged) for @mention messages so the system knows whether an agent received and responded to a directed message.

**Architecture:** Extend the message model with an optional `delivery` field (single target) or `deliveries` list (multi-target). JSONL file store for persistence. Services handle mention detection and state transitions. Routes expose message CRUD and delivery queries. Follows existing layer pattern: routes -> services -> stores.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, JSONL file storage, pytest + httpx for testing.

**Legacy reference:** This replaces legacy implicit delivery behavior via queue files. In agentchattr, `router.py` detected @mentions, `agents.trigger` wrote fire-and-forget queue files, and `mcp_bridge.chat_read` advanced cursors with no read receipts. DuckDome adds explicit delivery state tracking on the message record itself.

---

## Task 1: Set Up Test Infrastructure

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/pytest.ini`

**Step 1: Create test infrastructure files**

`backend/pytest.ini`:
```ini
[pytest]
testpaths = tests
pythonpath = src
```

`backend/tests/__init__.py`: empty file

`backend/tests/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient
from duckdome.app import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    return TestClient(app)
```

**Step 2: Run existing health test to verify setup**

Run: `cd backend && .venv/bin/python -m pytest tests/ -v`
Expected: 0 tests collected (no test files yet), no errors

**Step 3: Commit**

```bash
git add backend/tests/ backend/pytest.ini
git commit -m "chore: add test infrastructure for backend"
```

---

## Task 2: Message and Delivery Models

**Files:**
- Create: `backend/src/duckdome/models/__init__.py`
- Create: `backend/src/duckdome/models/message.py`
- Create: `backend/tests/test_models.py`

**Step 1: Write the failing test**

`backend/tests/test_models.py`:
```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_models.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write the implementation**

`backend/src/duckdome/models/__init__.py`: empty file

`backend/src/duckdome/models/message.py`:
```python
from __future__ import annotations

import time
import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class DeliveryState(StrEnum):
    SENT = "sent"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    TIMEOUT = "timeout"


class Delivery(BaseModel):
    target: str
    state: DeliveryState = DeliveryState.SENT
    sent_at: float = Field(default_factory=time.time)
    delivered_at: float | None = None
    acknowledged_at: float | None = None
    response_id: str | None = None


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    channel: str
    sender: str
    timestamp: float = Field(default_factory=time.time)
    delivery: Delivery | None = None
    deliveries: list[Delivery] = Field(default_factory=list)
```

**Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_models.py -v`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add backend/src/duckdome/models/ backend/tests/test_models.py
git commit -m "feat: add Message and Delivery models with state tracking"
```

---

## Task 3: Message Store (JSONL Persistence)

**Files:**
- Create: `backend/src/duckdome/stores/__init__.py`
- Create: `backend/src/duckdome/stores/message_store.py`
- Create: `backend/tests/test_message_store.py`

**Step 1: Write the failing tests**

`backend/tests/test_message_store.py`:
```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_message_store.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write the implementation**

`backend/src/duckdome/stores/__init__.py`: empty file

`backend/src/duckdome/stores/message_store.py`:
```python
from __future__ import annotations

import json
import os
from pathlib import Path

from duckdome.models.message import Message


class MessageStore:
    """Append-only JSONL message store with in-memory index."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._file = self._data_dir / "messages.jsonl"
        self._messages: dict[str, Message] = {}
        self._order: list[str] = []
        self._load()

    def _load(self) -> None:
        if not self._file.exists():
            return
        with open(self._file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                msg = Message(**json.loads(line))
                self._messages[msg.id] = msg
                if msg.id not in self._order:
                    self._order.append(msg.id)

    def _append(self, msg: Message) -> None:
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(msg.model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())

    def _rewrite(self) -> None:
        tmp = self._file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for msg_id in self._order:
                f.write(self._messages[msg_id].model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp.rename(self._file)

    def add(self, msg: Message) -> Message:
        self._messages[msg.id] = msg
        self._order.append(msg.id)
        self._append(msg)
        return msg

    def get(self, msg_id: str) -> Message | None:
        return self._messages.get(msg_id)

    def update(self, msg_id: str, msg: Message) -> Message | None:
        if msg_id not in self._messages:
            return None
        self._messages[msg_id] = msg
        self._rewrite()
        return msg

    def list_by_channel(
        self, channel: str, after_id: str | None = None
    ) -> list[Message]:
        msgs = [self._messages[mid] for mid in self._order if self._messages[mid].channel == channel]
        if after_id is not None:
            try:
                idx = next(i for i, m in enumerate(msgs) if m.id == after_id)
                msgs = msgs[idx + 1 :]
            except StopIteration:
                pass
        return msgs

    def list_by_delivery_state(self, state: str) -> list[Message]:
        result = []
        for mid in self._order:
            msg = self._messages[mid]
            if msg.delivery and msg.delivery.state == state:
                result.append(msg)
            elif msg.deliveries:
                if any(d.state == state for d in msg.deliveries):
                    result.append(msg)
        return result
```

**Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_message_store.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add backend/src/duckdome/stores/ backend/tests/test_message_store.py
git commit -m "feat: add JSONL message store with delivery state queries"
```

---

## Task 4: Message Service (Mention Detection + State Transitions)

**Files:**
- Create: `backend/src/duckdome/services/__init__.py`
- Create: `backend/src/duckdome/services/message_service.py`
- Create: `backend/tests/test_message_service.py`

**Step 1: Write the failing tests**

`backend/tests/test_message_service.py`:
```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_message_service.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write the implementation**

`backend/src/duckdome/services/__init__.py`: empty file

`backend/src/duckdome/services/message_service.py`:
```python
from __future__ import annotations

import re
import time

from duckdome.models.message import Delivery, DeliveryState, Message
from duckdome.stores.message_store import MessageStore


class MessageService:
    def __init__(self, store: MessageStore, known_agents: list[str]) -> None:
        self._store = store
        self._known_agents = [a.lower() for a in known_agents]
        self._build_mention_regex()

    def _build_mention_regex(self) -> None:
        if not self._known_agents:
            self._mention_re = None
            return
        # Sort longest-first to avoid partial matches
        names = sorted(self._known_agents, key=len, reverse=True)
        escaped = "|".join(re.escape(n) for n in names)
        self._mention_re = re.compile(
            rf"(?<![a-zA-Z0-9_.])@({escaped})\b", re.IGNORECASE
        )

    def _parse_mentions(self, text: str) -> list[str]:
        if self._mention_re is None:
            return []
        matches = self._mention_re.findall(text)
        # Deduplicate, preserve order, normalize to lowercase
        seen: set[str] = set()
        result: list[str] = []
        for m in matches:
            name = m.lower()
            if name not in seen:
                seen.add(name)
                result.append(name)
        return result

    def send(self, text: str, channel: str, sender: str) -> Message:
        mentions = self._parse_mentions(text)

        delivery = None
        deliveries: list[Delivery] = []

        if len(mentions) == 1:
            delivery = Delivery(target=mentions[0])
        elif len(mentions) > 1:
            deliveries = [Delivery(target=name) for name in mentions]

        msg = Message(
            text=text,
            channel=channel,
            sender=sender,
            delivery=delivery,
            deliveries=deliveries,
        )
        self._store.add(msg)
        return msg

    def _get_delivery_for_agent(
        self, msg: Message, agent_name: str
    ) -> Delivery | None:
        agent = agent_name.lower()
        if msg.delivery and msg.delivery.target == agent:
            return msg.delivery
        for d in msg.deliveries:
            if d.target == agent:
                return d
        return None

    def mark_delivered(self, msg_id: str, agent_name: str) -> Message | None:
        msg = self._store.get(msg_id)
        if msg is None:
            return None
        delivery = self._get_delivery_for_agent(msg, agent_name)
        if delivery is None:
            return None
        if delivery.state != DeliveryState.SENT:
            return msg
        delivery.state = DeliveryState.DELIVERED
        delivery.delivered_at = time.time()
        return self._store.update(msg_id, msg)

    def mark_acknowledged(
        self, msg_id: str, agent_name: str, response_id: str
    ) -> Message | None:
        msg = self._store.get(msg_id)
        if msg is None:
            return None
        delivery = self._get_delivery_for_agent(msg, agent_name)
        if delivery is None:
            return None
        if delivery.state != DeliveryState.DELIVERED:
            return None
        delivery.state = DeliveryState.ACKNOWLEDGED
        delivery.acknowledged_at = time.time()
        delivery.response_id = response_id
        return self._store.update(msg_id, msg)

    def process_agent_read(
        self, agent_name: str, channel: str, read_up_to_id: str
    ) -> list[Message]:
        """Mark all sent messages targeted at agent as delivered, up to read_up_to_id."""
        msgs = self._store.list_by_channel(channel)
        delivered: list[Message] = []
        for msg in msgs:
            d = self._get_delivery_for_agent(msg, agent_name)
            if d and d.state == DeliveryState.SENT:
                updated = self.mark_delivered(msg.id, agent_name)
                if updated:
                    delivered.append(updated)
            if msg.id == read_up_to_id:
                break
        return delivered

    def process_agent_response(
        self, agent_name: str, channel: str, response_id: str
    ) -> list[Message]:
        """Mark all delivered messages targeted at agent as acknowledged."""
        msgs = self._store.list_by_channel(channel)
        acknowledged: list[Message] = []
        for msg in msgs:
            d = self._get_delivery_for_agent(msg, agent_name)
            if d and d.state == DeliveryState.DELIVERED:
                updated = self.mark_acknowledged(msg.id, agent_name, response_id)
                if updated:
                    acknowledged.append(updated)
        return acknowledged
```

**Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_message_service.py -v`
Expected: All 13 tests PASS

**Step 5: Commit**

```bash
git add backend/src/duckdome/services/ backend/tests/test_message_service.py
git commit -m "feat: add message service with mention detection and delivery state transitions"
```

---

## Task 5: API Routes (Messages + Deliveries)

**Files:**
- Create: `backend/src/duckdome/routes/messages.py`
- Create: `backend/src/duckdome/routes/deliveries.py`
- Modify: `backend/src/duckdome/app.py`
- Create: `backend/tests/test_routes.py`

**Step 1: Write the failing tests**

`backend/tests/test_routes.py`:
```python
import pytest
from fastapi.testclient import TestClient
from duckdome.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(data_dir=tmp_path)
    return TestClient(app)


# --- POST /api/messages ---

def test_send_message(client):
    resp = client.post("/api/messages", json={
        "text": "hello world",
        "channel": "general",
        "sender": "human",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] is not None
    assert data["text"] == "hello world"
    assert data["delivery"] is None


def test_send_message_with_mention(client):
    resp = client.post("/api/messages", json={
        "text": "@claude review this",
        "channel": "general",
        "sender": "human",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["delivery"] is not None
    assert data["delivery"]["target"] == "claude"
    assert data["delivery"]["state"] == "sent"


def test_send_message_validation(client):
    resp = client.post("/api/messages", json={"text": ""})
    assert resp.status_code == 422


# --- GET /api/messages ---

def test_list_messages(client):
    client.post("/api/messages", json={
        "text": "one", "channel": "general", "sender": "human"
    })
    client.post("/api/messages", json={
        "text": "two", "channel": "general", "sender": "human"
    })
    resp = client.get("/api/messages", params={"channel": "general"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_list_messages_with_after(client):
    r1 = client.post("/api/messages", json={
        "text": "one", "channel": "general", "sender": "human"
    })
    client.post("/api/messages", json={
        "text": "two", "channel": "general", "sender": "human"
    })
    msg1_id = r1.json()["id"]
    resp = client.get("/api/messages", params={
        "channel": "general", "after": msg1_id
    })
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# --- POST /api/messages/{id}/delivered ---

def test_mark_delivered(client):
    r = client.post("/api/messages", json={
        "text": "@claude test", "channel": "general", "sender": "human"
    })
    msg_id = r.json()["id"]
    resp = client.post(f"/api/messages/{msg_id}/delivered", json={
        "agent_name": "claude"
    })
    assert resp.status_code == 200
    assert resp.json()["delivery"]["state"] == "delivered"


def test_mark_delivered_wrong_agent(client):
    r = client.post("/api/messages", json={
        "text": "@claude test", "channel": "general", "sender": "human"
    })
    msg_id = r.json()["id"]
    resp = client.post(f"/api/messages/{msg_id}/delivered", json={
        "agent_name": "codex"
    })
    assert resp.status_code == 404


# --- POST /api/messages/{id}/acknowledged ---

def test_mark_acknowledged(client):
    r = client.post("/api/messages", json={
        "text": "@claude test", "channel": "general", "sender": "human"
    })
    msg_id = r.json()["id"]
    client.post(f"/api/messages/{msg_id}/delivered", json={"agent_name": "claude"})
    resp = client.post(f"/api/messages/{msg_id}/acknowledged", json={
        "agent_name": "claude",
        "response_id": "resp-1"
    })
    assert resp.status_code == 200
    assert resp.json()["delivery"]["state"] == "acknowledged"
    assert resp.json()["delivery"]["response_id"] == "resp-1"


# --- POST /api/messages/agent-read ---

def test_agent_read_marks_delivered(client):
    r1 = client.post("/api/messages", json={
        "text": "@claude first", "channel": "general", "sender": "human"
    })
    r2 = client.post("/api/messages", json={
        "text": "@claude second", "channel": "general", "sender": "human"
    })
    resp = client.post("/api/messages/agent-read", json={
        "agent_name": "claude",
        "channel": "general",
        "read_up_to_id": r2.json()["id"],
    })
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# --- POST /api/messages/agent-response ---

def test_agent_response_marks_acknowledged(client):
    r = client.post("/api/messages", json={
        "text": "@claude review", "channel": "general", "sender": "human"
    })
    msg_id = r.json()["id"]
    client.post(f"/api/messages/{msg_id}/delivered", json={"agent_name": "claude"})

    resp = client.post("/api/messages/agent-response", json={
        "agent_name": "claude",
        "channel": "general",
        "response_id": "resp-1",
    })
    assert resp.status_code == 200
    assert len(resp.json()) == 1


# --- GET /api/deliveries ---

def test_list_deliveries_by_state(client):
    client.post("/api/messages", json={
        "text": "@claude one", "channel": "general", "sender": "human"
    })
    client.post("/api/messages", json={
        "text": "no mention", "channel": "general", "sender": "human"
    })
    resp = client.get("/api/deliveries", params={"state": "sent"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["delivery"]["state"] == "sent"


def test_list_deliveries_open(client):
    """state=open returns sent + delivered messages."""
    r = client.post("/api/messages", json={
        "text": "@claude one", "channel": "general", "sender": "human"
    })
    msg_id = r.json()["id"]
    client.post("/api/messages", json={
        "text": "@codex two", "channel": "general", "sender": "human"
    })
    # Deliver one
    client.post(f"/api/messages/{msg_id}/delivered", json={"agent_name": "claude"})

    resp = client.get("/api/deliveries", params={"state": "open"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2
```

**Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_routes.py -v`
Expected: FAIL

**Step 3: Write the route implementations**

`backend/src/duckdome/routes/messages.py`:
```python
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from duckdome.services.message_service import MessageService

router = APIRouter(prefix="/api/messages", tags=["messages"])

# Will be set by app factory
_service: MessageService | None = None


def init(service: MessageService) -> None:
    global _service
    _service = service


def _get_service() -> MessageService:
    assert _service is not None
    return _service


class SendMessageRequest(BaseModel):
    text: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    sender: str = Field(min_length=1)


class AgentDeliveredRequest(BaseModel):
    agent_name: str


class AgentAcknowledgedRequest(BaseModel):
    agent_name: str
    response_id: str


class AgentReadRequest(BaseModel):
    agent_name: str
    channel: str
    read_up_to_id: str


class AgentResponseRequest(BaseModel):
    agent_name: str
    channel: str
    response_id: str


@router.post("", status_code=201)
def send_message(body: SendMessageRequest):
    svc = _get_service()
    msg = svc.send(text=body.text, channel=body.channel, sender=body.sender)
    return msg.model_dump()


@router.get("")
def list_messages(channel: str, after: str | None = None):
    svc = _get_service()
    msgs = svc._store.list_by_channel(channel, after_id=after)
    return [m.model_dump() for m in msgs]


@router.post("/{msg_id}/delivered")
def mark_delivered(msg_id: str, body: AgentDeliveredRequest):
    svc = _get_service()
    result = svc.mark_delivered(msg_id, agent_name=body.agent_name)
    if result is None:
        raise HTTPException(status_code=404, detail="Message not found or agent not targeted")
    return result.model_dump()


@router.post("/{msg_id}/acknowledged")
def mark_acknowledged(msg_id: str, body: AgentAcknowledgedRequest):
    svc = _get_service()
    result = svc.mark_acknowledged(msg_id, agent_name=body.agent_name, response_id=body.response_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Message not found or not in delivered state")
    return result.model_dump()


@router.post("/agent-read")
def agent_read(body: AgentReadRequest):
    svc = _get_service()
    delivered = svc.process_agent_read(
        agent_name=body.agent_name,
        channel=body.channel,
        read_up_to_id=body.read_up_to_id,
    )
    return [m.model_dump() for m in delivered]


@router.post("/agent-response")
def agent_response(body: AgentResponseRequest):
    svc = _get_service()
    acknowledged = svc.process_agent_response(
        agent_name=body.agent_name,
        channel=body.channel,
        response_id=body.response_id,
    )
    return [m.model_dump() for m in acknowledged]
```

`backend/src/duckdome/routes/deliveries.py`:
```python
from __future__ import annotations

from fastapi import APIRouter

from duckdome.services.message_service import MessageService

router = APIRouter(prefix="/api/deliveries", tags=["deliveries"])

_service: MessageService | None = None


def init(service: MessageService) -> None:
    global _service
    _service = service


def _get_service() -> MessageService:
    assert _service is not None
    return _service


@router.get("")
def list_deliveries(state: str = "open"):
    svc = _get_service()
    if state == "open":
        sent = svc._store.list_by_delivery_state("sent")
        delivered = svc._store.list_by_delivery_state("delivered")
        # Deduplicate by id preserving order
        seen: set[str] = set()
        result = []
        for msg in sent + delivered:
            if msg.id not in seen:
                seen.add(msg.id)
                result.append(msg)
        return [m.model_dump() for m in result]
    else:
        msgs = svc._store.list_by_delivery_state(state)
        return [m.model_dump() for m in msgs]
```

**Step 4: Update app.py to wire everything together**

Modify `backend/src/duckdome/app.py`:
```python
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from duckdome.routes.health import router as health_router
from duckdome.routes import messages as messages_mod
from duckdome.routes import deliveries as deliveries_mod
from duckdome.services.message_service import MessageService
from duckdome.stores.message_store import MessageStore

DEV_ORIGINS = [
    "http://localhost:5173",
]

DEFAULT_AGENTS = ["claude", "codex", "gemini"]


def create_app(data_dir: Path | None = None) -> FastAPI:
    if data_dir is None:
        data_dir = Path.home() / ".duckdome" / "data"

    app = FastAPI(title="DuckDome")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Stores
    store = MessageStore(data_dir=data_dir)

    # Services
    message_service = MessageService(store=store, known_agents=DEFAULT_AGENTS)

    # Init routes with dependencies
    messages_mod.init(message_service)
    deliveries_mod.init(message_service)

    # Register routers
    app.include_router(health_router)
    app.include_router(messages_mod.router)
    app.include_router(deliveries_mod.router)

    return app
```

**Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_routes.py -v`
Expected: All 12 tests PASS

**Step 6: Run all tests**

Run: `cd backend && .venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS (models + store + service + routes)

**Step 7: Commit**

```bash
git add backend/src/duckdome/routes/messages.py backend/src/duckdome/routes/deliveries.py backend/src/duckdome/app.py backend/tests/test_routes.py
git commit -m "feat: add message and delivery API routes"
```

---

## Task 6: Verify Build and Integration

**Files:** None new — verification only.

**Step 1: Run full test suite**

Run: `cd backend && .venv/bin/python -m pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 2: Verify app starts**

Run: `cd backend && timeout 5 .venv/bin/python -m uvicorn duckdome.main:app --host 0.0.0.0 --port 8000 2>&1 || true`
Expected: Server starts without errors (may timeout, that's fine)

**Step 3: Verify no lint/type issues**

Run: `cd backend && .venv/bin/python -m py_compile src/duckdome/models/message.py && .venv/bin/python -m py_compile src/duckdome/stores/message_store.py && .venv/bin/python -m py_compile src/duckdome/services/message_service.py && .venv/bin/python -m py_compile src/duckdome/routes/messages.py && .venv/bin/python -m py_compile src/duckdome/routes/deliveries.py && echo "All files compile OK"`
Expected: "All files compile OK"

**Step 4: Commit any fixes, then create PR**

```bash
git push -u origin feature/reliability-delivery-state
gh pr create --title "feat: delivery state tracking for @mention messages" --body "..."
```
