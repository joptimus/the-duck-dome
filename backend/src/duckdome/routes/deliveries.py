from __future__ import annotations

from fastapi import APIRouter

from duckdome.services.message_service import MessageService

router = APIRouter(prefix="/api/deliveries", tags=["deliveries"])

_service: MessageService | None = None


def init(service: MessageService) -> None:
    global _service
    _service = service


def _get_service() -> MessageService:
    assert _service is not None
    return _service


@router.get("")
def list_deliveries(state: str = "open"):
    svc = _get_service()
    if state == "open":
        sent = svc._store.list_by_delivery_state("sent")
        delivered = svc._store.list_by_delivery_state("delivered")
        # Deduplicate by id preserving order
        seen: set[str] = set()
        result = []
        for msg in sent + delivered:
            if msg.id not in seen:
                seen.add(msg.id)
                result.append(msg)
        return [m.model_dump() for m in result]
    else:
        msgs = svc._store.list_by_delivery_state(state)
        return [m.model_dump() for m in msgs]
