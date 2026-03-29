from __future__ import annotations

from fastapi import APIRouter, HTTPException

from duckdome.services.message_service import MessageService

router = APIRouter(prefix="/api/deliveries", tags=["deliveries"])

_service: MessageService | None = None


def init(service: MessageService) -> None:
    global _service
    _service = service


def _get_service() -> MessageService:
    assert _service is not None
    return _service


VALID_STATES = {"open", "sent", "seen", "responded", "resolved", "timeout"}


@router.get("")
def list_deliveries(state: str = "open"):
    if state not in VALID_STATES:
        raise HTTPException(status_code=422, detail=f"Invalid state: {state}")
    svc = _get_service()
    if state == "open":
        return [m.model_dump() for m in svc.list_open_deliveries()]
    else:
        return [m.model_dump() for m in svc.list_by_delivery_state(state)]
