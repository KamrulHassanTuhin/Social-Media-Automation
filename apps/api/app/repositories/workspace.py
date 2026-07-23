from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class WorkspaceProject:
    id: str
    name: str
    slug: str
    status: str


@dataclass(frozen=True)
class WorkspaceMember:
    user_id: str
    full_name: str
    role: str
    status: str
    email: str | None = None


@dataclass(frozen=True)
class AuditRecord:
    id: str
    workspace_id: str
    actor_id: str
    action: str
    entity_type: str
    entity_id: str | None
    previous_value: dict[str, Any] | None
    new_value: dict[str, Any] | None
    created_at: str


class InMemoryWorkspaceRepository:
    def __init__(self) -> None:
        self._projects = [
            WorkspaceProject("project_demo", "Content Studio", "content-studio", "ACTIVE"),
            WorkspaceProject("project_growth", "Growth Lab", "growth-lab", "ACTIVE"),
        ]
        self._members = [
            WorkspaceMember("user_demo", "Nadia Rahman", "WORKSPACE_ADMIN", "ACTIVE", "demo@nova.local"),
            WorkspaceMember("user_writer", "Samira Islam", "TEAM_MEMBER", "ACTIVE", "samira@nova.local"),
            WorkspaceMember("user_reviewer", "Maya Patel", "REVIEWER", "ACTIVE", "maya@nova.local"),
        ]
        self._audit: list[AuditRecord] = []
        from app.config.settings import get_settings
        self._audit_retention_days = get_settings().audit_retention_days

    def list_projects(self, workspace_id: str, include_archived: bool = False) -> list[WorkspaceProject]:
        if workspace_id != "ws_demo":
            return []
        return list(self._projects) if include_archived else [project for project in self._projects if project.status == "ACTIVE"]

    def list_workspace_ids(self) -> list[str]:
        return ["ws_demo"]

    def list_members(self, workspace_id: str) -> list[WorkspaceMember]:
        if workspace_id != "ws_demo":
            return []
        return list(self._members)

    def create_project(self, workspace_id: str, name: str, slug: str, actor_id: str) -> WorkspaceProject:
        project = WorkspaceProject(f"project_{uuid4().hex[:10]}", name, slug, "ACTIVE")
        self._projects.append(project)
        self.record_audit(workspace_id, actor_id, "PROJECT_CREATED", "PROJECT", project.id, None, project.__dict__)
        return project

    def update_project(self, workspace_id: str, project_id: str, name: str, slug: str, status: str, actor_id: str) -> WorkspaceProject | None:
        for index, project in enumerate(self._projects):
            if project.id == project_id:
                updated = WorkspaceProject(project.id, name, slug, status)
                self._projects[index] = updated
                self.record_audit(workspace_id, actor_id, "PROJECT_UPDATED", "PROJECT", project_id, project.__dict__, updated.__dict__)
                return updated
        return None

    def invite_member(self, workspace_id: str, email: str, role: str, actor_id: str) -> WorkspaceMember:
        member = WorkspaceMember(f"pending_{uuid4().hex[:10]}", email.split("@")[0].replace(".", " ").title(), role, "INVITED", email)
        self._members.append(member)
        self.record_audit(workspace_id, actor_id, "MEMBER_INVITED", "WORKSPACE_MEMBER", member.user_id, None, member.__dict__)
        return member

    def update_member_role(self, workspace_id: str, user_id: str, role: str, actor_id: str) -> WorkspaceMember | None:
        for index, member in enumerate(self._members):
            if member.user_id == user_id:
                updated = WorkspaceMember(member.user_id, member.full_name, role, member.status, member.email)
                self._members[index] = updated
                self.record_audit(workspace_id, actor_id, "MEMBER_ROLE_UPDATED", "WORKSPACE_MEMBER", user_id, {"role": member.role}, {"role": role})
                return updated
        return None

    def update_member_status(self, workspace_id: str, user_id: str, status: str, actor_id: str) -> WorkspaceMember | None:
        for index, member in enumerate(self._members):
            if member.user_id == user_id:
                updated = WorkspaceMember(member.user_id, member.full_name, member.role, status, member.email)
                self._members[index] = updated
                self.record_audit(workspace_id, actor_id, "MEMBER_STATUS_UPDATED", "WORKSPACE_MEMBER", user_id, {"status": member.status}, {"status": status})
                return updated
        return None

    def accept_invitation(self, workspace_id: str, user_id: str) -> WorkspaceMember | None:
        for index, member in enumerate(self._members):
            if member.user_id == user_id and member.status == "INVITED":
                updated = WorkspaceMember(member.user_id, member.full_name, member.role, "ACTIVE", member.email)
                self._members[index] = updated
                return updated
        return None

    def record_audit(self, workspace_id: str, actor_id: str, action: str, entity_type: str, entity_id: str | None, previous_value: dict[str, Any] | None, new_value: dict[str, Any] | None) -> AuditRecord:
        record = AuditRecord(str(uuid4()), workspace_id, actor_id, action, entity_type, entity_id, previous_value, new_value, datetime.now(timezone.utc).isoformat())
        self._audit.append(record)
        return record

    def list_audit(self, workspace_id: str, limit: int = 50, action: str | None = None, entity_type: str | None = None) -> list[AuditRecord]:
        records = [record for record in self._audit if record.workspace_id == workspace_id and (not action or record.action == action) and (not entity_type or record.entity_type == entity_type)]
        return list(reversed(records[-limit:]))

    def get_audit_retention(self, workspace_id: str) -> int:
        return self._audit_retention_days

    def set_audit_retention(self, workspace_id: str, retention_days: int, actor_id: str) -> int:
        previous = self._audit_retention_days
        self._audit_retention_days = retention_days
        self.record_audit(workspace_id, actor_id, "AUDIT_RETENTION_UPDATED", "AUDIT_POLICY", workspace_id, {"retention_days": previous}, {"retention_days": retention_days})
        return retention_days

    def purge_audit(self, workspace_id: str, retention_days: int, dry_run: bool = True) -> tuple[int, str]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        eligible = [record for record in self._audit if record.workspace_id == workspace_id and datetime.fromisoformat(record.created_at.replace("Z", "+00:00")) < cutoff]
        if not dry_run:
            eligible_ids = {record.id for record in eligible}
            self._audit = [record for record in self._audit if record.id not in eligible_ids]
        return len(eligible), cutoff.isoformat()


