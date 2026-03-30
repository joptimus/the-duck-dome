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
