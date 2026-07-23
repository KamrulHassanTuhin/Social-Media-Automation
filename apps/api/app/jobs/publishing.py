from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class PublishingJobRecord:
    id: str
    workspace_id: str
    content_id: str
    channel: str
    idempotency_key: str
    status: str = "QUEUED"
    external_post_id: str | None = None
    external_post_url: str | None = None
    last_error: str | None = None
    scheduled_for: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class InMemoryPublishingStore:
    def __init__(self) -> None:
        self._jobs: dict[str, PublishingJobRecord] = {}
        self._by_key: dict[str, str] = {}

    def enqueue(self, workspace_id: str, content_id: str, channel: str, idempotency_key: str, scheduled_for: datetime | None = None) -> PublishingJobRecord:
        if idempotency_key in self._by_key:
            return self._jobs[self._by_key[idempotency_key]]
        job = PublishingJobRecord(str(uuid4()), workspace_id, content_id, channel, idempotency_key, scheduled_for=scheduled_for)
        self._jobs[job.id] = job
        self._by_key[idempotency_key] = job.id
        return job

    def for_content(self, content_id: str) -> list[PublishingJobRecord]:
        return [job for job in self._jobs.values() if job.content_id == content_id]

    def get(self, job_id: str) -> PublishingJobRecord | None:
        return self._jobs.get(job_id)

    def mark_failed(self, job_id: str, error: str) -> PublishingJobRecord | None:
        job = self._jobs.get(job_id)
        if job:
            job.status = "FAILED"
            job.last_error = error
        return job

    def mark_retry(self, job_id: str) -> PublishingJobRecord | None:
        job = self._jobs.get(job_id)
        if job:
            job.status = "QUEUED"
            job.last_error = None
        return job


publishing_store = InMemoryPublishingStore()
