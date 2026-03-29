from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from duckdome.services.trigger_service import TriggerService

router = APIRouter(tags=["triggers"])

_service: TriggerService | None = None


def init(service: TriggerService) -> None:
    global _service
    _service = service


def _get_service() -> TriggerService:
    assert _service is not None
    return _service


# --- Request models ---

class RegisterRequest(BaseModel):
    channel_id: str = Field(min_length=1)
    agent_type: str = Field(min_length=1)


class HeartbeatRequest(BaseModel):
    channel_id: str = Field(min_length=1)
    agent_type: str = Field(min_length=1)


class DeregisterRequest(BaseModel):
    channel_id: str = Field(min_length=1)
    agent_type: str = Field(min_length=1)


class ClaimRequest(BaseModel):
    channel_id: str = Field(min_length=1)
    agent_type: str = Field(min_length=1)


class FailRequest(BaseModel):
    error: str = Field(min_length=1)


# --- Agent runtime endpoints ---

@router.post("/api/agents/register", status_code=200)
def register_agent(body: RegisterRequest):
    svc = _get_service()
    try:
        agent = svc.register_agent(
            channel_id=body.channel_id, agent_type=body.agent_type
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return agent.model_dump()


@router.post("/api/agents/heartbeat", status_code=200)
def heartbeat(body: HeartbeatRequest):
    svc = _get_service()
    agent = svc.heartbeat(
        channel_id=body.channel_id, agent_type=body.agent_type
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.model_dump()


@router.post("/api/agents/deregister", status_code=200)
def deregister_agent(body: DeregisterRequest):
    svc = _get_service()
    agent = svc.deregister_agent(
        channel_id=body.channel_id, agent_type=body.agent_type
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.model_dump()


# --- Trigger endpoints ---

@router.post("/api/triggers/claim", status_code=200)
def claim_trigger(body: ClaimRequest):
    svc = _get_service()
    trigger = svc.claim_trigger(
        channel_id=body.channel_id, agent_type=body.agent_type
    )
    if trigger is None:
        return {"trigger": None}
    return trigger.model_dump()


@router.post("/api/triggers/{trigger_id}/complete", status_code=200)
def complete_trigger(trigger_id: str):
    svc = _get_service()
    trigger = svc.complete_trigger(trigger_id)
    if trigger is None:
        raise HTTPException(
            status_code=404, detail="Trigger not found or not in claimed state"
        )
    return trigger.model_dump()


@router.post("/api/triggers/{trigger_id}/fail", status_code=200)
def fail_trigger(trigger_id: str, body: FailRequest):
    svc = _get_service()
    trigger = svc.fail_trigger(trigger_id, error=body.error)
    if trigger is None:
        raise HTTPException(
            status_code=404, detail="Trigger not found or not in claimed state"
        )
    return trigger.model_dump()


@router.get("/api/triggers", status_code=200)
def list_triggers(channel_id: str, status: str | None = None):
    svc = _get_service()
    triggers = svc.list_triggers(channel_id, status=status)
    return [t.model_dump() for t in triggers]
