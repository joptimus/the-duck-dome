# Channel Runtime Model Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add first-class channel model with optional repo binding and channel-scoped agent instances as the runtime foundation for DuckDome.

**Architecture:** Channels are the primary partition for messages, agents, and routing. Two types: general (no repo) and repo (bound to a path). Agent instances are scoped per channel — one per type per channel. A store interface abstracts persistence so JSONL can be swapped later. Existing message flow gains channel validation.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, JSONL persistence, pytest + httpx

**Legacy reference:** This replaces legacy agentchattr's plain string channels and global agent registry. Channels become first-class objects. Agents become channel-scoped (were global). Slot naming, rename chains, and queue files are dropped.

---

## Task 1: Channel and AgentInstance Models

**Files:**
- Create: `backend/src/duckdome/models/channel.py`
- Test: `backend/tests/test_channel_models.py`

**Step 1: Write the failing test**

`backend/tests/test_channel_models.py`:
```python
import pytest
from duckdome.models.channel import Channel, ChannelType, AgentInstance


def test_general_channel():
    ch = Channel(name="planning", type=ChannelType.GENERAL)
    assert ch.id is not None
    assert ch.name == "planning"
    assert ch.type == ChannelType.GENERAL
    assert ch.repo_path is None
    assert ch.created_at is not None


def test_repo_channel():
    ch = Channel(
        name="my-app",
        type=ChannelType.REPO,
        repo_path="/Users/james/repos/my-app",
    )
    assert ch.type == ChannelType.REPO
    assert ch.repo_path == "/Users/james/repos/my-app"


def test_repo_channel_requires_repo_path():
    with pytest.raises(ValueError, match="repo_path"):
        Channel(name="bad", type=ChannelType.REPO)


def test_general_channel_rejects_repo_path():
    with pytest.raises(ValueError, match="repo_path"):
        Channel(name="bad", type=ChannelType.GENERAL, repo_path="/some/path")


def test_agent_instance():
    inst = AgentInstance(channel_id="ch-1", agent_type="claude")
    assert inst.id == "ch-1:claude"
    assert inst.status == "offline"
    assert inst.last_heartbeat is None
    assert inst.last_response is None
    assert inst.current_task is None
    assert inst.last_error is None


def test_agent_instance_serialization_roundtrip():
    inst = AgentInstance(channel_id="ch-1", agent_type="claude", status="working")
    data = inst.model_dump()
    restored = AgentInstance(**data)
    assert restored.id == "ch-1:claude"
    assert restored.status == "working"


def test_channel_serialization_roundtrip():
    ch = Channel(name="general", type=ChannelType.GENERAL)
    data = ch.model_dump()
    restored = Channel(**data)
    assert restored.id == ch.id
    assert restored.type == ChannelType.GENERAL
```

**Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_channel_models.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write the implementation**

`backend/src/duckdome/models/channel.py`:
```python
from __future__ import annotations

import time
import uuid
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ChannelType(StrEnum):
    GENERAL = "general"
    REPO = "repo"


class Channel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: ChannelType
    repo_path: str | None = None
    created_at: float = Field(default_factory=time.time)

    @model_validator(mode="after")
    def _validate_repo_path(self) -> Channel:
        if self.type == ChannelType.REPO and not self.repo_path:
            raise ValueError("repo_path is required for repo channels")
        if self.type == ChannelType.GENERAL and self.repo_path is not None:
            raise ValueError("repo_path must not be set for general channels")
        return self


class AgentInstance(BaseModel):
    id: str = ""
    channel_id: str
    agent_type: str
    status: str = "offline"
    last_heartbeat: float | None = None
    last_response: float | None = None
    current_task: str | None = None
    last_error: str | None = None

    def model_post_init(self, _context: object) -> None:
        if not self.id:
            self.id = f"{self.channel_id}:{self.agent_type}"
```

**Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_channel_models.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add backend/src/duckdome/models/channel.py backend/tests/test_channel_models.py
git commit -m "feat: add Channel and AgentInstance models"
```

---

## Task 2: Store Interface + Channel Store

**Files:**
- Create: `backend/src/duckdome/stores/base.py`
- Create: `backend/src/duckdome/stores/channel_store.py`
- Test: `backend/tests/test_channel_store.py`

**Step 1: Write the failing tests**

`backend/tests/test_channel_store.py`:
```python
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


