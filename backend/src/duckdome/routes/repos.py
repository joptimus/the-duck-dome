"""REST endpoints for repo management.

Ports the four repo endpoints from agentchattr:
  GET  /api/repos       — list sources and discovered repos
  POST /api/repos/add   — add a repo source path
  POST /api/repos/remove — hide a repo and remove its source
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from duckdome.services.repo_service import RepoService

router = APIRouter(prefix="/api/repos", tags=["repos"])

_service: RepoService | None = None


def init(service: RepoService) -> None:
    global _service
    _service = service


def _get_service() -> RepoService:
    assert _service is not None
    return _service


class AddRepoRequest(BaseModel):
    path: str


class RemoveRepoRequest(BaseModel):
    path: str


@router.get("")
def list_repos():
    svc = _get_service()
    return {
        "sources": svc.list_sources(),
        "repos": svc.collect_repos(),
    }


@router.post("/add")
def add_repo(body: AddRepoRequest):
    svc = _get_service()
    try:
        source = svc.add_source(body.path)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return {"ok": True, "source": source}


@router.post("/remove")
def remove_repo(body: RemoveRepoRequest):
    svc = _get_service()
    svc.remove_source(body.path)
    return {"ok": True}
