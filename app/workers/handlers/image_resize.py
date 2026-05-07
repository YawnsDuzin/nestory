"""image_resize handler — Pillow-based thumb/medium/webp generation."""
from pathlib import Path
from typing import Any

import structlog
from PIL import Image as PILImage

from app.config import get_settings
from app.db.session import SessionLocal
from app.models import Image
from app.models._enums import ImageStatus, JobKind
from app.workers.handlers import register

log = structlog.get_logger(__name__)

_THUMB_WIDTH = 320
_MEDIUM_WIDTH = 960


def _resize_to_width(src: PILImage.Image, target_w: int) -> PILImage.Image:
    """Return a copy resized to target width, preserving aspect. Never upscales."""
    if src.width <= target_w:
        return src.copy()
    ratio = target_w / src.width
    target_h = int(src.height * ratio)
    return src.resize((target_w, target_h), PILImage.Resampling.LANCZOS)


def _save(img: PILImage.Image, path: Path, fmt: str, quality: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "JPEG" and img.mode != "RGB":
        img = img.convert("RGB")
    img.save(path, format=fmt, quality=quality, optimize=True)


@register(JobKind.IMAGE_RESIZE)
def handle_image_resize(payload: dict[str, Any]) -> None:
    image_id = payload["image_id"]
    settings = get_settings()
    base = Path(settings.image_base_path)

    with SessionLocal() as db:
        img = db.get(Image, image_id)
        if img is None:
            log.warning("image_resize.image_missing", image_id=image_id)
            return
        if img.status == ImageStatus.READY:
            log.info("image_resize.already_ready", image_id=image_id)
            return

        try:
            orig_path = base / img.file_path_orig
            with PILImage.open(orig_path) as src:
                src.load()  # force-decode before context exits
                thumb = _resize_to_width(src, _THUMB_WIDTH)
                medium = _resize_to_width(src, _MEDIUM_WIDTH)

            out_dir = base / "images" / str(image_id)
            _save(thumb, out_dir / "thumb.jpg", "JPEG", 85)
            _save(thumb, out_dir / "thumb.webp", "WEBP", 80)
            _save(medium, out_dir / "medium.jpg", "JPEG", 88)
            _save(medium, out_dir / "medium.webp", "WEBP", 82)

            img.file_path_thumb = f"images/{image_id}/thumb.jpg"
            img.file_path_medium = f"images/{image_id}/medium.jpg"
            img.file_path_webp = f"images/{image_id}/medium.webp"
            img.status = ImageStatus.READY
            db.commit()
            log.info("image_resize.complete", image_id=image_id)
        except Exception as e:
            img.status = ImageStatus.FAILED
            db.commit()
            log.error("image_resize.failed", image_id=image_id, error=str(e))
            raise