def test_list_channels(store):
    store.add_channel(Channel(name="general", type=ChannelType.GENERAL))
    store.add_channel(Channel(name="my-app", type=ChannelType.REPO, repo_path="/tmp/my-app"))
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


def test_agents_do_not_cross_channels(store):
    ch1 = Channel(name="general", type=ChannelType.GENERAL)
    ch2 = Channel(name="my-app", type=ChannelType.REPO, repo_path="/tmp/my-app")
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_channel_store.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write the store interface and implementation**

`backend/src/duckdome/stores/base.py`:
```python
from __future__ import annotations

from abc import ABC, abstractmethod

from duckdome.models.channel import AgentInstance, Channel


class BaseChannelStore(ABC):
    @abstractmethod
    def add_channel(self, channel: Channel) -> Channel: ...

    @abstractmethod
    def get_channel(self, channel_id: str) -> Channel | None: ...

    @abstractmethod
    def list_channels(self) -> list[Channel]: ...

    @abstractmethod
    def add_agent(self, agent: AgentInstance) -> AgentInstance: ...

    @abstractmethod
    def get_agent(self, agent_id: str) -> AgentInstance | None: ...

    @abstractmethod
    def list_agents(self, channel_id: str) -> list[AgentInstance]: ...

    @abstractmethod
    def update_agent(self, agent_id: str, agent: AgentInstance) -> AgentInstance | None: ...
```

`backend/src/duckdome/stores/channel_store.py`:
```python
from __future__ import annotations

import json
import os
from pathlib import Path

from duckdome.models.channel import AgentInstance, Channel
from duckdome.stores.base import BaseChannelStore


class ChannelStore(BaseChannelStore):
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._channels_file = self._data_dir / "channels.jsonl"
        self._agents_file = self._data_dir / "agents.jsonl"
        self._channels: dict[str, Channel] = {}
        self._channel_order: list[str] = []
        self._agents: dict[str, AgentInstance] = {}
        self._load()

    def _load(self) -> None:
        if self._channels_file.exists():
            with open(self._channels_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    ch = Channel(**json.loads(line))
                    self._channels[ch.id] = ch
                    if ch.id not in self._channel_order:
                        self._channel_order.append(ch.id)
        if self._agents_file.exists():
            with open(self._agents_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    agent = AgentInstance(**json.loads(line))
                    self._agents[agent.id] = agent

    def _save_channels(self) -> None:
        tmp = self._channels_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for cid in self._channel_order:
                f.write(self._channels[cid].model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp.rename(self._channels_file)

    def _save_agents(self) -> None:
        tmp = self._agents_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for agent in self._agents.values():
                f.write(agent.model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp.rename(self._agents_file)

    def add_channel(self, channel: Channel) -> Channel:
        if channel.id in self._channels:
            return self._channels[channel.id]
        self._channels[channel.id] = channel
        self._channel_order.append(channel.id)
        self._save_channels()
        return channel

    def get_channel(self, channel_id: str) -> Channel | None:
        return self._channels.get(channel_id)

    def list_channels(self) -> list[Channel]:
        return [self._channels[cid] for cid in self._channel_order]

    def add_agent(self, agent: AgentInstance) -> AgentInstance:
        if agent.id in self._agents:
            return self._agents[agent.id]
        self._agents[agent.id] = agent
        self._save_agents()
        return agent

    def get_agent(self, agent_id: str) -> AgentInstance | None:
        return self._agents.get(agent_id)

    def list_agents(self, channel_id: str) -> list[AgentInstance]:
        return [a for a in self._agents.values() if a.channel_id == channel_id]

    def update_agent(self, agent_id: str, agent: AgentInstance) -> AgentInstance | None:
        if agent_id not in self._agents:
            return None
        self._agents[agent_id] = agent
        self._save_agents()
        return agent
```

**Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_channel_store.py -v`
Expected: All 11 tests PASS

**Step 5: Commit**

```bash
git add backend/src/duckdome/stores/base.py backend/src/duckdome/stores/channel_store.py backend/tests/test_channel_store.py
git commit -m "feat: add channel store with interface and JSONL persistence"
```

---

## Task 3: Channel Service

**Files:**
- Create: `backend/src/duckdome/services/channel_service.py`
- Test: `backend/tests/test_channel_service.py`

**Step 1: Write the failing tests**

`backend/tests/test_channel_service.py`:
```python
import os
import pytest
from duckdome.models.channel import ChannelType
from duckdome.services.channel_service import ChannelService
from duckdome.stores.channel_store import ChannelStore


@pytest.fixture
def store(tmp_path):
    return ChannelStore(data_dir=tmp_path)


@pytest.fixture
def service(store):
    return ChannelService(store=store)


# --- Channel CRUD ---

def test_create_general_channel(service):
    ch = service.create_channel(name="planning", type="general")
    assert ch.name == "planning"
    assert ch.type == ChannelType.GENERAL
    assert ch.repo_path is None


def test_create_repo_channel(service, tmp_path):
    repo = tmp_path / "my-repo"
    repo.mkdir()
    ch = service.create_channel(name="my-repo", type="repo", repo_path=str(repo))
    assert ch.type == ChannelType.REPO
    assert ch.repo_path == str(repo)


def test_create_repo_channel_validates_path_exists(service):
    with pytest.raises(ValueError, match="does not exist"):
        service.create_channel(name="bad", type="repo", repo_path="/nonexistent/path")


def test_get_channel(service):
    ch = service.create_channel(name="general", type="general")
    retrieved = service.get_channel(ch.id)
    assert retrieved.id == ch.id


def test_list_channels(service):
    service.create_channel(name="general", type="general")
    service.create_channel(name="planning", type="general")
    assert len(service.list_channels()) == 2


# --- Agent Management ---

def test_add_agent_to_channel(service):
    ch = service.create_channel(name="general", type="general")
    inst = service.add_agent(channel_id=ch.id, agent_type="claude")
    assert inst.channel_id == ch.id
    assert inst.agent_type == "claude"
    assert inst.id == f"{ch.id}:claude"


def test_add_agent_to_nonexistent_channel(service):
    with pytest.raises(ValueError, match="Channel not found"):
        service.add_agent(channel_id="nonexistent", agent_type="claude")


def test_duplicate_agent_type_per_channel(service):
    ch = service.create_channel(name="general", type="general")
    service.add_agent(channel_id=ch.id, agent_type="claude")
    inst2 = service.add_agent(channel_id=ch.id, agent_type="claude")
    agents = service.list_agents(ch.id)
    assert len(agents) == 1
    assert agents[0].id == inst2.id


def test_same_agent_type_different_channels(service):
    ch1 = service.create_channel(name="general", type="general")
    ch2 = service.create_channel(name="planning", type="general")
    i1 = service.add_agent(channel_id=ch1.id, agent_type="claude")
    i2 = service.add_agent(channel_id=ch2.id, agent_type="claude")
    assert i1.id != i2.id
    assert len(service.list_agents(ch1.id)) == 1
    assert len(service.list_agents(ch2.id)) == 1


def test_list_agents(service):
    ch = service.create_channel(name="general", type="general")
    service.add_agent(channel_id=ch.id, agent_type="claude")
    service.add_agent(channel_id=ch.id, agent_type="codex")
    agents = service.list_agents(ch.id)
    assert len(agents) == 2


# --- Channel-aware validation ---

def test_validate_channel_exists(service):
    ch = service.create_channel(name="general", type="general")
    assert service.validate_channel(ch.id) is True


def test_validate_channel_not_exists(service):
    assert service.validate_channel("nonexistent") is False


def test_get_agents_for_channel(service):
    ch = service.create_channel(name="general", type="general")
    service.add_agent(channel_id=ch.id, agent_type="claude")
    service.add_agent(channel_id=ch.id, agent_type="codex")
    agent_types = service.get_agent_types(ch.id)
    assert set(agent_types) == {"claude", "codex"}
```

**Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_channel_service.py -v`
Expected: FAIL with ModuleNotFoundError

**Step 3: Write the implementation**

