from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from duckdome.services.runner_service import RunnerService

router = APIRouter(prefix="/api/runners", tags=["runners"])

_service: RunnerService | None = None


def init(service: RunnerService) -> None:
    global _service
    _service = service


def _get_service() -> RunnerService:
    assert _service is not None
    return _service


class ExecuteRequest(BaseModel):
    channel_id: str = Field(min_length=1)
    agent_type: str = Field(default="claude", min_length=1)


@router.post("/execute", status_code=200)
def execute(body: ExecuteRequest):
    svc = _get_service()
    run = svc.execute_next(
        channel_id=body.channel_id,
        agent_type=body.agent_type,
    )
    if run is None:
        return {"run": None, "reason": "no pending triggers"}
    return run.model_dump()
