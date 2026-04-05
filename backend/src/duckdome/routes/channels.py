from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from duckdome.services.channel_service import ChannelService
from duckdome.services.agent_permission_service import AgentPermissionService
from duckdome.services.wrapper_service import WrapperService
from duckdome.stores.message_store import MessageStore
from duckdome.ws.events import CHANNEL_DELETED

if TYPE_CHECKING:
    from duckdome.ws.manager import ConnectionManager

router = APIRouter(prefix="/api/channels", tags=["channels"])

_service: ChannelService | None = None
_permission_service: AgentPermissionService | None = None
_wrapper_service: WrapperService | None = None
_message_store: MessageStore | None = None
_ws: ConnectionManager | None = None


def init(
    service: ChannelService,
    permission_service: AgentPermissionService | None = None,
    wrapper_service: WrapperService | None = None,
    message_store: MessageStore | None = None,
    ws_manager: ConnectionManager | None = None,
) -> None:
    global _service, _permission_service, _wrapper_service, _message_store, _ws
    _service = service
    _permission_service = permission_service
    _wrapper_service = wrapper_service
    _message_store = message_store
    _ws = ws_manager


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
        raise HTTPException(status_code=422, detail=str(e)) from e
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


@router.delete("/{channel_id}", status_code=204)
def delete_channel(channel_id: str):
    svc = _get_service()
    try:
        deleted = svc.delete_channel(channel_id)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if not deleted:
        raise HTTPException(status_code=404, detail="Channel not found")
    # Clean up messages for the deleted channel
    if _message_store:
        _message_store.delete_by_channel(channel_id)
    # Broadcast deletion to connected clients
    if _ws:
        _ws.broadcast_sync({"type": CHANNEL_DELETED, "channel_id": channel_id})
    return None


@router.get("/{channel_id}/agents")
def list_agents(channel_id: str):
    svc = _get_service()
    if not svc.validate_channel(channel_id):
        raise HTTPException(status_code=404, detail="Channel not found")
    agents = svc.list_agents(channel_id)
    result = []
    for a in agents:
        data = a.model_dump()
        if _permission_service:
            data["permissions"] = _permission_service.get_agent_permissions(a.agent_type).model_dump(mode="json")
        if _wrapper_service:
            details = _wrapper_service.get_agent_details(a.agent_type, channel_id=channel_id)
            if details:
                data["pid"] = details.get("pid")
                data["started_at"] = details.get("started_at")
                data["running"] = True
            else:
                data["running"] = False
        result.append(data)
    return result


@router.post("/{channel_id}/agents", status_code=201)
def add_agent(channel_id: str, body: AddAgentRequest):
    svc = _get_service()
    try:
        inst = svc.add_agent(channel_id=channel_id, agent_type=body.agent_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return inst.model_dump()


@router.delete("/{channel_id}/agents/{agent_type}", status_code=200)
def remove_agent(channel_id: str, agent_type: str):
    svc = _get_service()
    try:
        removed = svc.remove_agent(channel_id=channel_id, agent_type=agent_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    if not removed:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"removed": True}
