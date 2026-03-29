"""Tests for rules REST API routes."""

import pytest
from fastapi.testclient import TestClient

from duckdome.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(data_dir=tmp_path)
    return TestClient(app)


def test_list_rules_empty(client):
    resp = client.get("/api/rules")
    assert resp.status_code == 200
    assert resp.json() == []


def test_propose_rule(client):
    resp = client.post("/api/rules", json={"text": "Be concise", "author": "claude"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["text"] == "Be concise"
    assert data["author"] == "claude"
    assert data["status"] == "draft"
    assert "id" in data


def test_list_active_empty(client):
    resp = client.get("/api/rules/active")
    assert resp.status_code == 200
    assert resp.json() == []


def test_activate_rule(client):
    create = client.post("/api/rules", json={"text": "No yelling"})
    rule_id = create.json()["id"]

    resp = client.post(f"/api/rules/{rule_id}/activate")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"

    active = client.get("/api/rules/active")
    assert len(active.json()) == 1
    assert active.json()[0]["id"] == rule_id


def test_archive_rule(client):
    create = client.post("/api/rules", json={"text": "Old rule"})
    rule_id = create.json()["id"]
    client.post(f"/api/rules/{rule_id}/activate")

    resp = client.post(f"/api/rules/{rule_id}/archive")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archive"

    active = client.get("/api/rules/active")
    assert len(active.json()) == 0


def test_edit_rule(client):
    create = client.post("/api/rules", json={"text": "Draft text"})
    rule_id = create.json()["id"]

    resp = client.patch(f"/api/rules/{rule_id}", json={"text": "Updated text"})
    assert resp.status_code == 200
    assert resp.json()["text"] == "Updated text"


def test_freshness_epoch(client):
    resp = client.get("/api/rules/freshness")
    assert resp.status_code == 200
    assert resp.json()["epoch"] == 0

    client.post("/api/rules", json={"text": "Rule one"})
    resp = client.get("/api/rules/freshness")
    assert resp.json()["epoch"] == 1


def test_activate_nonexistent(client):
    resp = client.post("/api/rules/fake-id/activate")
    assert resp.status_code == 404


def test_archive_nonexistent(client):
    resp = client.post("/api/rules/fake-id/archive")
    assert resp.status_code == 404


def test_edit_nonexistent(client):
    resp = client.patch("/api/rules/fake-id", json={"text": "nope"})
    assert resp.status_code == 404


def test_propose_empty_text_rejected(client):
    resp = client.post("/api/rules", json={"text": ""})
    assert resp.status_code == 422


def test_full_lifecycle(client):
    # Propose
    create = client.post("/api/rules", json={"text": "Be kind", "author": "claude"})
    rule_id = create.json()["id"]
    assert create.json()["status"] == "draft"

    # Activate
    client.post(f"/api/rules/{rule_id}/activate")

    # Verify active
    active = client.get("/api/rules/active")
    assert len(active.json()) == 1

    # Edit
    client.patch(f"/api/rules/{rule_id}", json={"text": "Be very kind"})

    # Archive
    client.post(f"/api/rules/{rule_id}/archive")

    # Verify no active
    active = client.get("/api/rules/active")
    assert len(active.json()) == 0

    # Epoch reflects all mutations
    freshness = client.get("/api/rules/freshness")
    assert freshness.json()["epoch"] > 0
