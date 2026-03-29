from __future__ import annotations

import time
import uuid
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class TriggerStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    COMPLETED = "completed"
    FAILED = "failed"


class Trigger(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    channel_id: str
    target_agent_type: str
    target_agent_instance_id: str = ""
    source_message_id: str
    status: TriggerStatus = TriggerStatus.PENDING
    dedupe_key: str = ""
    created_at: float = Field(default_factory=time.time)
    claimed_at: float | None = None
    completed_at: float | None = None
    last_error: str | None = None

    @model_validator(mode="after")
    def _set_derived_fields(self) -> Trigger:
        if not self.target_agent_instance_id:
            self.target_agent_instance_id = (
                f"{self.channel_id}:{self.target_agent_type}"
            )
        if not self.dedupe_key:
            self.dedupe_key = (
                f"{self.channel_id}:{self.target_agent_type}:{self.source_message_id}"
            )
        return self
