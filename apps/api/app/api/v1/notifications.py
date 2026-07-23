import hashlib
import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status

from app.auth.dependencies import CurrentUser, workspace_context
from app.auth.permissions import require_permission
from app.config.settings import get_settings
from app.jobs.outbox import notification_outbox

router = APIRouter(prefix="/notifications", tags=["notifications"])


def serialize(event) -> dict:
    return {"id": event.id, "workspace_id": event.workspace_id, "event_type": event.event_type, "recipient_id": event.recipient_id, "status": event.status, "retry_count": event.retry_count, "payload": {key: value for key, value in event.payload.items() if key not in {"body"}}, "provider_message_id": event.provider_message_id, "provider_event_type": event.provider_event_type, "delivered_at": event.delivered_at.isoformat() if event.delivered_at else None, "bounced_at": event.bounced_at.isoformat() if event.bounced_at else None, "unsubscribed_at": event.unsubscribed_at.isoformat() if event.unsubscribed_at else None, "created_at": event.created_at.isoformat(), "sent_at": event.sent_at.isoformat() if event.sent_at else None, "last_error": event.last_error}


@router.get("/outbox", response_model=dict)
async def list_notification_outbox(limit: int = Query(default=100, ge=1, le=200), context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, _ = require_permission(context, "MANAGE_WORKSPACE")
    events = notification_outbox.list(workspace_id, limit)
    return {"success": True, "data": [serialize(event) for event in events], "error": None, "meta": {}}


@router.post("/outbox/{event_id}/retry", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def retry_notification(event_id: str, context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, _ = require_permission(context, "MANAGE_WORKSPACE")
    event = notification_outbox.get(event_id)
    if not event or event.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail={"code": "NOTIFICATION_NOT_FOUND", "message": "Notification event was not found."})
    if event.status != "FAILED":
        raise HTTPException(status_code=409, detail={"code": "NOTIFICATION_NOT_RETRYABLE", "message": "Only failed notifications can be retried."})
    notification_outbox.retry(event)
    return {"success": True, "data": serialize(event), "error": None, "meta": {"queued": True}}


@router.get("/analytics", response_model=dict)
async def notification_analytics(context: tuple[str, CurrentUser] = Depends(workspace_context)):
    workspace_id, _ = require_permission(context, "MANAGE_WORKSPACE")
    return {"success": True, "data": notification_outbox.analytics(workspace_id), "error": None, "meta": {}}


@router.post("/webhook/email", response_model=dict, status_code=status.HTTP_202_ACCEPTED)
async def email_webhook(request: Request, x_axis_signature: str | None = Header(default=None, alias="X-AXIS-Signature")):
    raw_body = await request.body()
    settings = get_settings()
    if settings.app_env != "local":
        if not settings.email_webhook_secret or not x_axis_signature:
            raise HTTPException(status_code=401, detail={"code": "WEBHOOK_UNAUTHORIZED", "message": "A valid webhook signature is required."})
        expected = hmac.new(settings.email_webhook_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, x_axis_signature):
            raise HTTPException(status_code=401, detail={"code": "WEBHOOK_UNAUTHORIZED", "message": "A valid webhook signature is required."})
    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "WEBHOOK_INVALID_JSON", "message": "Webhook payload must be valid JSON."}) from exc
    event_type = str(payload.get("type") or payload.get("event_type") or "").lower()
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    provider_message_id = data.get("email_id") or data.get("id") or payload.get("provider_message_id")
    mapped_status = {"email.delivered": "SENT", "delivered": "SENT", "email.bounced": "BOUNCED", "bounced": "BOUNCED", "email.complained": "UNSUBSCRIBED", "complained": "UNSUBSCRIBED", "email.unsubscribe": "UNSUBSCRIBED", "unsubscribed": "UNSUBSCRIBED"}.get(event_type)
    matched = bool(provider_message_id and mapped_status and notification_outbox.find_by_provider_message_id(str(provider_message_id)))
    if matched:
        event = notification_outbox.find_by_provider_message_id(str(provider_message_id))
        notification_outbox.mark_delivery(event, event_type, data, mapped_status)
    return {"success": True, "data": {"matched": matched, "status": mapped_status if matched else None}, "error": None, "meta": {"accepted": True}}
