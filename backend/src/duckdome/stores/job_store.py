from __future__ import annotations

import json
import os
from pathlib import Path

from duckdome.models.job import Job


class JobStore:
    """Append-only JSONL job store with in-memory index."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._file = self._data_dir / "jobs.jsonl"
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._load()

    def _load(self) -> None:
        if not self._file.exists():
            return
        with open(self._file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                job = Job(**json.loads(line))
                self._jobs[job.id] = job
                if job.id not in self._order:
                    self._order.append(job.id)

    def _save(self) -> None:
        tmp = self._file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for job_id in self._order:
                f.write(self._jobs[job_id].model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp.rename(self._file)

    def _append(self, job: Job) -> None:
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(job.model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())

    def add(self, job: Job) -> Job:
        if job.id in self._jobs:
            return self._jobs[job.id]
        self._jobs[job.id] = job
        self._order.append(job.id)
        self._append(job)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def update(self, job_id: str, job: Job) -> Job | None:
        if job_id not in self._jobs:
            return None
        if job.id != job_id:
            raise ValueError(f"job.id mismatch: expected {job_id}, got {job.id}")
        self._jobs[job_id] = job
        self._save()
        return job

    def list_jobs(
        self, channel: str | None = None, status: str | None = None
    ) -> list[Job]:
        result: list[Job] = []
        for job_id in self._order:
            job = self._jobs[job_id]
            if channel and job.channel != channel:
                continue
            if status and job.status != status:
                continue
            result.append(job)
        return result
