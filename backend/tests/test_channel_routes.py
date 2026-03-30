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


def test_remove_agent_from_channel(client):
    r = client.post("/api/channels", json={"name": "general", "type": "general"})
    ch_id = r.json()["id"]
    client.post(f"/api/channels/{ch_id}/agents", json={"agent_type": "claude"})
    resp = client.delete(f"/api/channels/{ch_id}/agents/claude")
    assert resp.status_code == 200
    assert resp.json() == {"removed": True}


def test_remove_agent_not_found(client):
    r = client.post("/api/channels", json={"name": "general", "type": "general"})
    ch_id = r.json()["id"]
    resp = client.delete(f"/api/channels/{ch_id}/agents/claude")
    assert resp.status_code == 404
