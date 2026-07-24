import csv
import io
import re

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from app.auth.dependencies import CurrentUser, get_current_user, workspace_context
from app.auth.permissions import permissions_for, require_permission
from app.config.settings import get_settings
from app.jobs.outbox import notification_outbox
from app.jobs.queue import job_queue
from app.repositories.membership_factory import membership_repository
from app.repositories.workspace_factory import workspace_repository
from app.schemas.workspace import AuditRetentionPurge, AuditRetentionUpdate, InvitationEmailPreview, MemberInvite, MemberRoleUpdate, MemberStatusUpdate, ProjectCreate, ProjectUpdate
from app.services.invitation_email import build_invitation_email

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("/context", response_model=dict)
async def get_workspace_context(context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, current_user = context
    workspace_name = workspace_repository.get_workspace_name(workspace_id) or "Workspace"
    return {"success": True, "data": {"workspace_id": workspace_id, "workspace_name": workspace_name, "user_id": current_user.id, "email": current_user.email, "roles": list(current_user.roles), "permissions": sorted(permissions_for(current_user.roles))}, "error": None, "meta": {}}


@router.get("/projects", response_model=dict)
async def list_projects(include_archived: bool = Query(default=False), context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, _ = context
    if include_archived:
        require_permission(context, "MANAGE_WORKSPACE")
    return {"success": True, "data": [project.__dict__ for project in workspace_repository.list_projects(workspace_id, include_archived)], "error": None, "meta": {}}


@router.get("/members", response_model=dict)
async def list_members(context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, _ = context
    return {"success": True, "data": [member.__dict__ for member in workspace_repository.list_members(workspace_id)], "error": None, "meta": {}}


@router.get("/audit-log", response_model=dict)
async def list_audit_log(action: str | None = Query(default=None), entity_type: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=200), context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, _ = require_permission(context, "MANAGE_WORKSPACE")
    return {"success": True, "data": [record.__dict__ for record in workspace_repository.list_audit(workspace_id, limit, action, entity_type)], "error": None, "meta": {"filters": {"action": action, "entity_type": entity_type}}}


@router.get("/audit-log.csv")
async def export_audit_log(action: str | None = Query(default=None), entity_type: str | None = Query(default=None), context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, _ = require_permission(context, "MANAGE_WORKSPACE")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "actor_id", "action", "entity_type", "entity_id", "created_at"])
    for record in workspace_repository.list_audit(workspace_id, 200, action, entity_type):
        writer.writerow([record.id, record.actor_id, record.action, record.entity_type, record.entity_id or "", record.created_at])
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=nova-audit-log.csv"})


@router.get("/audit-retention", response_model=dict)
async def get_audit_retention(context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, _ = require_permission(context, "MANAGE_WORKSPACE")
    retention_days = workspace_repository.get_audit_retention(workspace_id)
    _, cutoff_at = workspace_repository.purge_audit(workspace_id, retention_days, dry_run=True)
    return {"success": True, "data": {"retention_days": retention_days, "cutoff_at": cutoff_at}, "error": None, "meta": {"destructive_action": False}}


@router.patch("/audit-retention", response_model=dict)
async def update_audit_retention(payload: AuditRetentionUpdate, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, current_user = require_permission(context, "MANAGE_WORKSPACE")
    retention_days = workspace_repository.set_audit_retention(workspace_id, payload.retention_days, current_user.id)
    _, cutoff_at = workspace_repository.purge_audit(workspace_id, retention_days, dry_run=True)
    return {"success": True, "data": {"retention_days": retention_days, "cutoff_at": cutoff_at}, "error": None, "meta": {"audit_logged": True}}


@router.post("/audit-log/retention/purge", response_model=dict)
async def purge_audit_log(payload: AuditRetentionPurge, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, current_user = require_permission(context, "MANAGE_WORKSPACE")
    retention_days = workspace_repository.get_audit_retention(workspace_id)
    eligible_count, cutoff_at = workspace_repository.purge_audit(workspace_id, retention_days, dry_run=not payload.confirm)
    if payload.confirm and eligible_count:
        workspace_repository.record_audit(workspace_id, current_user.id, "AUDIT_RETENTION_PURGED", "AUDIT_LOG", None, None, {"deleted_count": eligible_count, "retention_days": retention_days, "cutoff_at": cutoff_at})
    return {"success": True, "data": {"eligible_count": eligible_count, "deleted_count": eligible_count if payload.confirm else 0, "retention_days": retention_days, "cutoff_at": cutoff_at, "dry_run": not payload.confirm}, "error": None, "meta": {"destructive_action": payload.confirm, "audit_logged": bool(payload.confirm and eligible_count)}}


@router.post("/projects", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, current_user = require_permission(context, "MANAGE_WORKSPACE")
    slug = payload.slug or re.sub(r"[^a-z0-9]+", "-", payload.name.lower()).strip("-")
    project = workspace_repository.create_project(workspace_id, payload.name, slug, current_user.id)
    return {"success": True, "data": project.__dict__, "error": None, "meta": {"audit_logged": True}}


@router.patch("/projects/{project_id}", response_model=dict)
async def update_project(project_id: str, payload: ProjectUpdate, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, current_user = require_permission(context, "MANAGE_WORKSPACE")
    project = workspace_repository.update_project(workspace_id, project_id, payload.name, payload.slug, payload.status, current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail={"code": "PROJECT_NOT_FOUND", "message": "Workspace project was not found."})
    return {"success": True, "data": project.__dict__, "error": None, "meta": {"audit_logged": True}}


@router.post("/members/invite", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def invite_member(payload: MemberInvite, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, current_user = require_permission(context, "MANAGE_WORKSPACE")
    member = workspace_repository.invite_member(workspace_id, payload.email, payload.role, current_user.id)
    email = build_invitation_email(payload.email, "Content Studio", current_user.email or "A workspace admin", f"{get_settings().app_base_url}/invite/accept?workspace_id={workspace_id}")
    event = notification_outbox.enqueue(workspace_id, "EMAIL", {"to": payload.email, "subject": email.subject, "body": email.body_text, "template": "workspace_invitation"}, f"workspace-invite:{workspace_id}:{payload.email.lower()}", member.user_id)
    job_queue.enqueue("SEND_NOTIFICATION", workspace_id, {"event_id": event.id}, f"notification:{event.id}")
    return {"success": True, "data": member.__dict__, "error": None, "meta": {"audit_logged": True, "email_template": email.__dict__, "notification_id": event.id}}


@router.post("/invitations/preview", response_model=dict)
async def preview_invitation_email(payload: InvitationEmailPreview, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, current_user = require_permission(context, "MANAGE_WORKSPACE")
    email = build_invitation_email(payload.email, "Content Studio", current_user.email or "A workspace admin", f"{get_settings().app_base_url}/invite/accept?workspace_id={workspace_id}")
    return {"success": True, "data": email.__dict__, "error": None, "meta": {"delivery": "preview_only"}}


@router.patch("/members/{user_id}/role", response_model=dict)
async def update_member_role(user_id: str, payload: MemberRoleUpdate, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, current_user = require_permission(context, "MANAGE_WORKSPACE")
    if user_id == current_user.id:
        raise HTTPException(status_code=409, detail={"code": "SELF_ROLE_CHANGE_BLOCKED", "message": "Ask another workspace admin to change your own role."})
    member = workspace_repository.update_member_role(workspace_id, user_id, payload.role, current_user.id)
    if not member:
        raise HTTPException(status_code=404, detail={"code": "MEMBER_NOT_FOUND", "message": "Workspace member was not found."})
    return {"success": True, "data": member.__dict__, "error": None, "meta": {"audit_logged": True}}


@router.patch("/members/{user_id}/status", response_model=dict)
async def update_member_status(user_id: str, payload: MemberStatusUpdate, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, current_user = require_permission(context, "MANAGE_WORKSPACE")
    if user_id == current_user.id:
        raise HTTPException(status_code=409, detail={"code": "SELF_STATUS_CHANGE_BLOCKED", "message": "Ask another workspace admin to change your own access."})
    member = workspace_repository.update_member_status(workspace_id, user_id, payload.status, current_user.id)
    if not member:
        raise HTTPException(status_code=404, detail={"code": "MEMBER_NOT_FOUND", "message": "Workspace member was not found."})
    return {"success": True, "data": member.__dict__, "error": None, "meta": {"audit_logged": True, "soft_change": True}}


@router.post("/invitations/accept", response_model=dict)
async def accept_invitation(
    current_user: CurrentUser = Depends(get_current_user),
    x_workspace_id: str | None = Header(default=None),
):
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail={"code": "WORKSPACE_REQUIRED", "message": "X-Workspace-ID is required to accept an invitation."})
    membership = membership_repository.get(current_user.id, x_workspace_id)
    if not membership or membership.status != "INVITED":
        raise HTTPException(status_code=404, detail={"code": "INVITATION_NOT_FOUND", "message": "No pending invitation was found for this account."})
    member = workspace_repository.accept_invitation(x_workspace_id, current_user.id)
    if not member:
        raise HTTPException(status_code=404, detail={"code": "INVITATION_NOT_FOUND", "message": "No pending invitation was found for this account."})
    workspace_repository.record_audit(x_workspace_id, current_user.id, "INVITATION_ACCEPTED", "WORKSPACE_MEMBER", current_user.id, {"status": "INVITED"}, {"status": "ACTIVE"})
    return {"success": True, "data": member.__dict__, "error": None, "meta": {"audit_logged": True}}
