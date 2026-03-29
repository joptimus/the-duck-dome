"""Jobs model.

This replaces legacy jobs from ``agentchattr/apps/server/src/jobs.py``.
Differences from legacy behavior:
- intentionally drops ``type``, ``anchor_msg_id``, and ``sort_order``
  per the migration plan for a smaller first version
"""

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
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(default="", max_length=1000)
    status: JobStatus = JobStatus.OPEN
    channel: str
    assignee: str | None = None
    created_by: str
    messages: list[dict] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
