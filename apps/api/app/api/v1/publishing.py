from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import CurrentUser, workspace_context
from app.jobs.outbox import notification_outbox
from app.jobs.publishing import publishing_store
from app.jobs.queue import job_queue
from app.jobs.worker import JobWorker
from app.repositories.factory import content_repository

router = APIRouter(prefix="/publishing-jobs", tags=["publishing"])


@router.get("/content/{content_id}", response_model=dict)
async def list_publishing_jobs(content_id: str, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, _ = context
    if not content_repository.get(workspace_id, content_id):
        raise HTTPException(status_code=404, detail={"code": "CONTENT_NOT_FOUND", "message": "Content item was not found."})
    jobs = [job for job in publishing_store.for_content(content_id) if job.workspace_id == workspace_id]
    return {"success": True, "data": [{"id": job.id, "channel": job.channel, "status": job.status, "idempotency_key": job.idempotency_key, "external_post_id": job.external_post_id, "external_post_url": job.external_post_url, "last_error": job.last_error, "scheduled_for": job.scheduled_for.isoformat() if job.scheduled_for else None, "created_at": job.created_at.isoformat()} for job in jobs], "error": None, "meta": {}}


@router.post("/{job_id}/retry", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def retry_publishing_job(job_id: str, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, current_user = context
    job = publishing_store.get(job_id)
    if not job or job.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail={"code": "PUBLISHING_JOB_NOT_FOUND", "message": "Publishing job was not found."})
    if job.status != "FAILED":
        raise HTTPException(status_code=409, detail={"code": "JOB_NOT_RETRYABLE", "message": "Only failed publishing jobs can be retried."})
    publishing_store.mark_retry(job.id)
    queued = job_queue.enqueue("PUBLISH_CHANNEL", workspace_id, {"content_id": job.content_id, "channel": job.channel, "actor_id": current_user.id, "publishing_job_id": job.id}, f"publish-retry:{job.id}:{job.created_at.isoformat()}")
    if current_user.is_demo:
        JobWorker(job_queue, notification_outbox, content_repository, publishing_store).drain_local()
    return {"success": True, "data": {"job_id": queued.id, "publishing_job_id": job.id, "status": job.status}, "error": None, "meta": {"worker_inline": current_user.is_demo}}
