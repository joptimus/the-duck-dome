from __future__ import annotations

import time
import uuid
from enum import StrEnum

from pydantic import BaseModel, Field


class ToolApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class ToolPolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class ToolApproval(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent: str
    tool: str
    arguments: dict = Field(default_factory=dict)
    channel: str
    status: ToolApprovalStatus = ToolApprovalStatus.PENDING
    resolution: str | None = None
    resolved_by: str | None = None
    created_at: float = Field(default_factory=time.time)
    resolved_at: float | None = None
