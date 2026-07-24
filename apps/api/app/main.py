from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.content import router as content_router
from app.api.v1.media import router as media_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.publishing import router as publishing_router
from app.api.v1.workspace import router as workspace_router
from app.api.v1.notifications import router as notifications_router
from app.config.settings import get_settings
from app.jobs.outbox import notification_outbox
from app.jobs.queue import job_queue
from app.integrations.factory import build_integrations
from app.jobs.worker import JobWorker
from app.repositories.factory import content_repository
from app.jobs.publishing import publishing_store
from app.services.health import health_store
from app.services.alerting import health_alert_manager
from app.integrations.google_sheets import GoogleSheetsClient, GoogleSheetsConfig

app = FastAPI(
    title="Nova Content Automation API",
    version="0.1.0",
    description="Versioned API boundary for the Nova content operations platform.",
)

settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)

app.include_router(content_router, prefix="/api/v1")
app.include_router(media_router, prefix="/api/v1")
app.include_router(integrations_router, prefix="/api/v1")
app.include_router(publishing_router, prefix="/api/v1")
app.include_router(workspace_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")

job_worker = JobWorker(job_queue, notification_outbox, content_repository, publishing_store)


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "nova-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health/providers")
async def provider_health(probe: bool = Query(default=False)) -> dict[str, Any]:
    def google_sheets_probe() -> bool:
        if not settings.google_sheets_spreadsheet_id or not settings.google_sheets_service_account_json:
            return False
        return GoogleSheetsClient(GoogleSheetsConfig(settings.google_sheets_spreadsheet_id, settings.google_sheets_service_account_json)).health_check()

    def state(configured: bool) -> str:
        if settings.app_env == "local":
            return "MOCK"
        return "CONFIGURED" if configured else "NOT_CONFIGURED"

    data = [
            {"provider": "supabase", "status": state(bool(settings.supabase_url and settings.supabase_service_role_key)), "checked_at": datetime.now(timezone.utc).isoformat()},
            {"provider": "openai", "status": state(bool(settings.openai_api_key)), "checked_at": datetime.now(timezone.utc).isoformat()},
            {"provider": "nuelink", "status": state(bool(settings.nuelink_api_key)), "checked_at": datetime.now(timezone.utc).isoformat()},
            {"provider": "slack", "status": state(bool(settings.slack_webhook_url)), "checked_at": datetime.now(timezone.utc).isoformat()},
            {"provider": "email", "status": state(bool(settings.email_api_key)), "checked_at": datetime.now(timezone.utc).isoformat()},
            {"provider": "google_sheets", "status": state(bool(settings.google_sheets_spreadsheet_id and settings.google_sheets_service_account_json)), "checked_at": datetime.now(timezone.utc).isoformat()},
        ]
    response_times: dict[str, int] = {}
    if probe:
        integrations = build_integrations()

        def timed_check(provider: str, check: Any) -> bool:
            started = perf_counter()
            try:
                result = bool(check())
            except Exception:
                result = False
            response_times[provider] = round((perf_counter() - started) * 1000)
            return result

        checks = {
            "supabase": timed_check("supabase", lambda: settings.app_env == "local" or bool(settings.supabase_url)),
            "openai": timed_check("openai", integrations.ai.health_check),
            "nuelink": timed_check("nuelink", integrations.publisher.health_check),
            "slack": timed_check("slack", integrations.notifier.health_check),
            "email": timed_check("email", integrations.email.health_check if integrations.email else lambda: False),
            "google_sheets": timed_check("google_sheets", google_sheets_probe),
        }
        data = [{**item, "probe": "PASS" if checks[item["provider"]] else "FAIL", "response_time_ms": response_times[item["provider"]]} for item in data]
    if probe:
        for item in data:
            health_store.record(item["provider"], item["probe"], item.get("response_time_ms"), {"status": item["status"]})
    alerts = health_alert_manager.process(data, build_integrations().notifier) if probe else []
    return {"data": data, "meta": {"alerts_emitted": alerts}}


@app.get("/health/history")
async def health_history(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    return {"data": [record.__dict__ for record in health_store.recent(limit)], "meta": {"persisted": settings.app_env != "local"}}


@app.get("/health/queue")
async def queue_health() -> dict[str, Any]:
    return {"status": "ok", "mode": "in-memory" if settings.app_env == "local" else "supabase", "checked_at": datetime.now(timezone.utc).isoformat()}


@app.get("/health/storage")
async def storage_health() -> dict[str, Any]:
    return {"status": "ok", "mode": "local-files" if settings.app_env == "local" else "supabase-storage", "bucket": "axis-media", "checked_at": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1")
async def api_root() -> dict[str, Any]:
    return {"success": True, "data": {"version": "v1"}, "error": None, "meta": {}}


@app.get("/api/v1/workflow/statuses")
async def workflow_statuses() -> dict[str, Any]:
    return {
        "success": True,
        "data": {
            "automation_statuses": [
                "NOT_STARTED", "QUEUED", "GENERATING", "NEEDS_REVIEW",
                "CHANGES_REQUESTED", "APPROVED", "READY_TO_PUBLISH", "PUBLISHING",
                "PARTIALLY_PUBLISHED", "PUBLISHED", "FAILED", "CANCELED",
            ],
            "publishing_job_statuses": [
                "PENDING", "QUEUED", "PROCESSING", "SUCCEEDED", "FAILED",
                "RETRY_SCHEDULED", "CANCELED", "MANUAL_REQUIRED", "SKIPPED",
            ],
        },
        "error": None,
        "meta": {},
    }
