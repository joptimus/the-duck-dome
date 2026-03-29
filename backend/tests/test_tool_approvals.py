from __future__ import annotations

from fastapi.testclient import TestClient


def test_request_approval_appears_in_pending(client: TestClient):
    resp = client.post(
        "/api/tool_approvals/request",
        json={
            "agent": "codex",
            "tool": "exec_command",
            "arguments": {"cmd": "ls"},
            "channel": "general",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "pending"
    approval_id = body["approval_id"]
    assert body["approval"]["status"] == "pending"

    pending = client.get("/api/tool_approvals/pending")
    assert pending.status_code == 200
    items = pending.json()
    assert len(items) == 1
    assert items[0]["id"] == approval_id
    assert items[0]["tool"] == "exec_command"


def test_approve_changes_status_and_clears_pending(client: TestClient):
    requested = client.post(
        "/api/tool_approvals/request",
        json={
            "agent": "codex",
            "tool": "exec_command",
            "arguments": {"cmd": "pwd"},
            "channel": "general",
        },
    ).json()
    approval_id = requested["approval_id"]

    approve = client.post(
        f"/api/tool_approvals/{approval_id}/approve",
        json={"resolved_by": "human"},
    )
    assert approve.status_code == 200
    data = approve.json()
    assert data["status"] == "approved"
    assert data["resolution"] == "approved"
    assert data["resolved_by"] == "human"

    pending = client.get("/api/tool_approvals/pending")
    assert pending.status_code == 200
    assert pending.json() == []


def test_deny_changes_status(client: TestClient):
    requested = client.post(
        "/api/tool_approvals/request",
        json={
            "agent": "claude",
            "tool": "delete_file",
            "arguments": {"path": "/tmp/x"},
            "channel": "general",
        },
    ).json()
    approval_id = requested["approval_id"]

    deny = client.post(
        f"/api/tool_approvals/{approval_id}/deny",
        json={"resolved_by": "human"},
    )
    assert deny.status_code == 200
    data = deny.json()
    assert data["status"] == "denied"
    assert data["resolution"] == "denied"
    assert data["resolved_by"] == "human"


def test_approve_with_remember_sets_policy(client: TestClient):
    first = client.post(
        "/api/tool_approvals/request",
        json={
            "agent": "codex",
            "tool": "exec_command",
            "arguments": {"cmd": "echo one"},
            "channel": "general",
        },
    ).json()
    approval_id = first["approval_id"]

    approved = client.post(
        f"/api/tool_approvals/{approval_id}/approve",
        json={"resolved_by": "human", "remember": True},
    )
    assert approved.status_code == 200

    second = client.post(
        "/api/tool_approvals/request",
        json={
            "agent": "codex",
            "tool": "exec_command",
            "arguments": {"cmd": "echo two"},
            "channel": "general",
        },
    )
    assert second.status_code == 201
    assert second.json() == {"status": "approved", "source": "policy"}


def test_websocket_broadcasts_on_request_and_resolve(app):
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            requested = client.post(
                "/api/tool_approvals/request",
                json={
                    "agent": "gemini",
                    "tool": "write_file",
                    "arguments": {"path": "notes.txt"},
                    "channel": "general",
                },
            )
            assert requested.status_code == 201
            approval_id = requested.json()["approval_id"]

            event1 = ws.receive_json()
            assert event1["type"] == "tool_approval_updated"
            assert event1["approval"]["id"] == approval_id
            assert event1["approval"]["status"] == "pending"

            approved = client.post(
                f"/api/tool_approvals/{approval_id}/approve",
                json={"resolved_by": "human"},
            )
            assert approved.status_code == 200

            event2 = ws.receive_json()
            assert event2["type"] == "tool_approval_updated"
            assert event2["approval"]["id"] == approval_id
            assert event2["approval"]["status"] == "approved"
