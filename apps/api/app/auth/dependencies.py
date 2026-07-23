from __future__ import annotations

from dataclasses import dataclass, replace

import jwt
from fastapi import Depends, Header, HTTPException, status

from app.config.settings import Settings, get_settings
from app.repositories.membership_factory import membership_repository


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str | None
    workspace_ids: tuple[str, ...]
    roles: tuple[str, ...]
    is_demo: bool = False


def _unauthorized(message: str = "A valid bearer token is required.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"code": "UNAUTHORIZED", "message": message})


def _decode_token(token: str, settings: Settings) -> CurrentUser:
    if settings.app_env == "local" and token == "demo":
        return CurrentUser("user_demo", "demo@nova.local", ("ws_demo",), ("WORKSPACE_ADMIN",), True)

    if not settings.supabase_jwt_secret:
        raise _unauthorized("Supabase JWT verification is not configured.")
    try:
        claims = jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated")
    except jwt.PyJWTError as exc:
        raise _unauthorized("The bearer token is invalid or expired.") from exc

    metadata = claims.get("app_metadata") or {}
    raw_workspaces = metadata.get("workspace_ids") or claims.get("workspace_ids") or []
    raw_roles = metadata.get("roles") or claims.get("roles") or []
    workspace_ids = tuple(str(value) for value in raw_workspaces if value)
    roles = tuple(str(value) for value in raw_roles if value)
    return CurrentUser(str(claims["sub"]), claims.get("email"), workspace_ids, roles)


async def get_current_user(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    if not authorization:
        if settings.app_env == "local":
            return CurrentUser("user_demo", "demo@nova.local", ("ws_demo",), ("WORKSPACE_ADMIN",), True)
        raise _unauthorized()
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized()
    return _decode_token(token, settings)


def workspace_context(
    current_user: CurrentUser = Depends(get_current_user),
    x_workspace_id: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> tuple[str, CurrentUser]:
    workspace_id = x_workspace_id or (current_user.workspace_ids[0] if current_user.workspace_ids else None)
    if not workspace_id:
        raise HTTPException(status_code=403, detail={"code": "WORKSPACE_ACCESS_DENIED", "message": "User is not a member of this workspace."})
    if settings.app_env == "local" and current_user.is_demo:
        if workspace_id != "ws_demo":
            raise HTTPException(status_code=403, detail={"code": "WORKSPACE_ACCESS_DENIED", "message": "Demo user is scoped to the demo workspace."})
        return workspace_id, current_user
    membership = membership_repository.get(current_user.id, workspace_id)
    if not membership or membership.status != "ACTIVE":
        raise HTTPException(status_code=403, detail={"code": "WORKSPACE_ACCESS_DENIED", "message": "User is not an active member of this workspace."})
    return workspace_id, replace(current_user, workspace_ids=(workspace_id,), roles=(membership.role,))