`backend/src/duckdome/services/channel_service.py`:
```python
from __future__ import annotations

from pathlib import Path

from duckdome.models.channel import AgentInstance, Channel, ChannelType
from duckdome.stores.base import BaseChannelStore


class ChannelService:
    def __init__(self, store: BaseChannelStore) -> None:
        self._store = store

    def create_channel(
        self,
        name: str,
        type: str,
        repo_path: str | None = None,
    ) -> Channel:
        channel_type = ChannelType(type)
        if channel_type == ChannelType.REPO:
            if not repo_path:
                raise ValueError("repo_path is required for repo channels")
            if not Path(repo_path).is_dir():
                raise ValueError(f"repo_path does not exist: {repo_path}")
        channel = Channel(name=name, type=channel_type, repo_path=repo_path)
        return self._store.add_channel(channel)

    def get_channel(self, channel_id: str) -> Channel | None:
        return self._store.get_channel(channel_id)

    def list_channels(self) -> list[Channel]:
        return self._store.list_channels()

    def validate_channel(self, channel_id: str) -> bool:
        return self._store.get_channel(channel_id) is not None

    def add_agent(self, channel_id: str, agent_type: str) -> AgentInstance:
        if not self.validate_channel(channel_id):
            raise ValueError(f"Channel not found: {channel_id}")
        agent = AgentInstance(channel_id=channel_id, agent_type=agent_type)
        return self._store.add_agent(agent)

    def list_agents(self, channel_id: str) -> list[AgentInstance]:
        return self._store.list_agents(channel_id)

    def get_agent_types(self, channel_id: str) -> list[str]:
        agents = self._store.list_agents(channel_id)
        return [a.agent_type for a in agents]
```

**Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_channel_service.py -v`
Expected: All 12 tests PASS

**Step 5: Commit**

```bash
git add backend/src/duckdome/services/channel_service.py backend/tests/test_channel_service.py
git commit -m "feat: add channel service with validation and agent management"
```

---

## Task 4: Channel API Routes

**Files:**
- Create: `backend/src/duckdome/routes/channels.py`
- Test: `backend/tests/test_channel_routes.py`
- Modify: `backend/src/duckdome/app.py`

**Step 1: Write the failing tests**

`backend/tests/test_channel_routes.py`:
```python
import os
import pytest
from fastapi.testclient import TestClient
from duckdome.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(data_dir=tmp_path)
    return TestClient(app)


# --- POST /api/channels ---

