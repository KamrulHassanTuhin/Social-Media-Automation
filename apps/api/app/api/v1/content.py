from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.dependencies import CurrentUser, get_current_user, workspace_context
from app.auth.permissions import require_permission
from app.domain.status import InvalidStatusTransition, PublishingReadiness, assert_transition
from app.jobs.outbox import notification_outbox
from app.jobs.publishing import publishing_store
from app.jobs.queue import job_queue
from app.jobs.worker import JobWorker
from app.services.idempotency import publishing_idempotency_key
from app.repositories.content import ApprovalRecord, new_content
from app.repositories.factory import content_repository
from app.schemas.content import ActionResponse, ApprovalAction, ContentCreate, ContentSummary, CopyUpdate, GenerateRequest, ScheduleRequest

router = APIRouter(prefix="/content", tags=["content"])


def to_summary(item) -> ContentSummary:
    return ContentSummary.model_validate(item, from_attributes=True)


@router.get("", response_model=dict)
async def list_content(search: str | None = Query(default=None, min_length=2), context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, _ = context
    return {"success": True, "data": [to_summary(item).model_dump(mode="json") for item in content_repository.list(workspace_id, search)], "error": None, "meta": {}}


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_content(payload: ContentCreate, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, current_user = require_permission(context, "CREATE_CONTENT")
    item = content_repository.add(new_content(workspace_id, payload.project_id, payload.topic), current_user.id)
    item.brief_status = payload.brief_status
    return {"success": True, "data": to_summary(item).model_dump(mode="json"), "error": None, "meta": {}}


@router.post("/{content_id}/generate", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def generate_content(content_id: str, payload: GenerateRequest, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, current_user = require_permission(context, "GENERATE_COPY")
    item = content_repository.get(workspace_id, content_id)
    if not item:
        raise HTTPException(status_code=404, detail={"code": "CONTENT_NOT_FOUND", "message": "Content item was not found."})
    if item.brief_status != "BRIEF_READY":
        raise HTTPException(status_code=400, detail={"code": "BRIEF_NOT_READY", "message": "Only BRIEF_READY content can generate copy."})
    if item.automation_status in {"QUEUED", "GENERATING"} and not payload.force_regenerate:
        raise HTTPException(status_code=409, detail={"code": "GENERATION_ALREADY_RUNNING", "message": "A generation job is already active."})
    item.automation_status = "QUEUED"
    content_repository.update(item, current_user.id)
    job = job_queue.enqueue("GENERATE_SOCIAL_COPY", workspace_id, {"content_id": item.id, "channels": payload.channels, "provider": payload.provider, "actor_id": current_user.id}, f"generate:{item.id}:{','.join(sorted(payload.channels))}")
    if current_user.is_demo:
        JobWorker(job_queue, notification_outbox, content_repository).drain_local()
    return {"success": True, "data": ActionResponse(job_id=job.id, content_id=item.id, status="QUEUED").model_dump(), "error": None, "meta": {"provider": payload.provider, "mock": current_user.is_demo, "worker_inline": current_user.is_demo}}


@router.post("/{content_id}/approve", response_model=dict)
async def approve_content(content_id: str, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, current_user = require_permission(context, "APPROVE_CONTENT")
    item = content_repository.get(workspace_id, content_id)
    if not item:
        raise HTTPException(status_code=404, detail={"code": "CONTENT_NOT_FOUND", "message": "Content item was not found."})
    previous_status = item.automation_status
    try:
        assert_transition(item.automation_status, "APPROVED")
    except InvalidStatusTransition as exc:
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATUS_TRANSITION", "message": str(exc)}) from exc
    item.automation_status = "APPROVED"
    content_repository.update(item, current_user.id)
    content_repository.record_approval(ApprovalRecord(str(uuid4()), item.id, current_user.id, "APPROVED", None, previous_status, item.automation_status))
    return {"success": True, "data": ActionResponse(content_id=item.id, status=item.automation_status).model_dump(), "error": None, "meta": {}}


@router.get("/{content_id}/copies", response_model=dict)
async def list_copies(content_id: str, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, _ = context
    item = content_repository.get(workspace_id, content_id)
    if not item:
        raise HTTPException(status_code=404, detail={"code": "CONTENT_NOT_FOUND", "message": "Content item was not found."})
    versions = content_repository.list_copy_versions(content_id)
    return {"success": True, "data": [{"id": version.id, "channel": version.channel, "version": version.version, "body": version.body, "created_by": version.created_by, "created_at": version.created_at.isoformat()} for version in versions], "error": None, "meta": {}}


@router.patch("/copies/{copy_id}", response_model=dict)
async def update_copy(copy_id: str, payload: CopyUpdate, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    _, current_user = context
    updated = content_repository.update_copy(copy_id, payload.body, current_user.id)
    if not updated:
        raise HTTPException(status_code=404, detail={"code": "COPY_NOT_FOUND", "message": "Social copy was not found."})
    return {"success": True, "data": {"id": updated.id, "channel": updated.channel, "version": updated.version, "body": updated.body, "created_at": updated.created_at.isoformat()}, "error": None, "meta": {}}


@router.get("/{content_id}/approvals", response_model=dict)
async def list_approvals(content_id: str, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, _ = context
    if not content_repository.get(workspace_id, content_id):
        raise HTTPException(status_code=404, detail={"code": "CONTENT_NOT_FOUND", "message": "Content item was not found."})
    approvals = content_repository.list_approvals(content_id)
    return {"success": True, "data": [{"id": approval.id, "decision": approval.decision, "notes": approval.notes, "reviewer_id": approval.reviewer_id, "previous_status": approval.previous_status, "new_status": approval.new_status, "created_at": approval.created_at.isoformat()} for approval in approvals], "error": None, "meta": {}}


@router.post("/{content_id}/request-changes", response_model=dict)
async def request_changes(content_id: str, payload: ApprovalAction, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, current_user = require_permission(context, "APPROVE_CONTENT")
    item = content_repository.get(workspace_id, content_id)
    if not item:
        raise HTTPException(status_code=404, detail={"code": "CONTENT_NOT_FOUND", "message": "Content item was not found."})
    previous_status = item.automation_status
    try:
        assert_transition(previous_status, "CHANGES_REQUESTED")
    except InvalidStatusTransition as exc:
        raise HTTPException(status_code=409, detail={"code": "INVALID_STATUS_TRANSITION", "message": str(exc)}) from exc
    item.automation_status = "CHANGES_REQUESTED"
    content_repository.update(item, current_user.id)
    content_repository.record_approval(ApprovalRecord(str(uuid4()), item.id, current_user.id, "CHANGES_REQUESTED", payload.notes, previous_status, item.automation_status))
    return {"success": True, "data": ActionResponse(content_id=item.id, status=item.automation_status).model_dump(), "error": None, "meta": {}}


@router.post("/{content_id}/publish", response_model=dict)
async def publish_content(content_id: str, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, current_user = require_permission(context, "PUBLISH_CONTENT")
    item = content_repository.get(workspace_id, content_id)
    if not item:
        raise HTTPException(status_code=404, detail={"code": "CONTENT_NOT_FOUND", "message": "Content item was not found."})
    readiness = PublishingReadiness(item.automation_status in {"APPROVED", "READY_TO_PUBLISH"}, bool(item.live_url), bool(item.publisher_id), bool(item.copies), item.has_media, True)
    if not readiness.ready:
        raise HTTPException(status_code=422, detail={"code": "PUBLISH_VALIDATION_FAILED", "message": "Publishing prerequisites are missing.", "details": {"missing": readiness.missing()}})
    if item.automation_status == "APPROVED":
        assert_transition(item.automation_status, "READY_TO_PUBLISH")
        item.automation_status = "READY_TO_PUBLISH"
    assert_transition(item.automation_status, "PUBLISHING")
    item.automation_status = "PUBLISHING"
    content_repository.update(item, current_user.id)
    channels = list(item.copies.keys())
    jobs = []
    worker = JobWorker(job_queue, notification_outbox, content_repository, publishing_store)
    for channel in channels:
        idempotency_key = publishing_idempotency_key(workspace_id, item.id, channel, 1, None)
        publishing_job = publishing_store.enqueue(workspace_id, item.id, channel, idempotency_key)
        jobs.append(publishing_job)
        job_queue.enqueue("PUBLISH_CHANNEL", workspace_id, {"content_id": item.id, "channel": channel, "actor_id": current_user.id, "publishing_job_id": publishing_job.id}, f"publish:{publishing_job.id}")
    if current_user.is_demo:
        worker.drain_local()
        completed = publishing_store.for_content(item.id)
        if completed and all(job.status == "SUCCEEDED" for job in completed):
            item.automation_status = "PUBLISHED"
            content_repository.update(item, current_user.id)
    return {"success": True, "data": {**ActionResponse(job_id=jobs[0].id if jobs else str(uuid4()), content_id=item.id, status=item.automation_status).model_dump(), "publishing_job_ids": [job.id for job in jobs]}, "error": None, "meta": {"provider": worker.integrations.publisher.name, "worker_inline": current_user.is_demo}}


@router.post("/{content_id}/schedule", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def schedule_content(content_id: str, payload: ScheduleRequest, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    from datetime import datetime, timezone

    workspace_id, current_user = require_permission(context, "PUBLISH_CONTENT")
    if payload.scheduled_for.tzinfo is None:
        raise HTTPException(status_code=422, detail={"code": "TIMEZONE_REQUIRED", "message": "scheduled_for must include a timezone."})
    if payload.scheduled_for <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail={"code": "SCHEDULE_IN_PAST", "message": "scheduled_for must be in the future."})
    item = content_repository.get(workspace_id, content_id)
    if not item:
        raise HTTPException(status_code=404, detail={"code": "CONTENT_NOT_FOUND", "message": "Content item was not found."})
    if item.automation_status == "APPROVED":
        assert_transition(item.automation_status, "READY_TO_PUBLISH")
        item.automation_status = "READY_TO_PUBLISH"
    if item.automation_status != "READY_TO_PUBLISH":
        raise HTTPException(status_code=409, detail={"code": "CONTENT_NOT_READY_TO_SCHEDULE", "message": "Only approved content can be scheduled."})
    if not item.copies:
        raise HTTPException(status_code=422, detail={"code": "NO_CHANNEL_COPY", "message": "At least one channel copy is required."})
    content_repository.update(item, current_user.id)
    jobs = []
    for channel in item.copies:
        idempotency_key = publishing_idempotency_key(workspace_id, item.id, channel, 1, payload.scheduled_for.isoformat())
        publishing_job = publishing_store.enqueue(workspace_id, item.id, channel, idempotency_key, payload.scheduled_for)
        jobs.append(publishing_job)
        job_queue.enqueue("PUBLISH_CHANNEL", workspace_id, {"content_id": item.id, "channel": channel, "actor_id": current_user.id, "publishing_job_id": publishing_job.id}, f"schedule:{publishing_job.id}", payload.scheduled_for)
    return {"success": True, "data": {"content_id": item.id, "status": item.automation_status, "scheduled_for": payload.scheduled_for.isoformat(), "publishing_job_ids": [job.id for job in jobs]}, "error": None, "meta": {"worker_inline": False}}
