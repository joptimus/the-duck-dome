from __future__ import annotations

import time
import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class RuleStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVE = "archive"


class Rule(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str = Field(max_length=160)
    status: RuleStatus = RuleStatus.DRAFT
    author: str | None = None
    reason: str | None = Field(default=None, max_length=240)
    created_at: float = Field(default_factory=time.time)
