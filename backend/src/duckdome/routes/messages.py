from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from duckdome.services.message_service import MessageService

router = APIRouter(prefix="/api/messages", tags=["messages"])

# Will be set by app factory
_service: MessageService | None = None


def init(service: MessageService) -> None:
    global _service
    _service = service


def _get_service() -> MessageService:
    assert _service is not None
    return _service


class SendMessageRequest(BaseModel):
    text: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    sender: str = Field(min_length=1)


class AgentSeenRequest(BaseModel):
    agent_name: str = Field(min_length=1)


class AgentRespondedRequest(BaseModel):
    agent_name: str = Field(min_length=1)
    response_id: str = Field(min_length=1)


class AgentReadRequest(BaseModel):
    agent_name: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    read_up_to_id: str = Field(min_length=1)


class AgentResponseRequest(BaseModel):
    agent_name: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    response_id: str = Field(min_length=1)


@router.post("", status_code=201)
def send_message(body: SendMessageRequest):
    svc = _get_service()
    msg = svc.send(text=body.text, channel=body.channel, sender=body.sender)
    return msg.model_dump()


@router.get("")
def list_messages(channel: str, after: str | None = None):
    svc = _get_service()
    msgs = svc.list_messages(channel, after_id=after)
    return [m.model_dump() for m in msgs]


# Static routes MUST come before parameterized routes
@router.post("/agent-read")
def agent_read(body: AgentReadRequest):
    svc = _get_service()
    result = svc.process_agent_read(
        agent_name=body.agent_name,
        channel=body.channel,
        read_up_to_id=body.read_up_to_id,
    )
    return [m.model_dump() for m in result]


@router.post("/agent-response")
def agent_response(body: AgentResponseRequest):
    svc = _get_service()
    result = svc.process_agent_response(
        agent_name=body.agent_name,
        channel=body.channel,
        response_id=body.response_id,
    )
    return [m.model_dump() for m in result]


@router.post("/{msg_id}/seen")
def mark_seen(msg_id: str, body: AgentSeenRequest):
    svc = _get_service()
    result = svc.mark_seen(msg_id, agent_name=body.agent_name)
    if result is None:
        raise HTTPException(status_code=404, detail="Message not found or agent not targeted")
    return result.model_dump()


@router.post("/{msg_id}/responded")
def mark_responded(msg_id: str, body: AgentRespondedRequest):
    svc = _get_service()
    result = svc.mark_responded(msg_id, agent_name=body.agent_name, response_id=body.response_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Message not found or not in seen/timeout state")
    return result.model_dump()
