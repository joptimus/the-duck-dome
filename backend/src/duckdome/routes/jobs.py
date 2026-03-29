from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from duckdome.services.job_service import JobService

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

_service: JobService | None = None


def init(service: JobService) -> None:
    global _service
    _service = service


def _get_service() -> JobService:
    assert _service is not None
    return _service


class CreateJobBody(BaseModel):
    title: str = Field(min_length=1)
    body: str = ""
    channel: str = Field(min_length=1)
    assignee: str | None = None
    created_by: str = Field(min_length=1)


class UpdateJobBody(BaseModel):
    title: str | None = None
    body: str | None = None
    status: str | None = None
    assignee: str | None = None


class JobMessageBody(BaseModel):
    sender: str = Field(min_length=1)
    text: str = Field(min_length=1)
    type: str = "chat"


@router.get("")
def list_jobs(channel: str | None = None, status: str | None = None):
    svc = _get_service()
    jobs = svc.list_jobs(channel=channel, status=status)
    return [job.model_dump(mode="json") for job in jobs]


@router.post("", status_code=201)
def create_job(body: CreateJobBody):
    svc = _get_service()
    job = svc.create(
        title=body.title,
        body=body.body,
        channel=body.channel,
        assignee=body.assignee,
        created_by=body.created_by,
    )
    return job.model_dump(mode="json")


@router.patch("/{job_id}")
def update_job(job_id: str, body: UpdateJobBody):
    svc = _get_service()
    kwargs = {}
    if "title" in body.model_fields_set:
        kwargs["title"] = body.title
    if "body" in body.model_fields_set:
        kwargs["body"] = body.body
    if "status" in body.model_fields_set:
        kwargs["status"] = body.status
    if "assignee" in body.model_fields_set:
        kwargs["assignee"] = body.assignee
    try:
        job = svc.update(job_id, **kwargs)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump(mode="json")


@router.get("/{job_id}/messages")
def list_job_messages(job_id: str):
    svc = _get_service()
    messages = svc.list_messages(job_id)
    if messages is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return messages


@router.post("/{job_id}/messages", status_code=201)
def post_job_message(job_id: str, body: JobMessageBody):
    svc = _get_service()
    message = svc.post_message(
        job_id=job_id,
        sender=body.sender,
        text=body.text,
        type=body.type,
    )
    if message is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return message
