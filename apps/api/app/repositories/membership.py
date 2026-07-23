from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Membership:
    user_id: str
    workspace_id: str
    role: str
    status: str


class InMemoryMembershipRepository:
    def get(self, user_id: str, workspace_id: str) -> Membership | None:
        if user_id == "user_demo" and workspace_id == "ws_demo":
            return Membership(user_id, workspace_id, "WORKSPACE_ADMIN", "ACTIVE")
        return None


class SupabaseMembershipRepository:
    """Canonical workspace membership lookup; JWT claims are not trusted for access."""

    def __init__(self, url: str, service_role_key: str) -> None:
        from supabase import Client, create_client

        self.client: Client = create_client(url, service_role_key)

    def get(self, user_id: str, workspace_id: str) -> Membership | None:
        result: Any = self.client.table("workspace_members").select("user_id,workspace_id,role,status").eq("user_id", user_id).eq("workspace_id", workspace_id).maybe_single().execute()
        if not result.data:
            return None
        row = result.data
        return Membership(str(row["user_id"]), str(row["workspace_id"]), row["role"], row["status"])
