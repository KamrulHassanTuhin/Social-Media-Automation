from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.config.settings import get_settings


@dataclass
class Job:
    id: str
    job_type: str
    workspace_id: str
    payload: dict
    status: str = "QUEUED"
    retry_count: int = 0
    max_retries: int = 3
    scheduled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    last_error: str | None = None
    idempotency_key: str | None = None


class InMemoryJobQueue:
    """Development queue with the same retry/idempotency semantics as the DB queue."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._by_idempotency: dict[str, str] = {}

    def enqueue(self, job_type: str, workspace_id: str, payload: dict, idempotency_key: str | None = None, scheduled_at: datetime | None = None) -> Job:
        if idempotency_key and idempotency_key in self._by_idempotency:
            return self._jobs[self._by_idempotency[idempotency_key]]
        job = Job(str(uuid4()), job_type, workspace_id, payload, scheduled_at=scheduled_at or datetime.now(timezone.utc), idempotency_key=idempotency_key)
        self._jobs[job.id] = job
        if idempotency_key:
            self._by_idempotency[idempotency_key] = job.id
        return job

    def claim_next(self) -> Job | None:
        now = datetime.now(timezone.utc)
        candidates = [job for job in self._jobs.values() if job.status in {"QUEUED", "RETRY_SCHEDULED"} and job.scheduled_at <= now]
        if not candidates:
            return None
        job = sorted(candidates, key=lambda candidate: candidate.scheduled_at)[0]
        job.status = "PROCESSING"
        job.started_at = now
        return job

    def complete(self, job: Job) -> Job:
        job.status = "SUCCEEDED"
        job.completed_at = datetime.now(timezone.utc)
        return job

    def fail(self, job: Job, error: str) -> Job:
        job.retry_count += 1
        job.last_error = error
        if job.retry_count <= job.max_retries:
            job.status = "RETRY_SCHEDULED"
            job.scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=(2 ** (job.retry_count - 1)))
        else:
            job.status = "DEAD_LETTER"
            job.completed_at = datetime.now(timezone.utc)
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)


class SupabaseJobQueue:
    """Persistent queue adapter. Claiming is performed by a Postgres RPC using SKIP LOCKED."""

    def __init__(self, url: str, service_role_key: str, worker_id: str = "api-worker") -> None:
        from supabase import Client, create_client

        self.client: Client = create_client(url, service_role_key)
        self.worker_id = worker_id

    def enqueue(self, job_type: str, workspace_id: str, payload: dict, idempotency_key: str | None = None, scheduled_at: datetime | None = None) -> Job:
        if idempotency_key:
            existing = self.client.table("job_queue").select("*").eq("idempotency_key", idempotency_key).maybe_single().execute()
            if existing.data:
                return self._from_row(existing.data)
        result = self.client.table("job_queue").insert({"workspace_id": workspace_id, "type": job_type, "payload": payload, "idempotency_key": idempotency_key, "scheduled_at": (scheduled_at or datetime.now(timezone.utc)).isoformat()}).execute()
        return self._from_row(result.data[0])

    def claim_next(self) -> Job | None:
        result = self.client.rpc("claim_next_job", {"worker_id": self.worker_id, "visibility_seconds": 300}).execute()
        row = result.data
        if isinstance(row, list):
            row = row[0] if row else None
        return self._from_row(row) if row else None

    def complete(self, job: Job) -> Job:
        self.client.rpc("complete_job", {"job_id": job.id}).execute()
        job.status = "SUCCEEDED"
        job.completed_at = datetime.now(timezone.utc)
        return job

    def fail(self, job: Job, error: str) -> Job:
        retry_count = job.retry_count + 1
        if retry_count <= job.max_retries:
            status = "RETRY_SCHEDULED"
            scheduled_at = datetime.now(timezone.utc) + timedelta(minutes=2 ** (retry_count - 1))
        else:
            status = "DEAD_LETTER"
            scheduled_at = datetime.now(timezone.utc)
        self.client.table("job_queue").update({"status": status, "retry_count": retry_count, "scheduled_at": scheduled_at.isoformat(), "error": error, "visibility_timeout_at": None}).eq("id", job.id).execute()
        job.status, job.retry_count, job.scheduled_at, job.last_error = status, retry_count, scheduled_at, error
        return job

    def get(self, job_id: str) -> Job | None:
        result = self.client.table("job_queue").select("*").eq("id", job_id).maybe_single().execute()
        return self._from_row(result.data) if result.data else None

    @staticmethod
    def _from_row(row: dict) -> Job:
        return Job(str(row["id"]), row["type"], str(row["workspace_id"]), row.get("payload") or {}, row.get("status", "QUEUED"), int(row.get("retry_count") or 0), int(row.get("max_retries") or 3), datetime.fromisoformat(row["scheduled_at"].replace("Z", "+00:00")), datetime.fromisoformat(row["started_at"].replace("Z", "+00:00")) if row.get("started_at") else None, datetime.fromisoformat(row["completed_at"].replace("Z", "+00:00")) if row.get("completed_at") else None, row.get("error"), row.get("idempotency_key"))


def build_job_queue():
    settings = get_settings()
    if settings.app_env == "local":
        return InMemoryJobQueue()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required outside local mode.")
    return SupabaseJobQueue(settings.supabase_url, settings.supabase_service_role_key)


job_queue = build_job_queue()
