from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.auth.dependencies import CurrentUser, workspace_context
from app.services.media import MediaValidationError, media_store

router = APIRouter(prefix="/media", tags=["media"])


@router.post("/upload", response_model=dict, status_code=status.HTTP_201_CREATED)
async def upload_media(
    file: UploadFile = File(...),
    project_id: str = Form(..., min_length=1),
    content_id: str | None = Form(default=None),
    context: tuple[str, CurrentUser] = Depends(workspace_context),
):
    workspace_id, current_user = context
    try:
        content = await file.read(media_store.max_bytes + 1)
        asset = await media_store.save(workspace_id, project_id, content_id, file.filename or "upload", file.content_type or "application/octet-stream", content)
    except MediaValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": "MEDIA_VALIDATION_ERROR", "message": str(exc)}) from exc
    return {"success": True, "data": {"id": asset.id, "workspace_id": asset.workspace_id, "project_id": asset.project_id, "content_id": asset.content_id, "filename": asset.original_filename, "mime_type": asset.mime_type, "size": asset.file_size_bytes, "storage_path": asset.storage_path, "delivery_url": asset.delivery_url, "status": asset.status, "uploaded_by": current_user.id}, "error": None, "meta": {"local_storage": asset.delivery_url is None}}
