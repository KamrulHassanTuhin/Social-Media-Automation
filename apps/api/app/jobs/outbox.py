from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from app.config.settings import get_settings


@dataclass
class NotificationEvent:
    id: str
    workspace_id: str
    event_type: str
    payload: dict
    idempotency_key: str
    recipient_id: str | None = None
    status: str = "PENDING"
    retry_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    sent_at: datetime | None = None
    last_error: str | None = None
    provider_message_id: str | None = None
    delivered_at: datetime | None = None
    bounced_at: datetime | None = None
    unsubscribed_at: datetime | None = None
    provider_event_type: str | None = None


class InMemoryNotificationOutbox:
    def __init__(self) -> None:
        self._events: dict[str, NotificationEvent] = {}
        self._by_key: dict[str, str] = {}
        self._suppressions: dict[tuple[str, str], str] = {}

    def enqueue(self, workspace_id: str, event_type: str, payload: dict, idempotency_key: str, recipient_id: str | None = None) -> NotificationEvent:
        if idempotency_key in self._by_key:
            return self._events[self._by_key[idempotency_key]]
        event = NotificationEvent(str(uuid4()), workspace_id, event_type, payload, idempotency_key, recipient_id)
        self._events[event.id] = event
        self._by_key[idempotency_key] = event.id
        return event

    def claim_next(self) -> NotificationEvent | None:
        event = next((candidate for candidate in self._events.values() if candidate.status == "PENDING"), None)
        if event:
            event.status = "PROCESSING"
        return event

    def mark_sent(self, event: NotificationEvent, provider_message_id: str | None = None) -> NotificationEvent:
        event.status = "SENT"
        event.sent_at = datetime.now(timezone.utc)
        event.provider_message_id = provider_message_id
        return event

    def mark_canceled(self, event: NotificationEvent, error: str) -> NotificationEvent:
        event.status = "CANCELED"
        event.last_error = error
        return event

    def find_by_provider_message_id(self, provider_message_id: str) -> NotificationEvent | None:
        return next((event for event in self._events.values() if event.provider_message_id == provider_message_id), None)

    def mark_delivery(self, event: NotificationEvent, event_type: str, payload: dict, status: str) -> NotificationEvent:
        now = datetime.now(timezone.utc)
        event.provider_event_type = event_type
        if status == "SENT":
            event.delivered_at = now
        elif status == "BOUNCED":
            event.status = status
            event.bounced_at = now
            recipient = event.payload.get("to")
            if recipient:
                self._suppressions[(event.workspace_id, str(recipient).lower())] = "BOUNCE"
        elif status == "UNSUBSCRIBED":
            event.status = status
            event.unsubscribed_at = now
            recipient = event.payload.get("to")
            if recipient:
                self._suppressions[(event.workspace_id, str(recipient).lower())] = "UNSUBSCRIBE"
        event.payload["provider_event"] = payload
        return event

    def is_suppressed(self, workspace_id: str, recipient: str) -> bool:
        return (workspace_id, recipient.lower()) in self._suppressions

    def analytics(self, workspace_id: str) -> dict[str, int]:
        events = [event for event in self._events.values() if event.workspace_id == workspace_id]
        return {status: sum(1 for event in events if event.status == status) for status in ("PENDING", "PROCESSING", "SENT", "FAILED", "CANCELED", "BOUNCED", "UNSUBSCRIBED")}

    def mark_failed(self, event: NotificationEvent, error: str) -> NotificationEvent:
        event.retry_count += 1
        event.last_error = error
        event.status = "FAILED" if event.retry_count >= 3 else "PENDING"
        return event

    def get(self, event_id: str) -> NotificationEvent | None:
        return self._events.get(event_id)

    def list(self, workspace_id: str, limit: int = 100) -> list[NotificationEvent]:
        return list(reversed([event for event in self._events.values() if event.workspace_id == workspace_id][-limit:]))

    def retry(self, event: NotificationEvent) -> NotificationEvent:
        event.status = "PENDING"
        event.last_error = None
        return event


