"""JSON-file persistence for repo sources and hidden repos.

Files created under data_dir:
  - repo_sources.json  — list of {path, mode} source configs
  - repo_hidden.json   — list of hidden repo paths
"""

from __future__ import annotations

import json
import os
from pathlib import Path


class RepoStore:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._sources_file = self._data_dir / "repo_sources.json"
        self._hidden_file = self._data_dir / "repo_hidden.json"
        self._sources: list[dict] = []
        self._hidden: set[str] = set()
        self._load()

    def _load(self) -> None:
        if self._sources_file.exists():
            with open(self._sources_file, "r", encoding="utf-8") as f:
                self._sources = json.load(f)
        if self._hidden_file.exists():
            with open(self._hidden_file, "r", encoding="utf-8") as f:
                self._hidden = set(json.load(f))

    def _save_sources(self) -> None:
        tmp = self._sources_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._sources, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self._sources_file)

    def _save_hidden(self) -> None:
        tmp = self._hidden_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(sorted(self._hidden), f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        tmp.replace(self._hidden_file)

    def list_sources(self) -> list[dict]:
        return list(self._sources)

    def add_source(self, path: str, mode: str = "root") -> None:
        exists = any(
            s["path"] == path and s["mode"] == mode for s in self._sources
        )
        if not exists:
            self._sources.append({"path": path, "mode": mode})
            self._save_sources()

    def remove_source(self, path: str) -> None:
        self._sources = [s for s in self._sources if s["path"] != path]
        self._save_sources()

    def list_hidden(self) -> set[str]:
        return set(self._hidden)

    def hide(self, path: str) -> None:
        self._hidden.add(path)
        self._save_hidden()

    def unhide(self, path: str) -> None:
        self._hidden.discard(path)
        self._save_hidden()
