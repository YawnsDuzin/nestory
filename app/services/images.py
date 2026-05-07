"""Synchronous image upload pipeline.

CLAUDE.md alignment: db first arg, user second, returns ORM Image (not bare path).
Async resize dispatched via existing PG queue (workers.queue.enqueue).
"""
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Final
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from PIL import Image as PILImage
from PIL import UnidentifiedImageError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Image, User
from app.models._enums import ImageStatus, JobKind
from app.workers import queue

_ALLOWED_MIME: Final[set[str]] = {"image/jpeg", "image/png", "image/webp"}
_MAGIC: Final[dict[str, bytes]] = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/webp": b"RIFF",  # full magic is RIFF....WEBP — checked in code
}
_EXT_FOR_MIME: Final[dict[str, str]] = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
_MIME_FOR_EXT: Final[dict[str, str]] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _infer_mime(file: UploadFile) -> str:
    """Prefer client-supplied content_type; fall back to filename extension."""
    if file.content_type:
        return file.content_type
    if file.filename:
        suffix = PurePosixPath(file.filename).suffix.lower()
        return _MIME_FOR_EXT.get(suffix, "")
    return ""


def validate_upload(file: UploadFile) -> tuple[bytes, str, int, int]:
    """Return (raw_bytes, mime, width, height) or raise 400."""
    settings = get_settings()
    raw = file.file.read()
    if len(raw) > settings.max_upload_size:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File too large")
    if len(raw) < 16:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File too small")
    mime = _infer_mime(file)
    if mime not in _ALLOWED_MIME:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unsupported mime: {mime}")
    expected_magic = _MAGIC[mime]
    if mime == "image/webp":
        if raw[:4] != b"RIFF" or raw[8:12] != b"WEBP":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bad WebP magic")
    elif not raw.startswith(expected_magic):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Bad magic bytes")
    try:
        with PILImage.open(BytesIO(raw)) as img:
            width, height = img.size
    except UnidentifiedImageError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot decode image") from e
    if width > settings.image_max_dimension or height > settings.image_max_dimension:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Dimensions too large")
    return raw, mime, width, height


def strip_exif(raw: bytes, mime: str) -> bytes:
    """Re-encode without EXIF (removes GPS, camera info, etc)."""
    out = BytesIO()
    with PILImage.open(BytesIO(raw)) as img:
        if mime == "image/jpeg":
            img.save(out, format="JPEG", quality=92, optimize=True, exif=b"")
        elif mime == "image/png":
            img.save(out, format="PNG", optimize=True)
        else:  # image/webp
            img.save(out, format="WEBP", quality=90)
    return out.getvalue()


def store_original(
    db: Session, owner: User, raw_clean: bytes, ext: str, width: int, height: int
) -> Image:
    """Write to disk + insert Image row (status=PROCESSING)."""
    settings = get_settings()
    uid = uuid4().hex
    rel_path = f"images/{uid}/orig.{ext}"
    full = Path(settings.image_base_path) / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_bytes(raw_clean)

    img = Image(
        owner_id=owner.id,
        file_path_orig=rel_path,
        status=ImageStatus.PROCESSING,
        width=width,
        height=height,
        size_bytes=len(raw_clean),
    )
    db.add(img)
    db.flush()
    return img


def dispatch_resize(db: Session, image: Image) -> None:
    """Enqueue JobKind.IMAGE_RESIZE for this image."""
    queue.enqueue(db, JobKind.IMAGE_RESIZE, {"image_id": image.id})


def upload_image(db: Session, owner: User, file: UploadFile) -> Image:
    """Single entrypoint: validate + strip + store + dispatch. Returns Image."""
    raw, mime, w, h = validate_upload(file)
    cleaned = strip_exif(raw, mime)
    ext = _EXT_FOR_MIME[mime]
    img = store_original(db, owner, cleaned, ext, w, h)
    dispatch_resize(db, img)
    return img


__all__ = [
    "dispatch_resize",
    "store_original",
    "strip_exif",
    "upload_image",
    "validate_upload",
]
