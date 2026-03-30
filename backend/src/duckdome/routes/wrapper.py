from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from duckdome.services.wrapper_service import WrapperService

router = APIRouter(prefix="/api/wrapper", tags=["wrapper"])

_service: WrapperService | None = None


def init(service: WrapperService) -> None:
    global _service
    _service = service


def _get_service() -> WrapperService:
    assert _service is not None
    return _service


class StartRequest(BaseModel):
    agent_type: str = Field(min_length=1)
    cwd: str | None = None


class TriggerRequest(BaseModel):
    agent_type: str = Field(min_length=1)
    sender: str = Field(min_length=1)
    text: str = Field(min_length=1)
    channel: str = Field(min_length=1)


class StopRequest(BaseModel):
    agent_type: str = Field(min_length=1)


@router.post("/start", status_code=200)
def start_agent(body: StartRequest):
    svc = _get_service()
    started = svc.start_agent(body.agent_type, cwd=body.cwd)
    return {"started": started, "agent_type": body.agent_type}


@router.post("/stop", status_code=200)
def stop_agent(body: StopRequest):
    svc = _get_service()
    stopped = svc.stop_agent(body.agent_type)
    return {"stopped": stopped, "agent_type": body.agent_type}


@router.post("/trigger", status_code=200)
def trigger_agent(body: TriggerRequest):
    svc = _get_service()
    triggered = svc.trigger(
        agent_type=body.agent_type,
        sender=body.sender,
        text=body.text,
        channel=body.channel,
    )
    if not triggered:
        raise HTTPException(status_code=409, detail=f"Agent '{body.agent_type}' is not running")
    return {"triggered": True, "agent_type": body.agent_type}


@router.get("/status", status_code=200)
def list_running():
    svc = _get_service()
    return {"running": svc.list_running()}
