from __future__ import annotations

import time
import uuid
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class ChannelType(StrEnum):
    GENERAL = "general"
    REPO = "repo"


class Channel(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: ChannelType
    repo_path: str | None = None
    created_at: float = Field(default_factory=time.time)

    @model_validator(mode="after")
    def _validate_repo_path(self) -> Channel:
        name = self.name.strip()
        if not name:
            raise ValueError("name must not be empty")
        self.name = name

        repo_path = self.repo_path.strip() if self.repo_path is not None else None
        if self.type == ChannelType.REPO and not repo_path:
            raise ValueError("repo_path is required for repo channels")
        if self.type == ChannelType.GENERAL and repo_path:
            raise ValueError("repo_path must not be set for general channels")

        self.repo_path = repo_path if self.type == ChannelType.REPO else None
        return self


class AgentInstance(BaseModel):
    id: str = ""
    channel_id: str
    agent_type: str
    status: str = "offline"
    last_heartbeat: float | None = None
    last_response: float | None = None
    current_task: str | None = None
    last_error: str | None = None

    def model_post_init(self, _context: object) -> None:
        if not self.id:
            self.id = f"{self.channel_id}:{self.agent_type}"