class SupabaseWorkspaceRepository:
    def __init__(self, url: str, service_role_key: str) -> None:
        from supabase import Client, create_client

        self.client: Client = create_client(url, service_role_key)

    def list_projects(self, workspace_id: str, include_archived: bool = False) -> list[WorkspaceProject]:
        query = self.client.table("projects").select("id,name,slug,status").eq("workspace_id", workspace_id)
        if not include_archived:
            query = query.eq("status", "ACTIVE")
        result: Any = query.order("name").execute()
        return [WorkspaceProject(str(row["id"]), row["name"], row["slug"], row["status"]) for row in result.data or []]

    def list_workspace_ids(self) -> list[str]:
        result: Any = self.client.table("workspaces").select("id").execute()
        return [str(row["id"]) for row in result.data or []]

    def list_members(self, workspace_id: str) -> list[WorkspaceMember]:
        result: Any = self.client.table("workspace_members").select("user_id,role,status,user_profiles(full_name)").eq("workspace_id", workspace_id).in_("status", ["ACTIVE", "INVITED", "DISABLED"]).execute()
        members: list[WorkspaceMember] = []
        for row in result.data or []:
            profile = row.get("user_profiles") or {}
            members.append(WorkspaceMember(str(row["user_id"]), profile.get("full_name") or "Unnamed member", row["role"], row["status"], None))
        return members

    def create_project(self, workspace_id: str, name: str, slug: str, actor_id: str) -> WorkspaceProject:
        row = self.client.table("projects").insert({"workspace_id": workspace_id, "name": name, "slug": slug, "created_by": actor_id, "updated_by": actor_id}).execute().data[0]
        project = WorkspaceProject(str(row["id"]), row["name"], row["slug"], row["status"])
        self.record_audit(workspace_id, actor_id, "PROJECT_CREATED", "PROJECT", project.id, None, project.__dict__)
        return project

    def update_project(self, workspace_id: str, project_id: str, name: str, slug: str, status: str, actor_id: str) -> WorkspaceProject | None:
        current = self.client.table("projects").select("id,name,slug,status").eq("workspace_id", workspace_id).eq("id", project_id).maybe_single().execute().data
        if not current:
            return None
        row = self.client.table("projects").update({"name": name, "slug": slug, "status": status, "updated_by": actor_id, "updated_at": datetime.now(timezone.utc).isoformat()}).eq("workspace_id", workspace_id).eq("id", project_id).execute().data[0]
        project = WorkspaceProject(str(row["id"]), row["name"], row["slug"], row["status"])
        self.record_audit(workspace_id, actor_id, "PROJECT_UPDATED", "PROJECT", project_id, {"name": current["name"], "slug": current["slug"], "status": current["status"]}, project.__dict__)
        return project

    def invite_member(self, workspace_id: str, email: str, role: str, actor_id: str) -> WorkspaceMember:
        response = self.client.auth.admin.invite_user_by_email(email)
        user = getattr(response, "user", None) or getattr(response, "data", None)
        user_id = str(getattr(user, "id", None) or (user or {}).get("id"))
        self.client.table("workspace_members").insert({"workspace_id": workspace_id, "user_id": user_id, "role": role, "status": "INVITED"}).execute()
        member = WorkspaceMember(user_id, email.split("@")[0].replace(".", " ").title(), role, "INVITED", email)
        self.record_audit(workspace_id, actor_id, "MEMBER_INVITED", "WORKSPACE_MEMBER", user_id, None, member.__dict__)
        return member

    def update_member_role(self, workspace_id: str, user_id: str, role: str, actor_id: str) -> WorkspaceMember | None:
        current = self.client.table("workspace_members").select("user_id,role,status").eq("workspace_id", workspace_id).eq("user_id", user_id).maybe_single().execute().data
        if not current:
            return None
        self.client.table("workspace_members").update({"role": role, "updated_at": datetime.now(timezone.utc).isoformat()}).eq("workspace_id", workspace_id).eq("user_id", user_id).execute()
        self.record_audit(workspace_id, actor_id, "MEMBER_ROLE_UPDATED", "WORKSPACE_MEMBER", user_id, {"role": current["role"]}, {"role": role})
        return WorkspaceMember(user_id, "Member", role, current["status"], None)

    def update_member_status(self, workspace_id: str, user_id: str, status: str, actor_id: str) -> WorkspaceMember | None:
        current = self.client.table("workspace_members").select("user_id,role,status").eq("workspace_id", workspace_id).eq("user_id", user_id).maybe_single().execute().data
        if not current:
            return None
        self.client.table("workspace_members").update({"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}).eq("workspace_id", workspace_id).eq("user_id", user_id).execute()
        self.record_audit(workspace_id, actor_id, "MEMBER_STATUS_UPDATED", "WORKSPACE_MEMBER", user_id, {"status": current["status"]}, {"status": status})
        return WorkspaceMember(user_id, "Member", current["role"], status, None)

    def accept_invitation(self, workspace_id: str, user_id: str) -> WorkspaceMember | None:
        current = self.client.table("workspace_members").select("user_id,role,status").eq("workspace_id", workspace_id).eq("user_id", user_id).eq("status", "INVITED").maybe_single().execute().data
        if not current:
            return None
        self.client.table("workspace_members").update({"status": "ACTIVE", "updated_at": datetime.now(timezone.utc).isoformat()}).eq("workspace_id", workspace_id).eq("user_id", user_id).execute()
        return WorkspaceMember(user_id, "Member", current["role"], "ACTIVE", None)

    def record_audit(self, workspace_id: str, actor_id: str, action: str, entity_type: str, entity_id: str | None, previous_value: dict[str, Any] | None, new_value: dict[str, Any] | None) -> AuditRecord:
        row = self.client.table("audit_logs").insert({"workspace_id": workspace_id, "actor_id": actor_id, "action": action, "entity_type": entity_type, "entity_id": entity_id, "previous_value": previous_value, "new_value": new_value}).execute().data[0]
        return AuditRecord(str(row["id"]), workspace_id, actor_id, action, entity_type, entity_id, previous_value, new_value, row["created_at"])

    def list_audit(self, workspace_id: str, limit: int = 50, action: str | None = None, entity_type: str | None = None) -> list[AuditRecord]:
        query = self.client.table("audit_logs").select("id,workspace_id,actor_id,action,entity_type,entity_id,previous_value,new_value,created_at").eq("workspace_id", workspace_id)
        if action:
            query = query.eq("action", action)
        if entity_type:
            query = query.eq("entity_type", entity_type)
        rows = query.order("created_at", desc=True).limit(limit).execute().data or []
        return [AuditRecord(str(row["id"]), str(row["workspace_id"]), str(row["actor_id"]), row["action"], row["entity_type"], str(row["entity_id"]) if row.get("entity_id") else None, row.get("previous_value"), row.get("new_value"), row["created_at"]) for row in rows]

    def get_audit_retention(self, workspace_id: str) -> int:
        from app.config.settings import get_settings
        row = self.client.table("audit_retention_policies").select("retention_days").eq("workspace_id", workspace_id).maybe_single().execute().data
        return int(row["retention_days"]) if row else get_settings().audit_retention_days

    def set_audit_retention(self, workspace_id: str, retention_days: int, actor_id: str) -> int:
        previous = self.get_audit_retention(workspace_id)
        self.client.table("audit_retention_policies").upsert({"workspace_id": workspace_id, "retention_days": retention_days, "updated_by": actor_id, "updated_at": datetime.now(timezone.utc).isoformat()}).execute()
        self.record_audit(workspace_id, actor_id, "AUDIT_RETENTION_UPDATED", "AUDIT_POLICY", workspace_id, {"retention_days": previous}, {"retention_days": retention_days})
        return retention_days

    def purge_audit(self, workspace_id: str, retention_days: int, dry_run: bool = True) -> tuple[int, str]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        query = self.client.table("audit_logs").select("id").eq("workspace_id", workspace_id).lt("created_at", cutoff.isoformat())
        rows = query.execute().data or []
        if not dry_run:
            self.client.table("audit_logs").delete().eq("workspace_id", workspace_id).lt("created_at", cutoff.isoformat()).execute()
        return len(rows), cutoff.isoformat()
