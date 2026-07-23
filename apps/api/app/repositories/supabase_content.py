from __future__ import annotations

from datetime import datetime
from typing import Any

from app.repositories.content import ApprovalRecord, ContentRecord, CopyVersionRecord


class SupabaseContentRepository:
    """Supabase-backed repository. The service role is used only server-side."""

    def __init__(self, url: str, service_role_key: str) -> None:
        from supabase import Client, create_client

        self.client: Client = create_client(url, service_role_key)

    def list(self, workspace_id: str, search: str | None = None) -> list[ContentRecord]:
        query = self.client.table("content_items").select("*").eq("workspace_id", workspace_id).is_("deleted_at", "null")
        if search:
            query = query.ilike("topic", f"%{search}%")
        result: Any = query.order("updated_at", desc=True).execute()
        items = [self._map(row) for row in (result.data or [])]
        for item in items:
            self._hydrate_copies(item)
        return items

    def get(self, workspace_id: str, content_id: str) -> ContentRecord | None:
        result: Any = self.client.table("content_items").select("*").eq("workspace_id", workspace_id).eq("id", content_id).is_("deleted_at", "null").maybe_single().execute()
        if not result.data:
            return None
        item = self._map(result.data)
        self._hydrate_copies(item)
        return item

    def add(self, item: ContentRecord, actor_id: str | None = None) -> ContentRecord:
        actor = actor_id or "system"
        result: Any = self.client.table("content_items").insert({
            "id": item.id,
            "workspace_id": item.workspace_id,
            "project_id": item.project_id,
            "topic": item.topic,
            "brief_status": item.brief_status,
            "automation_status": item.automation_status,
            "publisher_id": item.publisher_id,
            "live_url": item.live_url,
            "updated_by": actor,
            "created_by": actor,
        }).execute()
        return self._map(result.data[0])

    def update(self, item: ContentRecord, actor_id: str | None = None) -> ContentRecord:
        actor = actor_id or "system"
        item.updated_at = datetime.now(item.updated_at.tzinfo)
        result: Any = self.client.table("content_items").update({
            "brief_status": item.brief_status,
            "automation_status": item.automation_status,
            "publisher_id": item.publisher_id,
            "live_url": item.live_url,
            "updated_at": item.updated_at.isoformat(),
            "updated_by": actor,
        }).eq("workspace_id", item.workspace_id).eq("id", item.id).execute()
        return self._map(result.data[0])

    def save_copy_version(self, content_id: str, channel: str, body: str, created_by: str) -> CopyVersionRecord:
        normalized_channel = self._channel_value(channel)
        existing: Any = self.client.table("social_copies").select("id,current_version").eq("content_item_id", content_id).eq("channel", normalized_channel).maybe_single().execute()
        if existing.data:
            social_copy_id = str(existing.data["id"])
            version_number = int(existing.data.get("current_version") or 0) + 1
            self.client.table("social_copies").update({"body": body, "current_version": version_number, "updated_by": created_by, "updated_at": datetime.utcnow().isoformat()}).eq("id", social_copy_id).execute()
        else:
            version_number = 1
            inserted: Any = self.client.table("social_copies").insert({"workspace_id": self._workspace_for_content(content_id), "content_item_id": content_id, "channel": normalized_channel, "body": body, "status": "DRAFT", "current_version": version_number, "created_by": created_by, "updated_by": created_by}).execute()
            social_copy_id = str(inserted.data[0]["id"])
        self.client.table("social_copy_versions").insert({"workspace_id": self._workspace_for_content(content_id), "social_copy_id": social_copy_id, "version_number": version_number, "body": body, "created_by": created_by}).execute()
        return CopyVersionRecord(social_copy_id, content_id, normalized_channel, version_number, body, created_by)

    def list_copy_versions(self, content_id: str) -> list[CopyVersionRecord]:
        copies: Any = self.client.table("social_copies").select("id,channel").eq("content_item_id", content_id).execute()
        output: list[CopyVersionRecord] = []
        for copy in copies.data or []:
            versions: Any = self.client.table("social_copy_versions").select("id,version_number,body,created_by,created_at").eq("social_copy_id", copy["id"]).order("version_number").execute()
            output.extend(CopyVersionRecord(str(row["id"]), content_id, copy["channel"], int(row["version_number"]), row.get("body") or "", str(row["created_by"]), datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))) for row in versions.data or [])
        return output

    def find_copy(self, copy_id: str) -> CopyVersionRecord | None:
        result: Any = self.client.table("social_copies").select("id,content_item_id,channel,current_version").eq("id", copy_id).maybe_single().execute()
        if not result.data:
            return None
        version: Any = self.client.table("social_copy_versions").select("id,version_number,body,created_by,created_at").eq("social_copy_id", copy_id).order("version_number", desc=True).limit(1).maybe_single().execute()
        if not version.data:
            return None
        row = version.data
        return CopyVersionRecord(str(row["id"]), str(result.data["content_item_id"]), result.data["channel"], int(row["version_number"]), row.get("body") or "", str(row["created_by"]), datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")))

    def update_copy(self, copy_id: str, body: str, updated_by: str) -> CopyVersionRecord | None:
        current = self.find_copy(copy_id)
        if not current:
            return None
        return self.save_copy_version(current.content_id, current.channel, body, updated_by)

    def record_approval(self, approval: ApprovalRecord) -> ApprovalRecord:
        self.client.table("approvals").insert({"id": approval.id, "workspace_id": self._workspace_for_content(approval.content_id), "content_item_id": approval.content_id, "reviewer_id": approval.reviewer_id, "decision": approval.decision, "notes": approval.notes, "previous_status": approval.previous_status, "new_status": approval.new_status, "created_at": approval.created_at.isoformat()}).execute()
        return approval

    def list_approvals(self, content_id: str) -> list[ApprovalRecord]:
        result: Any = self.client.table("approvals").select("id,reviewer_id,decision,notes,previous_status,new_status,created_at").eq("content_item_id", content_id).order("created_at").execute()
        return [ApprovalRecord(str(row["id"]), content_id, str(row["reviewer_id"]), row["decision"], row.get("notes"), row.get("previous_status") or "", row.get("new_status") or "", datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))) for row in result.data or []]

    def _workspace_for_content(self, content_id: str) -> str:
        result: Any = self.client.table("content_items").select("workspace_id").eq("id", content_id).maybe_single().execute()
        return str(result.data["workspace_id"])

    def _hydrate_copies(self, item: ContentRecord) -> None:
        result: Any = self.client.table("social_copies").select("channel,body").eq("content_item_id", item.id).execute()
        item.copies = {str(row["channel"]).lower(): row.get("body") or "" for row in result.data or []}

    @staticmethod
    def _channel_value(channel: str) -> str:
        return {"facebook_instagram": "FACEBOOK_INSTAGRAM", "linkedin": "LINKEDIN", "youtube": "YOUTUBE", "gbp": "GBP", "reddit": "REDDIT"}.get(channel.lower(), channel.upper())

    @staticmethod
    def _map(row: dict[str, Any]) -> ContentRecord:
        return ContentRecord(
            id=str(row["id"]),
            workspace_id=str(row["workspace_id"]),
            project_id=str(row["project_id"]),
            topic=row["topic"],
            brief_status=row.get("brief_status", "NOT_STARTED"),
            automation_status=row.get("automation_status", "NOT_STARTED"),
            publisher_id=row.get("publisher_id"),
            live_url=row.get("live_url"),
            has_media=bool(row.get("has_media", False)),
            updated_at=datetime.fromisoformat(row["updated_at"].replace("Z", "+00:00")),
        )
