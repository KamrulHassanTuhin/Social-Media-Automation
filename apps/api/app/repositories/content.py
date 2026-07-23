from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class ContentRecord:
    id: str
    workspace_id: str
    project_id: str
    topic: str
    brief_status: str = "NOT_STARTED"
    automation_status: str = "NOT_STARTED"
    publisher_id: str | None = None
    live_url: str | None = None
    has_media: bool = False
    copies: dict[str, str] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CopyVersionRecord:
    id: str
    content_id: str
    channel: str
    version: int
    body: str
    created_by: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ApprovalRecord:
    id: str
    content_id: str
    reviewer_id: str
    decision: str
    notes: str | None
    previous_status: str
    new_status: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class InMemoryContentRepository:
    """Safe local fallback for development; production will use Supabase."""

    def __init__(self) -> None:
        self._items: dict[str, ContentRecord] = {}
        self._copy_versions: dict[str, list[CopyVersionRecord]] = {}
        self._approvals: dict[str, list[ApprovalRecord]] = {}
        self._seed()

    def _seed(self) -> None:
        self.add(ContentRecord("cnt_demo_01", "ws_demo", "project_axis", "Search intent content engine", "BRIEF_READY", "NEEDS_REVIEW", "publisher_demo", "https://axis.example.com/search-intent", True, {"linkedin": "A practical search intent framework for B2B teams."}))
        self.add(ContentRecord("cnt_demo_02", "ws_demo", "project_growth", "Technical SEO migration checklist", "IN_PROGRESS"))

    def list(self, workspace_id: str, search: str | None = None) -> list[ContentRecord]:
        items = [item for item in self._items.values() if item.workspace_id == workspace_id]
        if search:
            needle = search.lower()
            items = [item for item in items if needle in item.topic.lower()]
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def get(self, workspace_id: str, content_id: str) -> ContentRecord | None:
        item = self._items.get(content_id)
        return item if item and item.workspace_id == workspace_id else None

    def add(self, item: ContentRecord, actor_id: str | None = None) -> ContentRecord:
        self._items[item.id] = item
        return item

    def update(self, item: ContentRecord, actor_id: str | None = None) -> ContentRecord:
        item.updated_at = datetime.now(timezone.utc)
        self._items[item.id] = item
        return item

    def save_copy_version(self, content_id: str, channel: str, body: str, created_by: str) -> CopyVersionRecord:
        copy_id = f"copy_{content_id}_{channel.lower()}"
        versions = self._copy_versions.setdefault(copy_id, [])
        version = CopyVersionRecord(copy_id, content_id, channel, len(versions) + 1, body, created_by)
        versions.append(version)
        return version

    def list_copy_versions(self, content_id: str) -> list[CopyVersionRecord]:
        return [version for versions in self._copy_versions.values() for version in versions if version.content_id == content_id]

    def find_copy(self, copy_id: str) -> CopyVersionRecord | None:
        versions = self._copy_versions.get(copy_id, [])
        return versions[-1] if versions else None

    def update_copy(self, copy_id: str, body: str, updated_by: str) -> CopyVersionRecord | None:
        current = self.find_copy(copy_id)
        if not current:
            return None
        return self.save_copy_version(current.content_id, current.channel, body, updated_by)

    def record_approval(self, approval: ApprovalRecord) -> ApprovalRecord:
        self._approvals.setdefault(approval.content_id, []).append(approval)
        return approval

    def list_approvals(self, content_id: str) -> list[ApprovalRecord]:
        return list(self._approvals.get(content_id, []))


content_repository = InMemoryContentRepository()


def new_content(workspace_id: str, project_id: str, topic: str) -> ContentRecord:
    return ContentRecord(str(uuid4()), workspace_id, project_id, topic)
