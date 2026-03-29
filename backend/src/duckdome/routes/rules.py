from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from duckdome.services.rule_service import RuleService

router = APIRouter(prefix="/api/rules", tags=["rules"])

_service: RuleService | None = None


def init(service: RuleService) -> None:
    global _service
    _service = service


def _get_service() -> RuleService:
    assert _service is not None
    return _service


class ProposeRuleBody(BaseModel):
    text: str = Field(min_length=1, max_length=160)
    author: str | None = None
    reason: str | None = Field(default=None, max_length=240)


class EditRuleBody(BaseModel):
    text: str = Field(min_length=1, max_length=160)


@router.get("")
def list_rules():
    svc = _get_service()
    return [rule.model_dump() for rule in svc.list_all()]


@router.get("/active")
def list_active_rules():
    svc = _get_service()
    return [rule.model_dump() for rule in svc.list_active()]


@router.get("/freshness")
def get_freshness():
    svc = _get_service()
    return {"epoch": svc.get_epoch()}


@router.post("", status_code=201)
def propose_rule(body: ProposeRuleBody):
    svc = _get_service()
    rule = svc.propose(text=body.text, author=body.author, reason=body.reason)
    return rule.model_dump()


@router.patch("/{rule_id}")
def edit_rule(rule_id: str, body: EditRuleBody):
    svc = _get_service()
    result = svc.edit(rule_id, text=body.text)
    if result is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result.model_dump()


@router.post("/{rule_id}/activate")
def activate_rule(rule_id: str):
    svc = _get_service()
    result = svc.activate(rule_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result.model_dump()


@router.post("/{rule_id}/archive")
def archive_rule(rule_id: str):
    svc = _get_service()
    result = svc.deactivate(rule_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result.model_dump()
