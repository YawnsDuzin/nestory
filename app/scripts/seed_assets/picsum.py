"""Picsum random-image download + image pipeline integration for demo seeding."""
from __future__ import annotations

import warnings
from io import BytesIO
from typing import Final

import httpx
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.models import Image, Post, User
from app.services import images as image_service
from app.workers.handlers.image_resize import handle_image_resize

PICSUM_BASE: Final = "https://picsum.photos"
DEFAULT_W: Final = 1280
DEFAULT_H: Final = 720
TIMEOUT_S: Final = 5.0
MAX_FAILURES: Final = 10


class SeedAbort(RuntimeError):
    """Raised when accumulated Picsum failures exceed MAX_FAILURES."""


def _fetch_picsum(seed: int, *, w: int = DEFAULT_W, h: int = DEFAULT_H) -> bytes | None:
    """Download one image. Returns JPEG bytes, or None on any failure."""
    url = f"{PICSUM_BASE}/{w}/{h}?random={seed}"
    try:
        resp = httpx.get(url, timeout=TIMEOUT_S, follow_redirects=True)
        resp.raise_for_status()
        return resp.content
    except httpx.HTTPError as e:
        warnings.warn(f"Picsum fetch failed (seed={seed}): {e}", stacklevel=2)
        return None


def attach_image(db: Session, owner: User, raw: bytes) -> Image | None:
    """Push raw bytes through the image pipeline.

    Re-uses `app.services.images.strip_exif` + `store_original`, then invokes
    `handle_image_resize` synchronously (bypassing the queue) so the resulting
    Image row reaches `status=READY` before this function returns.

    The worker handler opens its own SessionLocal — we MUST commit the new
    Image row first so the handler can SELECT it. Returns the refreshed Image
    or None on failure.
    """
    try:
        with PILImage.open(BytesIO(raw)) as src:
            width, height = src.size
        mime = "image/jpeg"  # Picsum delivers JPEG
        cleaned = image_service.strip_exif(raw, mime)
        img = image_service.store_original(db, owner, cleaned, "jpg", width, height)
        db.commit()  # so worker handler's session can read this row
        handle_image_resize({"image_id": img.id})
        db.refresh(img)  # pick up status=READY + thumb/medium paths
        return img
    except Exception as e:  # noqa: BLE001  — best-effort seeder
        warnings.warn(f"attach_image failed: {e}", stacklevel=2)
        return None


def download_and_attach(
    db: Session,
    post: Post,
    count: int,
    *,
    base_seed: int,
    failure_counter: list[int],
) -> int:
    """Fetch `count` images, attach to post, append `![](/img/<id>/orig)` to body.

    `failure_counter` is a single-element list used as a mutable int across calls
    (callers reuse one counter across the whole seed run). Raises SeedAbort if
    cumulative failures reach MAX_FAILURES. Returns count of successfully
    attached images.
    """
    refs: list[str] = []
    for i in range(count):
        if failure_counter[0] >= MAX_FAILURES:
            raise SeedAbort(
                f"Picsum 누적 실패 ≥ {MAX_FAILURES}회. 네트워크/방화벽/프록시 점검."
            )
        raw = _fetch_picsum(base_seed + i)
        if raw is None:
            failure_counter[0] += 1
            continue
        img = attach_image(db, post.author, raw)
        if img is None:
            failure_counter[0] += 1
            continue
        refs.append(f"![](/img/{img.id}/orig)")
    if refs:
        post.body = (post.body or "") + "\n\n" + "\n\n".join(refs)
        db.flush()
    return len(refs)
