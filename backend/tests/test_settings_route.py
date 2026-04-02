from fastapi.testclient import TestClient
from duckdome.app import create_app


def test_get_settings_returns_defaults(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    resp = client.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["show_agent_windows"] is False


def test_patch_settings_persists(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    resp = client.patch("/api/settings", json={"show_agent_windows": True})
    assert resp.status_code == 200
    assert resp.json()["show_agent_windows"] is True

    resp2 = client.get("/api/settings")
    assert resp2.json()["show_agent_windows"] is True


def test_patch_unknown_key_is_ignored(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path))
    resp = client.patch("/api/settings", json={"unknown_key": "foo"})
    assert resp.status_code == 200
    assert "unknown_key" not in resp.json()
