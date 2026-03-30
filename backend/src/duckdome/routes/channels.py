from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from duckdome.services.channel_service import ChannelService

router = APIRouter(prefix="/api/channels", tags=["channels"])

_service: ChannelService | None = None


def init(service: ChannelService) -> None:
    global _service
    _service = service


def _get_service() -> ChannelService:
    assert _service is not None
    return _service


class CreateChannelRequest(BaseModel):
    name: str = Field(min_length=1)
    type: str = Field(min_length=1)
    repo_path: str | None = None


class AddAgentRequest(BaseModel):
    agent_type: str = Field(min_length=1)


@router.post("", status_code=201)
def create_channel(body: CreateChannelRequest):
    svc = _get_service()
    try:
        ch = svc.create_channel(
            name=body.name, type=body.type, repo_path=body.repo_path
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return ch.model_dump()


@router.get("")
def list_channels():
    svc = _get_service()
    return [ch.model_dump() for ch in svc.list_channels()]


@router.get("/{channel_id}")
def get_channel(channel_id: str):
    svc = _get_service()
    ch = svc.get_channel(channel_id)
    if ch is None:
        raise HTTPException(status_code=404, detail="Channel not found")
    return ch.model_dump()


@router.get("/{channel_id}/agents")
def list_agents(channel_id: str):
    svc = _get_service()
    if not svc.validate_channel(channel_id):
        raise HTTPException(status_code=404, detail="Channel not found")
    agents = svc.list_agents(channel_id)
    return [a.model_dump() for a in agents]


@router.post("/{channel_id}/agents", status_code=201)
def add_agent(channel_id: str, body: AddAgentRequest):
    svc = _get_service()
    try:
        inst = svc.add_agent(channel_id=channel_id, agent_type=body.agent_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return inst.model_dump()


@router.delete("/{channel_id}/agents/{agent_type}", status_code=200)
def remove_agent(channel_id: str, agent_type: str):
    svc = _get_service()
    try:
        removed = svc.remove_agent(channel_id=channel_id, agent_type=agent_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if not removed:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"removed": True}