def test_create_general_channel(client):
    resp = client.post("/api/channels", json={
        "name": "planning",
        "type": "general",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "planning"
    assert data["type"] == "general"
    assert data["repo_path"] is None


def test_create_repo_channel(client, tmp_path):
    repo = tmp_path / "my-repo"
    repo.mkdir()
    resp = client.post("/api/channels", json={
        "name": "my-repo",
        "type": "repo",
        "repo_path": str(repo),
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["type"] == "repo"
    assert data["repo_path"] == str(repo)


def test_create_repo_channel_invalid_path(client):
    resp = client.post("/api/channels", json={
        "name": "bad",
        "type": "repo",
        "repo_path": "/nonexistent/path",
    })
    assert resp.status_code == 422


def test_create_channel_validation(client):
    resp = client.post("/api/channels", json={"name": ""})
    assert resp.status_code == 422


# --- GET /api/channels ---

def test_list_channels(client):
    client.post("/api/channels", json={"name": "general", "type": "general"})
    client.post("/api/channels", json={"name": "planning", "type": "general"})
    resp = client.get("/api/channels")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# --- GET /api/channels/{id} ---

def test_get_channel(client):
    r = client.post("/api/channels", json={"name": "general", "type": "general"})
    ch_id = r.json()["id"]
    resp = client.get(f"/api/channels/{ch_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "general"


def test_get_channel_not_found(client):
    resp = client.get("/api/channels/nonexistent")
    assert resp.status_code == 404


# --- GET /api/channels/{id}/agents ---

def test_list_agents_empty(client):
    r = client.post("/api/channels", json={"name": "general", "type": "general"})
    ch_id = r.json()["id"]
    resp = client.get(f"/api/channels/{ch_id}/agents")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_agents_after_adding(client):
    r = client.post("/api/channels", json={"name": "general", "type": "general"})
    ch_id = r.json()["id"]
    client.post(f"/api/channels/{ch_id}/agents", json={"agent_type": "claude"})
    client.post(f"/api/channels/{ch_id}/agents", json={"agent_type": "codex"})
    resp = client.get(f"/api/channels/{ch_id}/agents")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


# --- POST /api/channels/{id}/agents ---

def test_add_agent_to_channel(client):
    r = client.post("/api/channels", json={"name": "general", "type": "general"})
    ch_id = r.json()["id"]
    resp = client.post(f"/api/channels/{ch_id}/agents", json={"agent_type": "claude"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["agent_type"] == "claude"
    assert data["channel_id"] == ch_id


def test_add_agent_to_nonexistent_channel(client):
    resp = client.post("/api/channels/nonexistent/agents", json={"agent_type": "claude"})
    assert resp.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_channel_routes.py -v`
Expected: FAIL

**Step 3: Write the route implementation**

`backend/src/duckdome/routes/channels.py`:
```python
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from duckdome.services.channel_service import ChannelService

router = APIRouter(prefix="/api/channels", tags=["channels"])

_service: ChannelService | None = None


def init(service: ChannelService) -> None:
    global _service
    _service = service


def _get_service() -> ChannelService:
    assert _service is not None
    return _service


class CreateChannelRequest(BaseModel):
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    repo_path: str | None = None


class AddAgentRequest(BaseModel):
    agent_type: str = Field(min_length=1)


@router.post("", status_code=201)
def create_channel(body: CreateChannelRequest):
    svc = _get_service()
    try:
        ch = svc.create_channel(
            name=body.name, type=body.type, repo_path=body.repo_path
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return ch.model_dump()


@router.get("")
def list_channels():
    svc = _get_service()
    return [ch.model_dump() for ch in svc.list_channels()]


@router.get("/{channel_id}")
def get_channel(channel_id: str):
    svc = _get_service()
    ch = svc.get_channel(channel_id)
    if ch is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return ch.model_dump()


# Static route before parameterized
@router.get("/{channel_id}/agents")
def list_agents(channel_id: str):
    svc = _get_service()
    if not svc.validate_channel(channel_id):
        raise HTTPException(status_code=404, detail="Channel not found")
    agents = svc.list_agents(channel_id)
    return [a.model_dump() for a in agents]


@router.post("/{channel_id}/agents", status_code=201)
def add_agent(channel_id: str, body: AddAgentRequest):
    svc = _get_service()
    try:
        inst = svc.add_agent(channel_id=channel_id, agent_type=body.agent_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return inst.model_dump()
```

**Step 4: Update app.py to wire channel service**

Replace `backend/src/duckdome/app.py` with:
```python
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from duckdome.routes.health import router as health_router
from duckdome.routes import messages as messages_mod
from duckdome.routes import deliveries as deliveries_mod
from duckdome.routes import channels as channels_mod
from duckdome.services.channel_service import ChannelService
from duckdome.services.message_service import MessageService
from duckdome.stores.channel_store import ChannelStore
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
    message_store = MessageStore(data_dir=data_dir)
    channel_store = ChannelStore(data_dir=data_dir)

    # Services
    channel_service = ChannelService(store=channel_store)
    message_service = MessageService(
        store=message_store,
        known_agents=DEFAULT_AGENTS,
        channel_service=channel_service,
    )

    # Init routes with dependencies
    messages_mod.init(message_service)
    deliveries_mod.init(message_service)
    channels_mod.init(channel_service)

    # Register routers
    app.include_router(health_router)
    app.include_router(messages_mod.router)
    app.include_router(deliveries_mod.router)
    app.include_router(channels_mod.router)

    return app
```

NOTE: This passes `channel_service` to `MessageService` — Task 5 will add that parameter.

**Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_channel_routes.py -v`
Expected: All 11 tests PASS (after Task 5 completes the MessageService change)

**Step 6: Commit**

```bash
git add backend/src/duckdome/routes/channels.py backend/tests/test_channel_routes.py backend/src/duckdome/app.py
git commit -m "feat: add channel API routes and wire into app"
```

---

## Task 5: Channel-Aware Message Validation + Mention Routing

**Files:**
- Modify: `backend/src/duckdome/services/message_service.py`
- Test: `backend/tests/test_channel_message_integration.py`

**Step 1: Write the failing tests**

`backend/tests/test_channel_message_integration.py`:
```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/python -m pytest tests/test_channel_message_integration.py -v`
Expected: FAIL (MessageService doesn't accept channel_service yet)

**Step 3: Update MessageService**

Modify `backend/src/duckdome/services/message_service.py` — add `channel_service` parameter and channel-aware routing:

```python
from __future__ import annotations

import re
import time

from duckdome.models.message import Delivery, DeliveryState, Message
from duckdome.stores.message_store import MessageStore


class MessageService:
    def __init__(
        self,
        store: MessageStore,
        known_agents: list[str],
        channel_service: object | None = None,
    ) -> None:
        self._store = store
        self._known_agents = [a.lower() for a in known_agents]
        self._channel_service = channel_service
        self._build_mention_regex()

    def _build_mention_regex(self) -> None:
        if not self._known_agents:
            self._mention_re = None
            return
        names = sorted(self._known_agents, key=len, reverse=True)
        escaped = "|".join(re.escape(n) for n in names)
        self._mention_re = re.compile(
            rf"(?<![a-zA-Z0-9_.])@({escaped})\b", re.IGNORECASE
        )

    def _parse_mentions(self, text: str) -> list[str]:
        if self._mention_re is None:
            return []
        matches = self._mention_re.findall(text)
        seen: set[str] = set()
        result: list[str] = []
        for m in matches:
            name = m.lower()
            if name not in seen:
                seen.add(name)
                result.append(name)
        return result

    def _filter_mentions_by_channel(
        self, mentions: list[str], channel_id: str
    ) -> list[str]:
        if self._channel_service is None:
            return mentions
        channel_agents = set(self._channel_service.get_agent_types(channel_id))
        return [m for m in mentions if m in channel_agents]

    def send(self, text: str, channel: str, sender: str) -> Message:
        if self._channel_service and not self._channel_service.validate_channel(channel):
            raise ValueError(f"Invalid channel: {channel}")

        mentions = self._parse_mentions(text)
        mentions = self._filter_mentions_by_channel(mentions, channel)

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

    # ... rest of the methods remain unchanged ...
```

IMPORTANT: Only the `__init__`, `_filter_mentions_by_channel`, and `send` methods change. All other methods (`mark_seen`, `mark_responded`, `process_agent_read`, `process_agent_response`, `list_messages`, `list_by_delivery_state`, `list_open_deliveries`) stay exactly as they are.

**Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/python -m pytest tests/test_channel_message_integration.py -v`
Expected: All 5 tests PASS

**Step 5: Run ALL tests to confirm nothing broke**

Run: `cd backend && .venv/bin/python -m pytest tests/ -v`
Expected: All tests PASS (existing tests still work because `channel_service=None` preserves old behavior)

**Step 6: Commit**

```bash
git add backend/src/duckdome/services/message_service.py backend/tests/test_channel_message_integration.py
git commit -m "feat: add channel-aware message validation and mention routing"
```

---

## Task 6: Verify Build + Push + PR

**Step 1: Run full test suite**

Run: `cd backend && .venv/bin/python -m pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 2: Verify all files compile**

Run: `cd backend && .venv/bin/python -m py_compile src/duckdome/models/channel.py && .venv/bin/python -m py_compile src/duckdome/stores/base.py && .venv/bin/python -m py_compile src/duckdome/stores/channel_store.py && .venv/bin/python -m py_compile src/duckdome/services/channel_service.py && .venv/bin/python -m py_compile src/duckdome/routes/channels.py && .venv/bin/python -m py_compile src/duckdome/app.py && echo "All compile OK"`

**Step 3: Verify app starts**

Run: `cd backend && .venv/bin/python -c "from duckdome.app import create_app; import tempfile, pathlib; app = create_app(data_dir=pathlib.Path(tempfile.mkdtemp())); print('OK:', [r.path for r in app.routes if '/api/' in r.path])"`

**Step 4: Push and create PR**

```bash
git push -u origin feature/channel-runtime-model
gh pr create --title "Add channel model with optional repo binding and channel-scoped agents"
```
