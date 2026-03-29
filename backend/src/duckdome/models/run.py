from __future__ import annotations

import time
import uuid

from pydantic import BaseModel, Field


class RunRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    trigger_id: str
    channel_id: str
    agent_type: str
    started_at: float = Field(default_factory=time.time)
    ended_at: float | None = None
    duration_ms: int | None = None
    exit_code: int | None = None
    error_summary: str | None = None
