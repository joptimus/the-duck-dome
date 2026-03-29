from __future__ import annotations

from fastapi.testclient import TestClient


def test_create_and_list_jobs(client: TestClient):
    created = client.post(
        "/api/jobs",
        json={
            "title": "Investigate flaky tests",
            "body": "Find root cause and patch",
            "channel": "general",
            "created_by": "human",
            "assignee": "codex",
        },
    )
    assert created.status_code == 201
    job = created.json()
    assert job["title"] == "Investigate flaky tests"
    assert job["status"] == "open"
    assert job["channel"] == "general"
    assert job["assignee"] == "codex"

    listed = client.get("/api/jobs")
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["id"] == job["id"]


def test_list_jobs_filtered_by_channel_and_status(client: TestClient):
    j1 = client.post(
        "/api/jobs",
        json={
            "title": "General open",
            "channel": "general",
            "created_by": "human",
        },
    ).json()
    j2 = client.post(
        "/api/jobs",
        json={
            "title": "Repo open",
            "channel": "repo-x",
            "created_by": "human",
        },
    ).json()
    client.patch(f"/api/jobs/{j2['id']}", json={"status": "done"})

    filtered_channel = client.get("/api/jobs", params={"channel": "general"})
    assert filtered_channel.status_code == 200
    assert [j["id"] for j in filtered_channel.json()] == [j1["id"]]

    filtered_status = client.get("/api/jobs", params={"status": "done"})
    assert filtered_status.status_code == 200
    assert [j["id"] for j in filtered_status.json()] == [j2["id"]]


def test_update_job_assign_and_close(client: TestClient):
    created = client.post(
        "/api/jobs",
        json={
            "title": "Implement parser",
            "channel": "general",
            "created_by": "human",
        },
    ).json()
    job_id = created["id"]

    updated = client.patch(
        f"/api/jobs/{job_id}",
        json={"assignee": "claude", "status": "done"},
    )
    assert updated.status_code == 200
    data = updated.json()
    assert data["assignee"] == "claude"
    assert data["status"] == "done"

    archived = client.patch(f"/api/jobs/{job_id}", json={"status": "archived"})
    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"


def test_job_messages_roundtrip(client: TestClient):
    created = client.post(
        "/api/jobs",
        json={
            "title": "Write migration notes",
            "channel": "general",
            "created_by": "human",
        },
    ).json()
    job_id = created["id"]

    post_msg = client.post(
        f"/api/jobs/{job_id}/messages",
        json={
            "sender": "codex",
            "text": "Started drafting plan",
            "type": "chat",
        },
    )
    assert post_msg.status_code == 201
    msg = post_msg.json()
    assert msg["sender"] == "codex"
    assert msg["text"] == "Started drafting plan"
    assert msg["type"] == "chat"

    listed = client.get(f"/api/jobs/{job_id}/messages")
    assert listed.status_code == 200
    messages = listed.json()
    assert len(messages) == 1
    assert messages[0]["id"] == msg["id"]


def test_create_job_rejects_oversized_title_and_body(client: TestClient):
    too_long_title = "x" * 121
    resp_title = client.post(
        "/api/jobs",
        json={
            "title": too_long_title,
            "channel": "general",
            "created_by": "human",
        },
    )
    assert resp_title.status_code == 422

    too_long_body = "x" * 1001
    resp_body = client.post(
        "/api/jobs",
        json={
            "title": "ok",
            "body": too_long_body,
            "channel": "general",
            "created_by": "human",
        },
    )
    assert resp_body.status_code == 422


def test_websocket_broadcasts_job_changes(app):
    with TestClient(app) as client:
        with client.websocket_connect("/ws") as ws:
            created = client.post(
                "/api/jobs",
                json={
                    "title": "Ship v1",
                    "channel": "general",
                    "created_by": "human",
                },
            )
            assert created.status_code == 201
            job_id = created.json()["id"]

            event1 = ws.receive_json()
            assert event1["type"] == "job_updated"
            assert event1["job"]["id"] == job_id
            assert event1["job"]["status"] == "open"

            posted = client.post(
                f"/api/jobs/{job_id}/messages",
                json={
                    "sender": "human",
                    "text": "Please prioritize this",
                    "type": "chat",
                },
            )
            assert posted.status_code == 201

            event2 = ws.receive_json()
            assert event2["type"] == "job_message_added"
            assert event2["job_id"] == job_id
            assert event2["message"]["text"] == "Please prioritize this"
