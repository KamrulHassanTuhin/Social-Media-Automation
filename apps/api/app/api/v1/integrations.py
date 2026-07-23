from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth.dependencies import CurrentUser, workspace_context
from app.auth.permissions import require_permission
from app.repositories.integrations import integration_repository
from app.schemas.integrations import IntegrationConnect

router = APIRouter(prefix="/integrations", tags=["integrations"])
ADMIN_ROLES = {"SUPER_ADMIN", "WORKSPACE_ADMIN"}


def require_admin(context: tuple[str, CurrentUser]) -> tuple[str, CurrentUser]:
    workspace_id, current_user = require_permission(context, "MANAGE_INTEGRATIONS")
    if not current_user.is_demo and not ADMIN_ROLES.intersection(current_user.roles):
        raise HTTPException(status_code=403, detail={"code": "INTEGRATION_ADMIN_REQUIRED", "message": "Only workspace admins can manage integrations."})
    return workspace_id, current_user


def serialize(summary) -> dict:
    return {"provider": summary.provider, "status": summary.status, "settings": summary.settings, "last_tested_at": summary.last_tested_at, "last_successful_use": summary.last_successful_use, "last_error": summary.last_error}


@router.get("", response_model=dict)
async def list_integrations(context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, _ = context
    return {"success": True, "data": [serialize(item) for item in integration_repository.list(workspace_id)], "error": None, "meta": {}}


@router.post("/{provider}/connect", response_model=dict)
async def connect_integration(provider: str, payload: IntegrationConnect, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, _ = require_admin(context)
    summary = integration_repository.connect(workspace_id, provider, payload.credentials, payload.settings)
    return {"success": True, "data": serialize(summary), "error": None, "meta": {"credentials_persisted": True, "credentials_returned": False}}


@router.post("/{provider}/test", response_model=dict)
async def test_integration(provider: str, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, _ = require_admin(context)
    summary = integration_repository.test(workspace_id, provider)
    return {"success": summary.status == "CONNECTED", "data": serialize(summary), "error": None if summary.status == "CONNECTED" else {"code": "INTEGRATION_NOT_CONNECTED", "message": "Integration is not configured."}, "meta": {}}


@router.post("/{provider}/disconnect", response_model=dict)
async def disconnect_integration(provider: str, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, _ = require_admin(context)
    summary = integration_repository.disconnect(workspace_id, provider)
    return {"success": True, "data": serialize(summary), "error": None, "meta": {"credentials_returned": False}}
