from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class AutoApprovePolicy(StrEnum):
    NONE = "none"
    TOOL = "tool"
    ALL = "all"


class ToolPermission(BaseModel):
    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    description: str = ""
    icon: str = "BoltIcon"
    enabled: bool = False
    highRisk: bool = False


class AgentPermissions(BaseModel):
    tools: list[ToolPermission] = Field(default_factory=list)
    autoApprove: AutoApprovePolicy = AutoApprovePolicy.NONE
    maxLoops: int = 25

    @model_validator(mode="after")
    def _clamp_max_loops(self) -> AgentPermissions:
        self.maxLoops = min(100, max(1, int(self.maxLoops)))
        return self
