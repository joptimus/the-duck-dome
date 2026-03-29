import pytest
from fastapi.testclient import TestClient
from duckdome.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(data_dir=tmp_path)
    return TestClient(app)


@pytest.fixture
def channel_id(client):
    r = client.post("/api/channels", json={"name": "general", "type": "general"})
    return r.json()["id"]


# --- Agent runtime ---

def test_register_agent(client, channel_id):
    resp = client.post("/api/agents/register", json={
        "channel_id": channel_id, "agent_type": "claude"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "idle"
    assert data["last_heartbeat"] is not None


def test_register_invalid_channel(client):
    resp = client.post("/api/agents/register", json={
        "channel_id": "nonexistent", "agent_type": "claude"
    })
    assert resp.status_code == 422


def test_heartbeat(client, channel_id):
    client.post("/api/agents/register", json={
        "channel_id": channel_id, "agent_type": "claude"
    })
    resp = client.post("/api/agents/heartbeat", json={
        "channel_id": channel_id, "agent_type": "claude"
    })
    assert resp.status_code == 200
    assert resp.json()["last_heartbeat"] is not None


def test_heartbeat_unregistered(client, channel_id):
    resp = client.post("/api/agents/heartbeat", json={
        "channel_id": channel_id, "agent_type": "claude"
    })
    assert resp.status_code == 404


def test_deregister(client, channel_id):
    client.post("/api/agents/register", json={
        "channel_id": channel_id, "agent_type": "claude"
    })
    resp = client.post("/api/agents/deregister", json={
        "channel_id": channel_id, "agent_type": "claude"
    })
    assert resp.status_code == 200
    assert resp.json()["status"] == "offline"


# --- Triggers ---

def test_claim_empty(client, channel_id):
    client.post("/api/agents/register", json={
        "channel_id": channel_id, "agent_type": "claude"
    })
    resp = client.post("/api/triggers/claim", json={
        "channel_id": channel_id, "agent_type": "claude"
    })
    assert resp.status_code == 200
    assert resp.json()["trigger"] is None


def test_list_triggers_after_mention(client, channel_id):
    """Sending a @mention creates a delivery but not a trigger (triggers are separate)."""
    client.post("/api/agents/register", json={
        "channel_id": channel_id, "agent_type": "claude"
    })
    client.post("/api/messages", json={
        "text": "@claude review this",
        "channel": channel_id,
        "sender": "human",
    })
    # Triggers are not auto-created from mentions yet
    resp = client.get("/api/triggers", params={"channel_id": channel_id})
    assert resp.status_code == 200
    assert resp.json() == []


def test_claim_and_complete_via_api(client, channel_id):
    """Full claim→complete lifecycle using a service-seeded trigger."""
    from duckdome.routes import triggers as triggers_mod

    # Register agent
    client.post("/api/agents/register", json={
        "channel_id": channel_id, "agent_type": "claude"
    })

    # Seed a trigger via the service (not yet wired to mentions)
    svc = triggers_mod._service
    svc.create_trigger(channel_id, "claude", "msg-1")

    # Claim
    claim_resp = client.post("/api/triggers/claim", json={
        "channel_id": channel_id, "agent_type": "claude"
    })
    assert claim_resp.status_code == 200
    claimed = claim_resp.json()
    assert claimed["status"] == "claimed"
    trigger_id = claimed["id"]

    # Complete
    complete_resp = client.post(f"/api/triggers/{trigger_id}/complete")
    assert complete_resp.status_code == 200
    assert complete_resp.json()["status"] == "completed"


def test_complete_nonexistent_trigger(client):
    resp = client.post("/api/triggers/nonexistent/complete")
    assert resp.status_code == 404


def test_fail_nonexistent_trigger(client):
    resp = client.post("/api/triggers/nonexistent/fail", json={
        "error": "something broke"
    })
    assert resp.status_code == 404


def test_list_triggers(client, channel_id):
    client.post("/api/agents/register", json={
        "channel_id": channel_id, "agent_type": "claude"
    })
    resp = client.get("/api/triggers", params={"channel_id": channel_id})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_triggers_with_status_filter(client, channel_id):
    client.post("/api/agents/register", json={
        "channel_id": channel_id, "agent_type": "claude"
    })
    resp = client.get("/api/triggers", params={
        "channel_id": channel_id, "status": "pending"
    })
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
