from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from duckdome.services.tool_approval_service import ToolApprovalService

router = APIRouter(prefix="/api/tool_approvals", tags=["tool_approvals"])

_service: ToolApprovalService | None = None


def init(service: ToolApprovalService) -> None:
    global _service
    _service = service


def _get_service() -> ToolApprovalService:
    assert _service is not None
    return _service


class RequestApprovalBody(BaseModel):
    agent: str = Field(min_length=1)
    tool: str = Field(min_length=1)
    arguments: dict = Field(default_factory=dict)
    channel: str = Field(min_length=1)


class ResolveApprovalBody(BaseModel):
    resolved_by: str = Field(min_length=1)
    remember: bool = False


@router.post("/request", status_code=201)
def request_approval(body: RequestApprovalBody):
    svc = _get_service()
    result = svc.request(
        agent=body.agent,
        tool=body.tool,
        arguments=body.arguments,
        channel=body.channel,
    )
    if "approval" in result:
        approval = result["approval"]
        return {
            "status": "pending",
            "approval_id": approval.id,
            "approval": approval.model_dump(mode="json"),
        }
    return result


@router.get("/pending")
def list_pending(channel: str | None = None):
    svc = _get_service()
    pending = svc.list_pending(channel=channel)
    return [item.model_dump(mode="json") for item in pending]


@router.post("/{approval_id}/approve")
def approve(approval_id: str, body: ResolveApprovalBody):
    svc = _get_service()
    approval = svc.approve(
        approval_id=approval_id,
        resolved_by=body.resolved_by,
        remember=body.remember,
    )
    if approval is None:
        raise HTTPException(
            status_code=404,
            detail="Approval not found or not in pending state",
        )
    return approval.model_dump(mode="json")


@router.post("/{approval_id}/deny")
def deny(approval_id: str, body: ResolveApprovalBody):
    svc = _get_service()
    approval = svc.deny(
        approval_id=approval_id,
        resolved_by=body.resolved_by,
        remember=body.remember,
    )
    if approval is None:
        raise HTTPException(
            status_code=404,
            detail="Approval not found or not in pending state",
        )
    return approval.model_dump(mode="json")
