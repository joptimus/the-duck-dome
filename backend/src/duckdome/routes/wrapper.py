from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from duckdome.services.channel_service import ChannelService
from duckdome.services.wrapper_service import WrapperService

router = APIRouter(prefix="/api/wrapper", tags=["wrapper"])

_service: WrapperService | None = None
_channel_service: ChannelService | None = None


def init(service: WrapperService, channel_service: ChannelService | None = None) -> None:
    global _service, _channel_service
    _service = service
    _channel_service = channel_service


def _get_service() -> WrapperService:
    assert _service is not None
    return _service


class StartRequest(BaseModel):
    agent_type: str = Field(min_length=1)
    channel: str = ""
    cwd: str | None = None


class TriggerRequest(BaseModel):
    agent_type: str = Field(min_length=1)
    sender: str = Field(min_length=1)
    text: str = Field(min_length=1)
    channel: str = Field(min_length=1)


class StopRequest(BaseModel):
    agent_type: str = Field(min_length=1)
    channel: str = ""


@router.post("/start", status_code=200)
def start_agent(body: StartRequest):
    svc = _get_service()
    started = svc.start_agent(body.agent_type, cwd=body.cwd, channel_id=body.channel)
    return {"started": started, "agent_type": body.agent_type, "channel": body.channel}


@router.post("/stop", status_code=200)
def stop_agent(body: StopRequest):
    svc = _get_service()
    stopped = svc.stop_agent(body.agent_type, channel_id=body.channel)
    return {"stopped": stopped, "agent_type": body.agent_type, "channel": body.channel}


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


class BootChannelRequest(BaseModel):
    channel: str = Field(min_length=1)


@router.post("/boot-channel", status_code=200)
def boot_channel(body: BootChannelRequest):
    """Start all available agents for a channel and tell them to greet."""
    import shutil

    svc = _get_service()
    started = []
    for agent_type in ["claude", "codex", "gemini"]:
        if not shutil.which(agent_type):
            continue
        if svc.is_running(agent_type, channel_id=body.channel):
            started.append(agent_type)
            continue

        # Register agent in channel store first (synchronous) so the
        # frontend sees them immediately on the next agents fetch.
        if _channel_service:
            try:
                _channel_service.add_agent(body.channel, agent_type)
            except Exception:
                pass  # already exists or channel not found

        svc.trigger(
            agent_type=agent_type,
            sender="system",
            text=(
                "You just joined this channel. Read the latest messages for context. "
                "Then send a short, unique greeting to let everyone know you're here. "
                "Be yourself — keep it natural and brief."
            ),
            channel=body.channel,
        )
        started.append(agent_type)
    return {"channel": body.channel, "started": started}


@router.get("/status", status_code=200)
def list_running():
    svc = _get_service()
    running = svc.list_running()
    agents = {}
    for agent_type in running:
        details = svc.get_agent_details(agent_type)
        agents[agent_type] = details or {}
    return {"running": running, "agents": agents}


@router.get("/status/{agent_type}", status_code=200)
def agent_status(agent_type: str):
    svc = _get_service()
    details = svc.get_agent_details(agent_type)
    if details is None:
        return {"running": False, "agent_type": agent_type}
    return {"running": True, "agent_type": agent_type, **details}
