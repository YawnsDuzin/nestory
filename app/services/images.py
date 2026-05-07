"""Synchronous image upload pipeline.

CLAUDE.md alignment: db first arg, user second, returns ORM Image (not bare path).
Async resize dispatched via existing PG queue (workers.queue.enqueue).
"""
import re
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
    """Return (raw_bytes, mime, width, height) or raise 400.

    Reads the body in 64KB chunks and aborts as soon as total exceeds
    max_upload_size — prevents memory exhaustion from a multi-GB streamed body.
    """
    settings = get_settings()
    max_size = settings.max_upload_size
    chunks: list[bytes] = []
    total = 0
    chunk_size = 64 * 1024  # 64KB
    while True:
        chunk = file.file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_size:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "File too large")
        chunks.append(chunk)
    raw = b"".join(chunks)
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


_IMG_REF_RE = re.compile(r"/img/(\d+)/(?:orig|thumb|medium|webp)")


def extract_image_ids(markdown_body: str) -> set[int]:
    """Return the set of internal image IDs referenced in markdown body."""
    return {int(m.group(1)) for m in _IMG_REF_RE.finditer(markdown_body)}


def validate_image_ownership(db: Session, body: str, owner: User) -> None:
    """Raise 400 if body references images not owned by `owner`.

    Prevents a user from embedding another user's uploaded image in their
    post body (attribution leak + storage hot-linking).
    """
    image_ids = extract_image_ids(body)
    if not image_ids:
        return
    rows = db.query(Image.id, Image.owner_id).filter(Image.id.in_(image_ids)).all()
    found_ids = {row.id for row in rows}
    missing = image_ids - found_ids
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"존재하지 않는 이미지 참조: {sorted(missing)}",
        )
    foreign = [row.id for row in rows if row.owner_id != owner.id]
    if foreign:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"본인이 업로드하지 않은 이미지: {sorted(foreign)}",
        )


__all__ = [
    "dispatch_resize",
    "extract_image_ids",
    "store_original",
    "strip_exif",
    "upload_image",
    "validate_image_ownership",
    "validate_upload",
]
