from __future__ import annotations

import hashlib


def publishing_idempotency_key(
    workspace_id: str,
    content_id: str,
    channel: str,
    copy_version: int,
    scheduled_time: str | None,
) -> str:
    raw = "|".join((workspace_id, content_id, channel, str(copy_version), scheduled_time or "immediate"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
