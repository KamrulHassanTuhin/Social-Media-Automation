from typing import Literal

from pydantic import BaseModel, Field


WorkspaceRole = Literal["SUPER_ADMIN", "WORKSPACE_ADMIN", "MANAGER", "TEAM_MEMBER", "REVIEWER", "PUBLISHER", "READ_ONLY"]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str | None = Field(default=None, min_length=2, max_length=80)


class ProjectUpdate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=80)
    status: Literal["ACTIVE", "ARCHIVED"] = "ACTIVE"


class MemberInvite(BaseModel):
    email: str = Field(min_length=5, max_length=320)
    role: WorkspaceRole = "TEAM_MEMBER"


class MemberRoleUpdate(BaseModel):
    role: WorkspaceRole


class MemberStatusUpdate(BaseModel):
    status: Literal["ACTIVE", "DISABLED"]


class InvitationEmailPreview(BaseModel):
    email: str = Field(min_length=5, max_length=320)


class AuditRetentionUpdate(BaseModel):
    retention_days: int = Field(ge=30, le=3650)


class AuditRetentionPurge(BaseModel):
    confirm: bool = False
