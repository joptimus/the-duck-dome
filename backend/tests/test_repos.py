"""Tests for repo store, service, and routes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from duckdome.stores.repo_store import RepoStore


@pytest.fixture
def tmp_data(tmp_path):
    return tmp_path


class TestRepoStore:
    def test_empty_on_init(self, tmp_data):
        store = RepoStore(data_dir=tmp_data)
        assert store.list_sources() == []
        assert store.list_hidden() == set()

    def test_add_source(self, tmp_data):
        store = RepoStore(data_dir=tmp_data)
        store.add_source("C:/Users/test/Dev", "root")
        sources = store.list_sources()
        assert len(sources) == 1
        assert sources[0]["path"] == "C:/Users/test/Dev"
        assert sources[0]["mode"] == "root"

    def test_add_source_no_duplicate(self, tmp_data):
        store = RepoStore(data_dir=tmp_data)
        store.add_source("C:/Users/test/Dev", "root")
        store.add_source("C:/Users/test/Dev", "root")
        assert len(store.list_sources()) == 1

    def test_remove_source(self, tmp_data):
        store = RepoStore(data_dir=tmp_data)
        store.add_source("C:/Users/test/Dev", "root")
        store.remove_source("C:/Users/test/Dev")
        assert len(store.list_sources()) == 0

    def test_hide_and_unhide(self, tmp_data):
        store = RepoStore(data_dir=tmp_data)
        store.hide("C:/Users/test/Dev/myrepo")
        assert "C:/Users/test/Dev/myrepo" in store.list_hidden()
        store.unhide("C:/Users/test/Dev/myrepo")
        assert "C:/Users/test/Dev/myrepo" not in store.list_hidden()

    def test_persistence_across_instances(self, tmp_data):
        store1 = RepoStore(data_dir=tmp_data)
        store1.add_source("C:/Dev", "repo")
        store1.hide("C:/Dev/hidden")

        store2 = RepoStore(data_dir=tmp_data)
        assert len(store2.list_sources()) == 1
        assert "C:/Dev/hidden" in store2.list_hidden()


from duckdome.services.repo_service import RepoService


@pytest.fixture
def repo_service(tmp_data, tmp_path):
    """Create a repo service with some fake git repos on disk."""
    store = RepoStore(data_dir=tmp_data)
    # Create fake repos with .git dirs
    for name in ("alpha", "bravo", "charlie"):
        repo_dir = tmp_path / "projects" / name
        repo_dir.mkdir(parents=True)
        (repo_dir / ".git").mkdir()
    return store, RepoService(store=store), tmp_path / "projects"


class TestRepoService:
    def test_collect_repos_from_root(self, repo_service):
        store, svc, projects = repo_service
        store.add_source(str(projects), "root")
        repos = svc.collect_repos()
        names = {r["name"] for r in repos}
        assert names == {"alpha", "bravo", "charlie"}

    def test_collect_repos_single(self, repo_service):
        store, svc, projects = repo_service
        store.add_source(str(projects / "alpha"), "repo")
        repos = svc.collect_repos()
        assert len(repos) == 1
        assert repos[0]["name"] == "alpha"

    def test_hidden_repos_excluded(self, repo_service):
        store, svc, projects = repo_service
        store.add_source(str(projects), "root")
        store.hide(str((projects / "bravo").resolve()))
        repos = svc.collect_repos()
        names = {r["name"] for r in repos}
        assert "bravo" not in names

    def test_add_source_auto_detects_repo(self, repo_service):
        store, svc, projects = repo_service
        svc.add_source(str(projects / "alpha"))
        sources = store.list_sources()
        assert sources[0]["mode"] == "repo"

    def test_add_source_root_mode(self, repo_service):
        store, svc, projects = repo_service
        svc.add_source(str(projects))
        sources = store.list_sources()
        assert sources[0]["mode"] == "root"

    def test_remove_source_hides(self, repo_service):
        store, svc, projects = repo_service
        store.add_source(str(projects), "root")
        svc.remove_source(str(projects / "alpha"))
        assert str((projects / "alpha").resolve()) in store.list_hidden()


from fastapi.testclient import TestClient
from duckdome.app import create_app


@pytest.fixture
def client(tmp_data):
    app = create_app(data_dir=tmp_data)
    return TestClient(app)


class TestRepoRoutes:
    def test_list_repos_empty(self, client):
        resp = client.get("/api/repos")
        assert resp.status_code == 200
        data = resp.json()
        assert data["repos"] == []
        assert data["sources"] == []

    def test_add_and_list(self, client, tmp_data, tmp_path):
        repo_dir = tmp_path / "myrepo"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        resp = client.post("/api/repos/add", json={"path": str(repo_dir)})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        resp = client.get("/api/repos")
        assert len(resp.json()["repos"]) == 1
        assert resp.json()["repos"][0]["name"] == "myrepo"

    def test_add_missing_path(self, client):
        resp = client.post("/api/repos/add", json={"path": "/nonexistent/path"})
        assert resp.status_code == 422

    def test_remove(self, client, tmp_path):
        repo_dir = tmp_path / "removeme"
        repo_dir.mkdir()
        (repo_dir / ".git").mkdir()

        client.post("/api/repos/add", json={"path": str(repo_dir)})
        resp = client.post("/api/repos/remove", json={"path": str(repo_dir)})
        assert resp.status_code == 200

        resp = client.get("/api/repos")
        assert len(resp.json()["repos"]) == 0
