"""Repo discovery and management logic.

Scans configured source directories for git repos,
filters hidden repos, and manages add/remove operations.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from duckdome.stores.repo_store import RepoStore


class RepoService:
    def __init__(self, store: RepoStore) -> None:
        self._store = store

    def collect_repos(self) -> list[dict]:
        """Scan all sources and return discovered repos, excluding hidden."""
        hidden = self._store.list_hidden()
        seen: set[str] = set()
        repos: list[dict] = []

        for source in self._store.list_sources():
            path = Path(source["path"])
            mode = source.get("mode", "root")
            if not path.is_dir():
                continue
            if mode == "repo":
                self._add_if_repo(path, source, hidden, seen, repos)
            else:
                for child in sorted(path.iterdir()):
                    if child.is_dir():
                        self._add_if_repo(child, source, hidden, seen, repos)

        repos.sort(key=lambda r: r["name"].lower())
        return repos

    def _add_if_repo(
        self,
        path: Path,
        source: dict,
        hidden: set[str],
        seen: set[str],
        repos: list[dict],
    ) -> None:
        resolved = str(path.resolve())
        if resolved in hidden or resolved in seen:
            return
        if not (path / ".git").exists():
            return
        seen.add(resolved)
        repos.append({
            "id": hashlib.sha1(resolved.encode()).hexdigest()[:12],
            "name": path.name,
            "path": resolved,
            "source": f"{source.get('mode', 'root')}:{source['path']}",
        })

    def add_source(self, path: str) -> dict:
        """Add a repo source. Auto-detects root vs single repo."""
        p = Path(path)
        if not p.is_dir():
            raise ValueError(f"Path does not exist: {path}")
        resolved = str(p.resolve())
        mode = "repo" if (p / ".git").exists() else "root"
        self._store.add_source(resolved, mode)
        self._store.unhide(resolved)
        return {"path": resolved, "mode": mode}

    def list_sources(self) -> list[dict]:
        """Return all configured repo sources."""
        return self._store.list_sources()

    def remove_source(self, path: str) -> None:
        """Hide a repo path and remove matching sources."""
        resolved = str(Path(path).resolve())
        self._store.hide(resolved)
        self._store.remove_source(resolved)
