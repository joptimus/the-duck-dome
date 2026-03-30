"""Repo data types — sources to scan and discovered repo entries."""

from __future__ import annotations

from pydantic import BaseModel, Field
import hashlib


class RepoSource(BaseModel):
    """A configured directory to scan for repos."""
    path: str
    mode: str = Field(pattern="^(root|repo)$", default="root")


class RepoEntry(BaseModel):
    """A discovered repo on disk."""
    id: str = ""
    name: str
    path: str
    channel: str = ""
    source: str = ""

    def model_post_init(self, __context) -> None:
        if not self.id:
            self.id = hashlib.sha256(self.path.encode()).hexdigest()[:12]
