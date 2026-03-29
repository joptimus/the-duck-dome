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


# --- POST /api/messages/{id}/seen ---

def test_mark_seen(client):
    r = client.post("/api/messages", json={
        "text": "@claude test", "channel": "general", "sender": "human"
    })
    msg_id = r.json()["id"]
    resp = client.post(f"/api/messages/{msg_id}/seen", json={
        "agent_name": "claude"
    })
    assert resp.status_code == 200
    assert resp.json()["delivery"]["state"] == "seen"


def test_mark_seen_wrong_agent(client):
    r = client.post("/api/messages", json={
        "text": "@claude test", "channel": "general", "sender": "human"
    })
    msg_id = r.json()["id"]
    resp = client.post(f"/api/messages/{msg_id}/seen", json={
        "agent_name": "codex"
    })
    assert resp.status_code == 404


# --- POST /api/messages/{id}/responded ---

def test_mark_responded(client):
    r = client.post("/api/messages", json={
        "text": "@claude test", "channel": "general", "sender": "human"
    })
    msg_id = r.json()["id"]
    client.post(f"/api/messages/{msg_id}/seen", json={"agent_name": "claude"})
    resp = client.post(f"/api/messages/{msg_id}/responded", json={
        "agent_name": "claude",
        "response_id": "resp-1"
    })
    assert resp.status_code == 200
    assert resp.json()["delivery"]["state"] == "responded"
    assert resp.json()["delivery"]["response_id"] == "resp-1"


# --- POST /api/messages/agent-read ---

def test_agent_read_marks_seen(client):
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

def test_agent_response_marks_responded(client):
    r = client.post("/api/messages", json={
        "text": "@claude review", "channel": "general", "sender": "human"
    })
    msg_id = r.json()["id"]
    client.post(f"/api/messages/{msg_id}/seen", json={"agent_name": "claude"})

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
    """state=open returns sent + seen messages."""
    r = client.post("/api/messages", json={
        "text": "@claude one", "channel": "general", "sender": "human"
    })
    msg_id = r.json()["id"]
    client.post("/api/messages", json={
        "text": "@codex two", "channel": "general", "sender": "human"
    })
    # Mark one as seen
    client.post(f"/api/messages/{msg_id}/seen", json={"agent_name": "claude"})

    resp = client.get("/api/deliveries", params={"state": "open"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2
