from __future__ import annotations

from fastapi import HTTPException, status

from app.auth.dependencies import CurrentUser


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "SUPER_ADMIN": {"CREATE_CONTENT", "GENERATE_COPY", "APPROVE_CONTENT", "PUBLISH_CONTENT", "MANAGE_WORKSPACE", "MANAGE_INTEGRATIONS"},
    "WORKSPACE_ADMIN": {"CREATE_CONTENT", "GENERATE_COPY", "APPROVE_CONTENT", "PUBLISH_CONTENT", "MANAGE_WORKSPACE", "MANAGE_INTEGRATIONS"},
    "MANAGER": {"CREATE_CONTENT", "GENERATE_COPY", "APPROVE_CONTENT", "PUBLISH_CONTENT"},
    "TEAM_MEMBER": {"CREATE_CONTENT", "GENERATE_COPY"},
    "REVIEWER": {"APPROVE_CONTENT"},
    "PUBLISHER": {"PUBLISH_CONTENT"},
    "READ_ONLY": set(),
}


def permissions_for(roles: tuple[str, ...]) -> set[str]:
    permissions: set[str] = set()
    for role in roles:
        permissions.update(ROLE_PERMISSIONS.get(role, set()))
    return permissions


def require_permission(context: tuple[str, CurrentUser], permission: str) -> tuple[str, CurrentUser]:
    workspace_id, current_user = context
    if permission not in permissions_for(current_user.roles):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"code": "PERMISSION_DENIED", "message": f"The current workspace role cannot perform {permission.lower().replace('_', ' ')}."})
    return workspace_id, current_user
