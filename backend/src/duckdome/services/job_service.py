from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING

from duckdome.models.job import Job, JobStatus
from duckdome.stores.job_store import JobStore
from duckdome.ws.events import JOB_MESSAGE_ADDED, JOB_UPDATED

if TYPE_CHECKING:
    from duckdome.ws.manager import ConnectionManager

_UNSET = object()


class JobService:
    def __init__(
        self,
        store: JobStore,
        ws_manager: ConnectionManager | None = None,
    ) -> None:
        self._store = store
        self._ws_manager = ws_manager

    def _broadcast(self, event: dict) -> None:
        if self._ws_manager is None:
            return
        self._ws_manager.broadcast_sync(event)

    def create(
        self,
        *,
        title: str,
        channel: str,
        created_by: str,
        body: str = "",
        assignee: str | None = None,
    ) -> Job:
        now = time.time()
        job = Job(
            title=title,
            body=body,
            channel=channel,
            assignee=assignee,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._store.add(job)
        self._broadcast({"type": JOB_UPDATED, "job": job.model_dump(mode="json")})
        return job

    def list_jobs(
        self, channel: str | None = None, status: str | None = None
    ) -> list[Job]:
        return self._store.list_jobs(channel=channel, status=status)

    def update(
        self,
        job_id: str,
        *,
        title: str | object = _UNSET,
        body: str | object = _UNSET,
        status: str | object = _UNSET,
        assignee: str | None | object = _UNSET,
    ) -> Job | None:
        job = self._store.get(job_id)
        if job is None:
            return None

        if title is not _UNSET:
            job.title = str(title)
        if body is not _UNSET:
            job.body = str(body)
        if status is not _UNSET:
            normalized = str(status).strip().lower()
            if normalized not in (
                JobStatus.OPEN.value,
                JobStatus.DONE.value,
                JobStatus.ARCHIVED.value,
            ):
                raise ValueError(f"Invalid job status: {status}")
            job.status = JobStatus(normalized)
        if assignee is not _UNSET:
            job.assignee = None if assignee is None else str(assignee)

        job.updated_at = time.time()
        updated = self._store.update(job_id, job)
        if updated:
            self._broadcast({"type": JOB_UPDATED, "job": updated.model_dump(mode="json")})
        return updated

    def list_messages(self, job_id: str) -> list[dict] | None:
        job = self._store.get(job_id)
        if job is None:
            return None
        return list(job.messages)

    def post_message(
        self,
        *,
        job_id: str,
        sender: str,
        text: str,
        type: str = "chat",
    ) -> dict | None:
        job = self._store.get(job_id)
        if job is None:
            return None

        message = {
            "id": str(uuid.uuid4()),
            "sender": sender,
            "text": text,
            "type": type,
            "timestamp": time.time(),
        }
        job.messages.append(message)
        job.updated_at = time.time()
        self._store.update(job_id, job)
        self._broadcast(
            {"type": JOB_MESSAGE_ADDED, "job_id": job_id, "message": message}
        )
        self._broadcast({"type": JOB_UPDATED, "job": job.model_dump(mode="json")})
        return message