class SupabaseNotificationOutbox:
    def __init__(self, url: str, service_role_key: str, worker_id: str = "notification-worker") -> None:
        from supabase import Client, create_client

        self.client: Client = create_client(url, service_role_key)
        self.worker_id = worker_id

    def enqueue(self, workspace_id: str, event_type: str, payload: dict, idempotency_key: str, recipient_id: str | None = None) -> NotificationEvent:
        existing = self.client.table("notification_outbox").select("*").eq("idempotency_key", idempotency_key).maybe_single().execute()
        if existing.data:
            return self._from_row(existing.data)
        result = self.client.table("notification_outbox").insert({"workspace_id": workspace_id, "event_type": event_type, "recipient_id": recipient_id, "payload": payload, "idempotency_key": idempotency_key}).execute()
        return self._from_row(result.data[0])

    def claim_next(self) -> NotificationEvent | None:
        result = self.client.rpc("claim_next_notification", {"worker_id": self.worker_id, "visibility_seconds": 300}).execute()
        row = result.data
        if isinstance(row, list):
            row = row[0] if row else None
        return self._from_row(row) if row else None

    def get(self, event_id: str) -> NotificationEvent | None:
        result = self.client.table("notification_outbox").select("*").eq("id", event_id).maybe_single().execute()
        return self._from_row(result.data) if result.data else None

    def list(self, workspace_id: str, limit: int = 100) -> list[NotificationEvent]:
        result = self.client.table("notification_outbox").select("*").eq("workspace_id", workspace_id).order("created_at", desc=True).limit(limit).execute()
        return [self._from_row(row) for row in result.data or []]

    def retry(self, event: NotificationEvent) -> NotificationEvent:
        event.status = "PENDING"
        event.last_error = None
        self.client.table("notification_outbox").update({"status": "PENDING", "last_error": None, "visibility_timeout_at": None}).eq("id", event.id).execute()
        return event

    def mark_sent(self, event: NotificationEvent, provider_message_id: str | None = None) -> NotificationEvent:
        event.status = "SENT"
        event.sent_at = datetime.now(timezone.utc)
        event.provider_message_id = provider_message_id
        values = {"status": "SENT", "sent_at": event.sent_at.isoformat(), "visibility_timeout_at": None}
        if provider_message_id:
            values["provider_message_id"] = provider_message_id
        self.client.table("notification_outbox").update(values).eq("id", event.id).execute()
        return event

    def mark_canceled(self, event: NotificationEvent, error: str) -> NotificationEvent:
        event.status = "CANCELED"
        event.last_error = error
        self.client.table("notification_outbox").update({"status": "CANCELED", "last_error": error, "visibility_timeout_at": None}).eq("id", event.id).execute()
        return event

    def find_by_provider_message_id(self, provider_message_id: str) -> NotificationEvent | None:
        result = self.client.table("notification_outbox").select("*").eq("provider_message_id", provider_message_id).maybe_single().execute()
        return self._from_row(result.data) if result.data else None

    def mark_delivery(self, event: NotificationEvent, event_type: str, payload: dict, status: str) -> NotificationEvent:
        now = datetime.now(timezone.utc)
        columns = {"provider_event_type": event_type, "provider_event_payload": payload}
        if status == "SENT":
            columns.update({"delivered_at": now.isoformat()})
        elif status == "BOUNCED":
            columns.update({"status": status, "bounced_at": now.isoformat()})
        elif status == "UNSUBSCRIBED":
            columns.update({"status": status, "unsubscribed_at": now.isoformat()})
        self.client.table("notification_outbox").update(columns).eq("id", event.id).execute()
        recipient = event.payload.get("to")
        if recipient and status in {"BOUNCED", "UNSUBSCRIBED"}:
            self.client.table("notification_suppressions").upsert({"workspace_id": event.workspace_id, "recipient": str(recipient).lower(), "reason": "BOUNCE" if status == "BOUNCED" else "UNSUBSCRIBE", "source_event_id": event.id}).execute()
        self.client.table("notification_delivery_events").insert({"workspace_id": event.workspace_id, "notification_id": event.id, "provider": "EMAIL", "event_type": event_type, "provider_message_id": event.provider_message_id, "payload": payload}).execute()
        return event

    def is_suppressed(self, workspace_id: str, recipient: str) -> bool:
        result = self.client.table("notification_suppressions").select("id").eq("workspace_id", workspace_id).eq("recipient", recipient.lower()).limit(1).execute()
        return bool(result.data)

    def analytics(self, workspace_id: str) -> dict[str, int]:
        result = self.client.table("notification_outbox").select("status").eq("workspace_id", workspace_id).execute()
        counts = {status: 0 for status in ("PENDING", "PROCESSING", "SENT", "FAILED", "CANCELED", "BOUNCED", "UNSUBSCRIBED")}
        for row in result.data or []:
            counts[row.get("status", "PENDING")] = counts.get(row.get("status", "PENDING"), 0) + 1
        return counts

    def mark_failed(self, event: NotificationEvent, error: str) -> NotificationEvent:
        event.retry_count += 1
        event.last_error = error
        event.status = "FAILED" if event.retry_count >= 3 else "PENDING"
        self.client.table("notification_outbox").update({"status": event.status, "retry_count": event.retry_count, "last_error": error, "visibility_timeout_at": None}).eq("id", event.id).execute()
        return event

    @staticmethod
    def _from_row(row: dict) -> NotificationEvent:
        return NotificationEvent(str(row["id"]), str(row["workspace_id"]), row["event_type"], row.get("payload") or {}, row["idempotency_key"], row.get("recipient_id"), row.get("status", "PENDING"), int(row.get("retry_count") or 0), datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")), datetime.fromisoformat(row["sent_at"].replace("Z", "+00:00")) if row.get("sent_at") else None, row.get("last_error"), row.get("provider_message_id"), datetime.fromisoformat(row["delivered_at"].replace("Z", "+00:00")) if row.get("delivered_at") else None, datetime.fromisoformat(row["bounced_at"].replace("Z", "+00:00")) if row.get("bounced_at") else None, datetime.fromisoformat(row["unsubscribed_at"].replace("Z", "+00:00")) if row.get("unsubscribed_at") else None, row.get("provider_event_type"))


def build_notification_outbox():
    settings = get_settings()
    if settings.app_env == "local":
        return InMemoryNotificationOutbox()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required outside local mode.")
    return SupabaseNotificationOutbox(settings.supabase_url, settings.supabase_service_role_key)


notification_outbox = build_notification_outbox()
