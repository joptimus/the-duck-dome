from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from duckdome.services.agent_permission_service import AgentPermissionService

router = APIRouter(prefix="/api/agents", tags=["agent_permissions"])

_service: AgentPermissionService | None = None


def init(service: AgentPermissionService) -> None:
    global _service
    _service = service


def _get_service() -> AgentPermissionService:
    assert _service is not None
    return _service


class ToolUpdate(BaseModel):
    key: str = Field(min_length=1)
    enabled: bool


class PermissionsUpdateBody(BaseModel):
    agent: str = Field(min_length=1)
    permissions: dict


@router.get("/{agent_key}/permissions")
def get_agent_permissions(agent_key: str):
    svc = _get_service()
    permissions = svc.get_agent_permissions(agent_key)
    return {
        "agent": agent_key,
        "permissions": permissions.model_dump(mode="json"),
    }


@router.put("/{agent_key}/permissions")
def update_agent_permissions(agent_key: str, body: PermissionsUpdateBody):
    svc = _get_service()
    raw_permissions = body.permissions or {}
    permissions = svc.update_agent_permissions(
        agent_key,
        tools=raw_permissions.get("tools"),
        auto_approve=raw_permissions.get("autoApprove"),
        max_loops=raw_permissions.get("maxLoops"),
    )
    return {
        "agent": agent_key,
        "permissions": permissions.model_dump(mode="json"),
    }
