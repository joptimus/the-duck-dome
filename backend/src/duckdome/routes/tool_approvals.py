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


class ClearPoliciesBody(BaseModel):
    agent: str | None = None
    tool: str | None = None


@router.post("/request", status_code=201)
def request_approval(body: RequestApprovalBody):
    svc = _get_service()
    result = svc.request(
        agent=body.agent,
        tool=body.tool,
        arguments=body.arguments,
        channel=body.channel,
    )
    if result.approval is not None:
        approval = result.approval
        return {
            "status": "pending",
            "approval_id": approval.id,
            "approval": approval.model_dump(mode="json"),
        }
    response = {"status": result.status}
    if result.source:
        response["source"] = result.source
    return response


@router.get("/pending")
def list_pending(channel: str | None = None):
    svc = _get_service()
    pending = svc.list_pending(channel=channel)
    return [item.model_dump(mode="json") for item in pending]


@router.get("/policies")
def list_policies():
    svc = _get_service()
    return svc.list_policies()


@router.delete("/policies")
def clear_policies(body: ClearPoliciesBody):
    svc = _get_service()
    removed = svc.clear_policies(agent=body.agent, tool=body.tool)
    return {"removed": removed}


@router.get("/{approval_id}")
def get_approval(approval_id: str):
    svc = _get_service()
    approval = svc.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    return approval.model_dump(mode="json")


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
