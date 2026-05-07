"""Image upload (HTMX) and static serve routes."""
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.deps import get_db, require_user
from app.models import Image, User
from app.services import images as images_service

router = APIRouter(tags=["images"])


@router.post("/htmx/image/upload")
def upload_image(
    image: UploadFile = File(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> JSONResponse:
    img = images_service.upload_image(db, user, image)
    db.commit()
    return JSONResponse({"image_id": img.id, "url": f"/img/{img.id}/orig"})


@router.get("/img/{image_id}/{variant}")
def serve_image(
    image_id: int,
    variant: str,
    db: Session = Depends(get_db),
) -> FileResponse:
    if variant not in ("orig", "thumb", "medium", "webp"):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    img = db.get(Image, image_id)
    if img is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    variant_path = {
        "orig": img.file_path_orig,
        "thumb": img.file_path_thumb,
        "medium": img.file_path_medium,
        "webp": img.file_path_webp,
    }[variant]
    fallback_used = variant_path is None
    rel_path = variant_path or img.file_path_orig

    full = Path(get_settings().image_base_path) / rel_path
    if not full.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    # Long cache only when serving the requested variant; short cache during fallback
    # so clients re-fetch once the worker fills in the variant.
    cache_value = "public, max-age=60" if fallback_used else "public, max-age=86400"

    media_type = mimetypes.guess_type(str(full))[0] or "application/octet-stream"
    return FileResponse(full, media_type=media_type, headers={"Cache-Control": cache_value})
