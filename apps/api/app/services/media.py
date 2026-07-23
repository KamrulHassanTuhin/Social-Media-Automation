from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


ALLOWED_MEDIA_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
MAGIC_BYTES = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),
}


class MediaValidationError(ValueError):
    pass


@dataclass(frozen=True)
class StoredMedia:
    id: str
    workspace_id: str
    project_id: str
    content_id: str | None
    original_filename: str
    mime_type: str
    file_size_bytes: int
    storage_path: str
    status: str = "READY"
    delivery_url: str | None = None


class LocalMediaStore:
    def __init__(self, root: str, max_bytes: int = 10_000_000) -> None:
        self.root = Path(root)
        self.max_bytes = max_bytes
        self.assets: dict[str, StoredMedia] = {}

    async def save(self, workspace_id: str, project_id: str, content_id: str | None, filename: str, mime_type: str, content: bytes) -> StoredMedia:
        _validate_media(mime_type, content, self.max_bytes)
        safe_filename = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename or "upload").name)[:120]
        asset_id = str(uuid4())
        relative = Path("workspace") / workspace_id / "project" / project_id / "content" / (content_id or "unattached") / f"{asset_id}{ALLOWED_MEDIA_TYPES[mime_type]}"
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        asset = StoredMedia(asset_id, workspace_id, project_id, content_id, safe_filename, mime_type, len(content), str(relative).replace("\\", "/"))
        self.assets[asset.id] = asset
        return asset


class SupabaseMediaStore:
    def __init__(self, url: str, service_role_key: str, bucket: str, max_bytes: int) -> None:
        from supabase import Client, create_client

        self.client: Client = create_client(url, service_role_key)
        self.bucket = bucket
        self.max_bytes = max_bytes

    async def save(self, workspace_id: str, project_id: str, content_id: str | None, filename: str, mime_type: str, content: bytes) -> StoredMedia:
        _validate_media(mime_type, content, self.max_bytes)
        safe_filename = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename or "upload").name)[:120]
        asset_id = str(uuid4())
        relative = Path("workspace") / workspace_id / "project" / project_id / "content" / (content_id or "unattached") / f"{asset_id}{ALLOWED_MEDIA_TYPES[mime_type]}"
        storage_path = str(relative).replace("\\", "/")
        try:
            self.client.storage.from_(self.bucket).upload(storage_path, content, {"content-type": mime_type, "upsert": False})
            signed = self.client.storage.from_(self.bucket).create_signed_url(storage_path, 3600)
            delivery_url = signed.get("signedURL") or signed.get("signedUrl")
        except Exception as exc:  # noqa: BLE001 - normalize provider errors at the adapter boundary
            raise MediaValidationError(f"Storage upload failed: {exc}") from exc
        return StoredMedia(asset_id, workspace_id, project_id, content_id, safe_filename, mime_type, len(content), storage_path, "READY", delivery_url)


def _validate_media(mime_type: str, content: bytes, max_bytes: int) -> None:
    if mime_type not in ALLOWED_MEDIA_TYPES:
        raise MediaValidationError("Only JPG, PNG, WEBP, and GIF images are supported.")
    if not content:
        raise MediaValidationError("The uploaded file is empty.")
    if len(content) > max_bytes:
        raise MediaValidationError(f"Media must be smaller than {max_bytes // 1_000_000} MB.")
    if not any(content.startswith(signature) for signature in MAGIC_BYTES[mime_type]):
        raise MediaValidationError("The file signature does not match its declared image type.")
    if mime_type == "image/webp" and content[8:12] != b"WEBP":
        raise MediaValidationError("The WEBP file signature is invalid.")


def build_media_store():
    from app.config.settings import get_settings

    settings = get_settings()
    if settings.app_env == "local":
        return LocalMediaStore(settings.media_root, settings.max_upload_bytes)
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required outside local mode.")
    return SupabaseMediaStore(settings.supabase_url, settings.supabase_service_role_key, "axis-media", settings.max_upload_bytes)


media_store = build_media_store()
