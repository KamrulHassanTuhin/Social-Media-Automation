from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class HealthRecord:
    id: str
    component: str
    status: str
    response_time_ms: int | None
    details: dict[str, Any]
    checked_at: str


class InMemoryHealthStore:
    def __init__(self) -> None:
        self.records: list[HealthRecord] = []

    def record(self, component: str, status: str, response_time_ms: int | None, details: dict[str, Any]) -> HealthRecord:
        record = HealthRecord(str(uuid4()), component, status, response_time_ms, details, datetime.now(timezone.utc).isoformat())
        self.records.append(record)
        self.records = self.records[-200:]
        return record

    def recent(self, limit: int = 50) -> list[HealthRecord]:
        return list(reversed(self.records[-limit:]))


class SupabaseHealthStore:
    def __init__(self, url: str, service_role_key: str) -> None:
        from supabase import Client, create_client

        self.client: Client = create_client(url, service_role_key)

    def record(self, component: str, status: str, response_time_ms: int | None, details: dict[str, Any]) -> HealthRecord:
        now = datetime.now(timezone.utc).isoformat()
        result = self.client.table("system_health_checks").insert({"component": component, "status": status, "response_time_ms": response_time_ms, "details": details, "checked_at": now}).execute()
        row = result.data[0]
        return HealthRecord(str(row["id"]), row["component"], row["status"], row.get("response_time_ms"), row.get("details") or {}, row["checked_at"])

    def recent(self, limit: int = 50) -> list[HealthRecord]:
        result = self.client.table("system_health_checks").select("id,component,status,response_time_ms,details,checked_at").order("checked_at", desc=True).limit(limit).execute()
        return [HealthRecord(str(row["id"]), row["component"], row["status"], row.get("response_time_ms"), row.get("details") or {}, row["checked_at"]) for row in result.data or []]


def build_health_store():
    from app.config.settings import get_settings

    settings = get_settings()
    if settings.app_env == "local":
        return InMemoryHealthStore()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required outside local mode.")
    return SupabaseHealthStore(settings.supabase_url, settings.supabase_service_role_key)


health_store = build_health_store()
