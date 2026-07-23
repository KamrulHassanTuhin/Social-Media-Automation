from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.services.credentials import CredentialCipher


@dataclass(frozen=True)
class IntegrationSummary:
    provider: str
    status: str
    settings: dict[str, Any]
    last_tested_at: str | None
    last_successful_use: str | None
    last_error: str | None


class InMemoryIntegrationRepository:
    def __init__(self, cipher: CredentialCipher) -> None:
        self.cipher = cipher
        self._records: dict[tuple[str, str], dict[str, Any]] = {}

    def list(self, workspace_id: str) -> list[IntegrationSummary]:
        return [self._summary(record) for (record_workspace, _), record in self._records.items() if record_workspace == workspace_id]

    def connect(self, workspace_id: str, provider: str, credentials: dict[str, str], settings: dict[str, Any]) -> IntegrationSummary:
        ciphertext, nonce = self.cipher.encrypt(credentials)
        now = datetime.now(timezone.utc).isoformat()
        record = {"provider": provider.upper(), "ciphertext": ciphertext, "nonce": nonce, "settings": settings, "status": "CONNECTED", "last_tested_at": now, "last_successful_use": None, "last_error": None}
        self._records[(workspace_id, provider.upper())] = record
        return self._summary(record)

    def test(self, workspace_id: str, provider: str) -> IntegrationSummary:
        record = self._records.get((workspace_id, provider.upper()))
        if not record:
            return IntegrationSummary(provider.upper(), "NOT_CONFIGURED", {}, None, None, None)
        record["status"] = "CONNECTED"
        record["last_tested_at"] = datetime.now(timezone.utc).isoformat()
        return self._summary(record)

    def disconnect(self, workspace_id: str, provider: str) -> IntegrationSummary:
        record = self._records.get((workspace_id, provider.upper()))
        if not record:
            return IntegrationSummary(provider.upper(), "NOT_CONFIGURED", {}, None, None, None)
        record["status"] = "DISCONNECTED"
        record["last_tested_at"] = datetime.now(timezone.utc).isoformat()
        return self._summary(record)

    @staticmethod
    def _summary(record: dict[str, Any]) -> IntegrationSummary:
        return IntegrationSummary(record["provider"], record["status"], record.get("settings", {}), record.get("last_tested_at"), record.get("last_successful_use"), record.get("last_error"))


class SupabaseIntegrationRepository:
    def __init__(self, url: str, service_role_key: str, cipher: CredentialCipher) -> None:
        from supabase import Client, create_client

        self.client: Client = create_client(url, service_role_key)
        self.cipher = cipher

    def list(self, workspace_id: str) -> list[IntegrationSummary]:
        result: Any = self.client.table("integrations").select("provider,status,settings,last_tested_at,last_successful_use,last_error").eq("workspace_id", workspace_id).execute()
        return [IntegrationSummary(row["provider"], row["status"], row.get("settings") or {}, row.get("last_tested_at"), row.get("last_successful_use"), row.get("last_error")) for row in result.data or []]

    def connect(self, workspace_id: str, provider: str, credentials: dict[str, str], settings: dict[str, Any]) -> IntegrationSummary:
        provider = provider.upper()
        ciphertext, nonce = self.cipher.encrypt(credentials)
        now = datetime.now(timezone.utc).isoformat()
        self.client.table("integration_credentials").upsert({"workspace_id": workspace_id, "provider": provider, "ciphertext": ciphertext, "nonce": nonce, "key_version": "v1", "rotated_at": now}).execute()
        self.client.table("integrations").upsert({"workspace_id": workspace_id, "provider": provider, "status": "CONNECTED", "settings": settings, "last_tested_at": now, "last_error": None, "updated_at": now}).execute()
        return self._get(workspace_id, provider)

    def test(self, workspace_id: str, provider: str) -> IntegrationSummary:
        provider = provider.upper()
        record = self._get(workspace_id, provider)
        now = datetime.now(timezone.utc).isoformat()
        if record.status == "NOT_CONFIGURED":
            return record
        self.client.table("integrations").update({"status": "CONNECTED", "last_tested_at": now, "last_error": None, "updated_at": now}).eq("workspace_id", workspace_id).eq("provider", provider).execute()
        return self._get(workspace_id, provider)

    def disconnect(self, workspace_id: str, provider: str) -> IntegrationSummary:
        provider = provider.upper()
        self.client.table("integrations").update({"status": "DISCONNECTED", "updated_at": datetime.now(timezone.utc).isoformat()}).eq("workspace_id", workspace_id).eq("provider", provider).execute()
        return self._get(workspace_id, provider)

    def _get(self, workspace_id: str, provider: str) -> IntegrationSummary:
        result: Any = self.client.table("integrations").select("provider,status,settings,last_tested_at,last_successful_use,last_error").eq("workspace_id", workspace_id).eq("provider", provider).maybe_single().execute()
        if not result.data:
            return IntegrationSummary(provider, "NOT_CONFIGURED", {}, None, None, None)
        row = result.data
        return IntegrationSummary(row["provider"], row["status"], row.get("settings") or {}, row.get("last_tested_at"), row.get("last_successful_use"), row.get("last_error"))


def build_integration_repository():
    from app.config.settings import get_settings

    settings = get_settings()
    key = settings.encryption_key
    if settings.app_env != "local" and (not key or key == "local-only-change-me"):
        raise RuntimeError("ENCRYPTION_KEY is required outside local mode.")
    cipher = CredentialCipher(key or "local-development-key")
    if settings.app_env == "local":
        return InMemoryIntegrationRepository(cipher)
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required outside local mode.")
    return SupabaseIntegrationRepository(settings.supabase_url, settings.supabase_service_role_key, cipher)


integration_repository = build_integration_repository()
