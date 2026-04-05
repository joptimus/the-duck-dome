from __future__ import annotations

from fastapi.testclient import TestClient


def test_get_default_agent_permissions(client: TestClient):
    response = client.get("/api/agents/claude/permissions")
    assert response.status_code == 200
    body = response.json()
    assert body["agent"] == "claude"
    assert body["permissions"]["autoApprove"] == "none"
    assert body["permissions"]["maxLoops"] == 25
    assert [tool["key"] for tool in body["permissions"]["tools"]] == [
        "bash",
        "write_file",
        "read_file",
        "web_search",
    ]


def test_update_agent_permissions_persists(client: TestClient):
    response = client.put(
        "/api/agents/codex/permissions",
        json={
            "agent": "codex",
            "permissions": {
                "tools": [
                    {"key": "bash", "enabled": False},
                    {"key": "write_file", "enabled": True},
                    {"key": "read_file", "enabled": True},
                    {"key": "web_search", "enabled": True},
                ],
                "autoApprove": "tool",
                "maxLoops": 17,
            },
        },
    )
    assert response.status_code == 200
    body = response.json()["permissions"]
    assert body["autoApprove"] == "tool"
    assert body["maxLoops"] == 17
    assert next(tool for tool in body["tools"] if tool["key"] == "bash")["enabled"] is False

    fetched = client.get("/api/agents/codex/permissions")
    assert fetched.status_code == 200
    fetched_body = fetched.json()["permissions"]
    assert fetched_body["autoApprove"] == "tool"
    assert fetched_body["maxLoops"] == 17
    assert next(tool for tool in fetched_body["tools"] if tool["key"] == "bash")["enabled"] is False


def test_disabled_tool_is_denied_without_creating_pending_approval(client: TestClient):
    update = client.put(
        "/api/agents/claude/permissions",
        json={
            "agent": "claude",
            "permissions": {
                "tools": [{"key": "bash", "enabled": False}],
                "autoApprove": "none",
                "maxLoops": 25,
            },
        },
    )
    assert update.status_code == 200

    request = client.post(
        "/api/tool_approvals/request",
        json={
            "agent": "claude",
            "tool": "bash",
            "arguments": {"cmd": "pwd"},
            "channel": "general",
        },
    )
    assert request.status_code == 201
    assert request.json() == {"status": "denied", "source": "permissions"}

    pending = client.get("/api/tool_approvals/pending")
    assert pending.status_code == 200
    assert pending.json() == []


def test_auto_approve_tools_allows_enabled_tool_without_pending_approval(client: TestClient):
    update = client.put(
        "/api/agents/codex/permissions",
        json={
            "agent": "codex",
            "permissions": {
                "tools": [
                    {"key": "bash", "enabled": True},
                    {"key": "write_file", "enabled": True},
                    {"key": "read_file", "enabled": True},
                    {"key": "web_search", "enabled": False},
                ],
                "autoApprove": "tool",
                "maxLoops": 25,
            },
        },
    )
    assert update.status_code == 200

    request = client.post(
        "/api/tool_approvals/request",
        json={
            "agent": "codex",
            "tool": "bash",
            "arguments": {"command": "ls"},
            "channel": "general",
        },
    )
    assert request.status_code == 201
    assert request.json() == {"status": "approved", "source": "permissions"}


def test_channel_agents_include_permissions(client: TestClient):
    created = client.post("/api/channels", json={"name": "planning", "type": "general"})
    assert created.status_code == 201
    channel_id = created.json()["id"]
    client.post(f"/api/channels/{channel_id}/agents", json={"agent_type": "claude"})

    listed = client.get(f"/api/channels/{channel_id}/agents")
    assert listed.status_code == 200
    body = listed.json()
    assert len(body) == 1
    assert body[0]["agent_type"] == "claude"
    assert body[0]["permissions"]["autoApprove"] == "none"
    assert body[0]["permissions"]["maxLoops"] == 25
