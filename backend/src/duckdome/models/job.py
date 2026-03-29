from __future__ import annotations

import time
import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class JobStatus(StrEnum):
    OPEN = "open"
    DONE = "done"
    ARCHIVED = "archived"


class Job(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    body: str = ""
    status: JobStatus = JobStatus.OPEN
    channel: str
    assignee: str | None = None
    created_by: str
    messages: list[dict] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
