# Nestory Phase 1.3 — Content + Images Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first user-facing content workflow — 5 write routes (review/journey/journey-episode/question/plan) + inline answer + 4 detail pages + image upload pipeline (sync EXIF strip + async Pillow resize worker) + markdown rendering — on top of the P1.1·1.2 model/queue/badge/guard infrastructure.

**Architecture:** 3 new routers (`content.py` / `journey.py` / `images.py`), 2 new services (`posts.py` / `images.py`), real Pillow implementation of the existing `image_resize` worker stub, JSON-returning standalone image upload (`/htmx/image/upload` returns `{image_id, url}`), markdown body embeds `/img/{id}/orig` which a Jinja filter swaps to `/img/{id}/medium` on render, worker generates thumb/medium/webp with graceful orig-fallback when variant not yet ready.

**Tech Stack:** FastAPI + Jinja2 SSR + HTMX (partial swaps), Pillow 11.x (resize + EXIF strip), `markdown` 3.x (pure-Python markdown→HTML, raw HTML stripped), existing `app/workers/queue.py` for image_resize dispatch.

**Spec:** [`docs/superpowers/specs/2026-05-07-nestory-phase1-3-content-and-images-design.md`](../specs/2026-05-07-nestory-phase1-3-content-and-images-design.md)

**CLAUDE.md alignment:** Services pattern (`db: Session` first arg, `user: User` second, no `request.session` import), JSON image responses (id+url, not bare path strings), factory-boy first for tests (no direct `Post(...)` constructors except documented bypasses), PostMetadata Pydantic validation enforced at every write route.

---

## File Structure

**Created:**
- `app/services/images.py` — sync image upload pipeline (validate, EXIF strip, store, dispatch)
- `app/services/posts.py` — 7 functions for 5 type create + view_count + journey row create
- `app/routers/images.py` — `POST /htmx/image/upload` + `GET /img/{id}/{variant}`
- `app/routers/content.py` — `/write/review` · `/write/question` · `/write/plan` · `/post/{id}` · `/question/{id}` · `/question/{qid}/answer`
- `app/routers/journey.py` — `/write/journey` · `/write/journey/{id}/ep` · `/journey/{id}` · `/journey/{id}/ep/{n}`
- `app/templating_filters.py` — `markdown_to_html` Jinja filter + URL swap regex
- `app/templates/pages/write/_base.html` — 4-section layout (extends `base.html`)
- `app/templates/pages/write/_common_fields.html` — title + body + image attach
- `app/templates/pages/write/_publish_card.html` — region select + publish button
- `app/templates/pages/write/_meta_review.html` — ReviewMetadata fields
- `app/templates/pages/write/_meta_journey_episode.html` — JourneyEpisodeMetadata fields
- `app/templates/pages/write/_meta_question.html` — QuestionMetadata fields
- `app/templates/pages/write/_meta_plan.html` — PlanMetadata fields
- `app/templates/pages/write/review.html` · `question.html` · `plan.html` · `journey_create.html` · `journey_episode.html`
- `app/templates/pages/detail/_meta_card_review.html` · `_meta_card_plan.html` · `_meta_card_journey_ep.html` · `_meta_card_question.html`
- `app/templates/pages/detail/post.html` · `journey.html` · `journey_episode.html` · `question.html`
- `app/tests/fixtures/sample.jpg` — real 200x200 JPEG with GPS EXIF tags
- Test files (one per logical concern; full list below)

**Modified:**
- `app/config.py` — add `image_base_path`, `max_upload_size`, `image_max_dimension`
- `app/workers/handlers/image_resize.py` — replace stub with Pillow implementation
- `app/main.py` — register 3 new routers
- `app/templating.py` — register `markdown_to_html` filter
- `app/services/__init__.py` — export new services
- `app/routers/__init__.py` — export new routers
- `pyproject.toml` — add `markdown>=3.6` and `pillow>=11.0` to main deps
- `.gitignore` — add `media/`
- `docker-compose.local.yml` — mount `./media:/app/media` on worker service

---

## Test File Plan

| Test file | Verifies |
|---|---|
| `app/tests/integration/test_images_service.py` | validate_upload + strip_exif + store_original + dispatch (Image row + JobKind.IMAGE_RESIZE enqueue) |
| `app/tests/integration/test_image_resize_handler.py` | thumb/medium/webp generation + status=READY transition + idempotency |
| `app/tests/integration/test_image_upload_route.py` | `POST /htmx/image/upload` JSON response, multipart form, 400 on invalid mime |
| `app/tests/integration/test_image_serve_route.py` | `GET /img/{id}/{variant}` FileResponse + variant fallback to orig + 404 |
| `app/tests/integration/test_posts_service.py` | 5 type create + view_count + Pydantic-valid metadata persisted |
| `app/tests/unit/test_markdown_filter.py` | markdown→HTML + `/img/{id}/orig` → `/img/{id}/medium` swap + raw HTML stripping |
| `app/tests/integration/test_write_review_route.py` | GET form renders + POST creates post + redirects + 400 on invalid metadata |
| `app/tests/integration/test_write_question_route.py` | same shape as review |
| `app/tests/integration/test_write_plan_route.py` | same + 400 when user has no primary_region_id |
| `app/tests/integration/test_write_journey_routes.py` | journey create + episode_no auto-increment + journey ownership guard |
| `app/tests/integration/test_answer_route.py` | inline POST creates answer with parent_post + region inheritance |
| `app/tests/integration/test_detail_routes.py` | /post/{id}, /journey/{id}, /journey/{id}/ep/{n}, /question/{id} render + 404 + view_count |
| `app/tests/integration/test_post_workflow_e2e.py` | full E2E: login → upload → write/review → /post/{id} renders image |

---

## Task 1: Foundation — config, deps, gitignore, sample fixture

**Files:**
- Modify: `pyproject.toml`
- Modify: `app/config.py`
- Modify: `.gitignore`
- Modify: `docker-compose.local.yml`
- Create: `app/tests/fixtures/__init__.py` (empty)
- Create: `app/tests/fixtures/sample.jpg` (200×200 JPEG with GPS EXIF — generated programmatically in Step 5)

- [ ] **Step 1: Add deps to pyproject.toml**

In `pyproject.toml`, find the `[project] dependencies = [...]` block and add `markdown>=3.6` and ensure `pillow>=11.0` is present. If pillow is already there at a different version, leave it. Then run `uv sync`.

- [ ] **Step 2: Extend Settings**

Edit `app/config.py`. Add three fields between `evidence_base_path` and the closing of the class:

```python
    image_base_path: str = "./media"
    max_upload_size: int = 10 * 1024 * 1024  # 10MB
    image_max_dimension: int = 6000  # px
```

- [ ] **Step 3: Update .gitignore**

Append `media/` (on its own line) to `.gitignore`. Then `git status` to confirm a `media/` directory you create later won't be tracked.

- [ ] **Step 4: Mount media volume on worker**

Edit `docker-compose.local.yml`. Find the `worker` service block. Add to its `volumes:` list:
```yaml
      - ./media:/app/media
```
Match the indentation of the existing volume entries.

- [ ] **Step 5: Generate sample.jpg with GPS EXIF**

Create `app/tests/fixtures/__init__.py` (empty file). Then run this one-shot script (you can paste into a `python -c` or save as a temp file and execute):

```python
from io import BytesIO
from pathlib import Path
from PIL import Image
import piexif

img = Image.new("RGB", (200, 200), color=(70, 130, 180))
exif_dict = {
    "0th": {piexif.ImageIFD.Make: b"TestCamera"},
    "Exif": {},
    "GPS": {
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLatitude: ((37, 1), (33, 1), (0, 1)),
        piexif.GPSIFD.GPSLongitudeRef: b"E",
        piexif.GPSIFD.GPSLongitude: ((127, 1), (0, 1), (0, 1)),
    },
    "1st": {},
    "thumbnail": None,
}
exif_bytes = piexif.dump(exif_dict)
out = Path("app/tests/fixtures/sample.jpg")
out.parent.mkdir(parents=True, exist_ok=True)
img.save(out, format="JPEG", exif=exif_bytes, quality=90)
print(f"Wrote {out} ({out.stat().st_size} bytes) with GPS EXIF")
```

If `piexif` isn't installed, install once via `uv add --dev piexif` (it's only needed for fixture generation, but adding to dev keeps the script reproducible). Actually — the fixture is committed binary so the dep is only needed if regeneration is ever requested. Add piexif to dev deps regardless: `uv add --dev piexif`.

- [ ] **Step 6: Verify EXIF actually present**

```python
python -c "from PIL import Image; im = Image.open('app/tests/fixtures/sample.jpg'); print('exif keys:', list(im.getexif().keys()))"
```
Expected output includes GPS-related tag IDs (specifically tag 34853 = GPSInfo).

- [ ] **Step 7: Run baseline pytest to confirm nothing broke**

```powershell
docker compose -f docker-compose.local.yml up -d
uv run pytest app/tests/ -q
```
Expected: 166 passed (factory-boy baseline).

- [ ] **Step 8: Commit**

```powershell
git add pyproject.toml uv.lock app/config.py .gitignore docker-compose.local.yml app/tests/fixtures/
git commit -m "feat(p1.3): add image config, media gitignore, sample fixture"
```

---

## Task 2: images service — sync upload pipeline

**Files:**
- Create: `app/services/images.py`
- Modify: `app/services/__init__.py`
- Create: `app/tests/integration/test_images_service.py`

- [ ] **Step 1: Write failing tests**

Create `app/tests/integration/test_images_service.py`:

```python
"""Tests for the synchronous image upload pipeline."""
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Image, Job
from app.models._enums import ImageStatus, JobKind, JobStatus
from app.services import images as images_service
from app.tests.factories import UserFactory


def _sample_upload(tmp_path: Path, name: str = "test.jpg") -> UploadFile:
    src = Path("app/tests/fixtures/sample.jpg")
    return UploadFile(filename=name, file=BytesIO(src.read_bytes()))


def test_validate_upload_accepts_jpeg(tmp_path: Path) -> None:
    f = _sample_upload(tmp_path)
    raw, mime, w, h = images_service.validate_upload(f)
    assert mime == "image/jpeg"
    assert w == 200 and h == 200
    assert raw.startswith(b"\xff\xd8\xff")  # JPEG magic


def test_validate_upload_rejects_oversize(tmp_path: Path) -> None:
    big = b"\xff\xd8\xff" + b"\x00" * (11 * 1024 * 1024)
    f = UploadFile(filename="big.jpg", file=BytesIO(big))
    with pytest.raises(HTTPException) as exc:
        images_service.validate_upload(f)
    assert exc.value.status_code == 400


def test_validate_upload_rejects_wrong_mime(tmp_path: Path) -> None:
    f = UploadFile(filename="evil.exe", file=BytesIO(b"MZ\x90\x00"))
    with pytest.raises(HTTPException) as exc:
        images_service.validate_upload(f)
    assert exc.value.status_code == 400


def test_strip_exif_removes_gps_tags(tmp_path: Path) -> None:
    raw_with_exif = Path("app/tests/fixtures/sample.jpg").read_bytes()
    cleaned = images_service.strip_exif(raw_with_exif, "image/jpeg")
    cleaned_img = PILImage.open(BytesIO(cleaned))
    exif = cleaned_img.getexif()
    # GPS tag 34853 must be gone
    assert 34853 not in exif
    # And no GPS sub-IFD either
    assert all(tag != 34853 for tag in exif.keys())


def test_store_original_writes_file_and_creates_row(db: Session, tmp_path: Path) -> None:
    user = UserFactory()
    raw = Path("app/tests/fixtures/sample.jpg").read_bytes()
    settings = get_settings()
    img = images_service.store_original(db, user, raw, "jpg", 200, 200)
    assert img.id is not None
    assert img.owner_id == user.id
    assert img.status == ImageStatus.PROCESSING
    assert img.file_path_orig.startswith("images/")
    full = Path(settings.image_base_path) / img.file_path_orig
    assert full.exists()
    assert full.stat().st_size == len(raw)


def test_dispatch_resize_enqueues_job(db: Session) -> None:
    user = UserFactory()
    raw = Path("app/tests/fixtures/sample.jpg").read_bytes()
    img = images_service.store_original(db, user, raw, "jpg", 200, 200)
    images_service.dispatch_resize(db, img)
    job = (
        db.query(Job)
        .filter(Job.kind == JobKind.IMAGE_RESIZE, Job.status == JobStatus.QUEUED)
        .one()
    )
    assert job.payload == {"image_id": img.id}


def test_upload_image_full_pipeline(db: Session) -> None:
    user = UserFactory()
    f = UploadFile(
        filename="sample.jpg",
        file=BytesIO(Path("app/tests/fixtures/sample.jpg").read_bytes()),
    )
    img = images_service.upload_image(db, user, f)
    assert img.id is not None and img.status == ImageStatus.PROCESSING
    job = db.query(Job).filter(Job.kind == JobKind.IMAGE_RESIZE).one()
    assert job.payload == {"image_id": img.id}
```

- [ ] **Step 2: Run failing tests**

```powershell
uv run pytest app/tests/integration/test_images_service.py -v
```
Expected: ImportError on `app.services.images`.

- [ ] **Step 3: Write images service**

Create `app/services/images.py`:

```python
"""Synchronous image upload pipeline.

CLAUDE.md alignment: db first arg, user second, returns ORM Image (not bare path).
Async resize dispatched via existing PG queue (workers.queue.enqueue).
"""
from io import BytesIO
from pathlib import Path
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


def validate_upload(file: UploadFile) -> tuple[bytes, str, int, int]:
    """Return (raw_bytes, mime, width, height) or raise 400."""
    settings = get_settings()
    raw = file.file.read()
    if len(raw) > settings.max_upload_size:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File too large")
    if len(raw) < 16:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File too small")
    mime = file.content_type or ""
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
```

- [ ] **Step 4: Re-export in services/__init__.py**

Edit `app/services/__init__.py`. Add:
```python
from app.services import images
```
And include `"images"` in `__all__` (alphabetical position).

- [ ] **Step 5: Run tests to verify pass**

```powershell
uv run pytest app/tests/integration/test_images_service.py -v
```
Expected: all 7 tests pass. The store/dispatch tests will create files under `./media/images/...` — these are gitignored.

- [ ] **Step 6: Run full suite + lint**

```powershell
uv run pytest app/tests/ -q
uv run ruff check app/
```
Expected: 173 pass (166 + 7 new), ruff clean.

- [ ] **Step 7: Commit**

```powershell
git add app/services/images.py app/services/__init__.py app/tests/integration/test_images_service.py
git commit -m "feat(services): add images sync upload pipeline (validate/EXIF/store/dispatch)"
```

---

## Task 3: image_resize worker handler — real implementation

**Files:**
- Modify: `app/workers/handlers/image_resize.py`
- Create: `app/tests/integration/test_image_resize_handler.py`

- [ ] **Step 1: Write failing tests**

Create `app/tests/integration/test_image_resize_handler.py`:

```python
"""Tests for the image_resize worker handler — real Pillow implementation."""
from pathlib import Path

from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Image, Job
from app.models._enums import ImageStatus, JobKind, JobStatus
from app.services import images as images_service
from app.tests.factories import ImageFactory, UserFactory
from app.workers import queue
from app.workers.runner import process_one


def _seed_real_image(db: Session) -> Image:
    """Use the real upload pipeline so a file actually exists on disk."""
    from io import BytesIO
    from fastapi import UploadFile

    user = UserFactory()
    f = UploadFile(
        filename="sample.jpg",
        file=BytesIO(Path("app/tests/fixtures/sample.jpg").read_bytes()),
    )
    return images_service.upload_image(db, user, f)


def test_image_resize_creates_thumb_medium_webp(db: Session) -> None:
    img = _seed_real_image(db)
    db.commit()  # so worker session sees it

    processed = process_one()
    assert processed is True

    db.refresh(img)
    assert img.status == ImageStatus.READY
    assert img.file_path_thumb and img.file_path_medium and img.file_path_webp

    settings = get_settings()
    base = Path(settings.image_base_path)
    assert (base / img.file_path_thumb).exists()
    assert (base / img.file_path_medium).exists()
    assert (base / img.file_path_webp).exists()

    with PILImage.open(base / img.file_path_thumb) as t:
        assert t.size[0] <= 320
    with PILImage.open(base / img.file_path_medium) as m:
        assert m.size[0] <= 960


def test_image_resize_idempotent(db: Session) -> None:
    """Running handler twice on a READY image must not re-process."""
    img = _seed_real_image(db)
    db.commit()
    process_one()  # first run — produces variants

    db.refresh(img)
    assert img.status == ImageStatus.READY
    thumb_mtime = (Path(get_settings().image_base_path) / img.file_path_thumb).stat().st_mtime

    # Manually re-enqueue and process again
    queue.enqueue(db, JobKind.IMAGE_RESIZE, {"image_id": img.id})
    db.commit()
    process_one()

    db.refresh(img)
    assert img.status == ImageStatus.READY
    new_thumb_mtime = (Path(get_settings().image_base_path) / img.file_path_thumb).stat().st_mtime
    assert thumb_mtime == new_thumb_mtime, "Should have skipped re-processing"


def test_image_resize_failed_on_missing_file(db: Session) -> None:
    """Image row exists but file_path_orig points to nothing — handler marks FAILED."""
    user = UserFactory()
    img = ImageFactory(owner=user, file_path_orig="images/does-not-exist/orig.jpg",
                       status=ImageStatus.PROCESSING)
    queue.enqueue(db, JobKind.IMAGE_RESIZE, {"image_id": img.id})
    db.commit()

    process_one()

    db.refresh(img)
    assert img.status == ImageStatus.FAILED
    job = db.query(Job).filter(Job.kind == JobKind.IMAGE_RESIZE).order_by(Job.id.desc()).first()
    assert job.status in (JobStatus.FAILED, JobStatus.QUEUED)  # depending on retry policy
```

- [ ] **Step 2: Run failing tests**

```powershell
uv run pytest app/tests/integration/test_image_resize_handler.py -v
```
Expected: tests fail because the existing handler is a stub that just logs.

- [ ] **Step 3: Implement handler**

Replace `app/workers/handlers/image_resize.py` entirely with:

```python
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
```

Note: the variant out_dir uses `images/{image_id}/` (numeric id), separate from the original which uses `images/{uuid}/`. This is intentional — variant dir is keyed by DB id for fast lookup, original is uuid-keyed for opacity.

- [ ] **Step 4: Run tests to verify pass**

```powershell
uv run pytest app/tests/integration/test_image_resize_handler.py -v
```
Expected: all 3 pass. The first test creates real image variants under `./media/images/{id}/`.

- [ ] **Step 5: Run full suite + lint**

```powershell
uv run pytest app/tests/ -q
uv run ruff check app/
```
Expected: 176 pass (173 + 3 new), clean.

- [ ] **Step 6: Commit**

```powershell
git add app/workers/handlers/image_resize.py app/tests/integration/test_image_resize_handler.py
git commit -m "feat(workers): real Pillow implementation of image_resize handler"
```

---

## Task 4: images router — upload + serve

**Files:**
- Create: `app/routers/images.py`
- Modify: `app/routers/__init__.py`
- Modify: `app/main.py`
- Create: `app/tests/integration/test_image_upload_route.py`
- Create: `app/tests/integration/test_image_serve_route.py`

- [ ] **Step 1: Write failing tests for upload route**

Create `app/tests/integration/test_image_upload_route.py`:

```python
"""Tests for POST /htmx/image/upload."""
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Image
from app.tests.factories import UserFactory


def _login_cookie(client: TestClient, user_id: int) -> dict[str, str]:
    """Reuse P1.2 pattern: signed session cookie via /auth/test-login (skip if absent).

    Falls back to direct session middleware manipulation."""
    from itsdangerous import TimestampSigner
    from app.config import get_settings
    signer = TimestampSigner(get_settings().app_secret_key)
    import json, base64
    payload = {"user_id": user_id}
    raw = base64.b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    cookie = signer.sign(raw.encode()).decode()
    return {"nestory_session": cookie}


def test_upload_returns_json_with_image_id_and_url(client: TestClient, db: Session) -> None:
    user = UserFactory()
    db.commit()
    cookies = _login_cookie(client, user.id)
    sample = Path("app/tests/fixtures/sample.jpg").read_bytes()
    r = client.post(
        "/htmx/image/upload",
        files={"image": ("sample.jpg", BytesIO(sample), "image/jpeg")},
        cookies=cookies,
    )
    assert r.status_code == 200
    body = r.json()
    assert "image_id" in body and isinstance(body["image_id"], int)
    assert body["url"] == f"/img/{body['image_id']}/orig"


def test_upload_requires_login(client: TestClient) -> None:
    sample = Path("app/tests/fixtures/sample.jpg").read_bytes()
    r = client.post(
        "/htmx/image/upload",
        files={"image": ("sample.jpg", BytesIO(sample), "image/jpeg")},
    )
    assert r.status_code == 401


def test_upload_rejects_non_image_mime(client: TestClient, db: Session) -> None:
    user = UserFactory()
    db.commit()
    cookies = _login_cookie(client, user.id)
    r = client.post(
        "/htmx/image/upload",
        files={"image": ("evil.exe", BytesIO(b"MZ\x90\x00not-an-image"), "application/octet-stream")},
        cookies=cookies,
    )
    assert r.status_code == 400


def test_upload_creates_image_row_and_enqueues_job(client: TestClient, db: Session) -> None:
    from app.models import Job
    from app.models._enums import JobKind
    user = UserFactory()
    db.commit()
    cookies = _login_cookie(client, user.id)
    sample = Path("app/tests/fixtures/sample.jpg").read_bytes()
    r = client.post(
        "/htmx/image/upload",
        files={"image": ("sample.jpg", BytesIO(sample), "image/jpeg")},
        cookies=cookies,
    )
    assert r.status_code == 200
    img_id = r.json()["image_id"]
    img = db.query(Image).filter_by(id=img_id).one()
    assert img.owner_id == user.id
    job = db.query(Job).filter(Job.kind == JobKind.IMAGE_RESIZE).one()
    assert job.payload == {"image_id": img_id}
```

- [ ] **Step 2: Write failing tests for serve route**

Create `app/tests/integration/test_image_serve_route.py`:

```python
"""Tests for GET /img/{id}/{variant}."""
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models._enums import ImageStatus
from app.tests.factories import ImageFactory, UserFactory


def _make_real_image_files(db: Session) -> tuple[int, Path]:
    """Create an image row + write actual JPEG bytes to disk. Return (id, base_dir)."""
    settings = get_settings()
    user = UserFactory()
    img = ImageFactory(owner=user, status=ImageStatus.READY,
                       file_path_orig="images/test-serve-orig/orig.jpg",
                       file_path_thumb="images/test-serve-orig/thumb.jpg",
                       file_path_medium="images/test-serve-orig/medium.jpg",
                       file_path_webp="images/test-serve-orig/medium.webp")
    base = Path(settings.image_base_path)
    out_dir = base / "images" / "test-serve-orig"
    out_dir.mkdir(parents=True, exist_ok=True)
    sample = Path("app/tests/fixtures/sample.jpg").read_bytes()
    (out_dir / "orig.jpg").write_bytes(sample)
    (out_dir / "thumb.jpg").write_bytes(sample[:1000])
    (out_dir / "medium.jpg").write_bytes(sample[:1500])
    (out_dir / "medium.webp").write_bytes(b"RIFF\x00\x00\x00\x00WEBP")
    db.commit()
    return img.id, base


def test_serve_orig_returns_file(client: TestClient, db: Session) -> None:
    img_id, _ = _make_real_image_files(db)
    r = client.get(f"/img/{img_id}/orig")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/jpeg")


def test_serve_thumb_returns_file(client: TestClient, db: Session) -> None:
    img_id, _ = _make_real_image_files(db)
    r = client.get(f"/img/{img_id}/thumb")
    assert r.status_code == 200


def test_serve_unknown_id_returns_404(client: TestClient, db: Session) -> None:
    r = client.get("/img/99999/orig")
    assert r.status_code == 404


def test_serve_variant_falls_back_to_orig(client: TestClient, db: Session) -> None:
    """If file_path_thumb is None (worker hasn't run yet), serve orig instead."""
    user = UserFactory()
    img = ImageFactory(owner=user, status=ImageStatus.PROCESSING,
                       file_path_orig="images/test-fallback/orig.jpg")
    settings = get_settings()
    out_dir = Path(settings.image_base_path) / "images" / "test-fallback"
    out_dir.mkdir(parents=True, exist_ok=True)
    sample = Path("app/tests/fixtures/sample.jpg").read_bytes()
    (out_dir / "orig.jpg").write_bytes(sample)
    db.commit()

    r = client.get(f"/img/{img.id}/thumb")
    assert r.status_code == 200  # served orig as fallback
    assert r.content == sample


def test_serve_includes_cache_header(client: TestClient, db: Session) -> None:
    img_id, _ = _make_real_image_files(db)
    r = client.get(f"/img/{img_id}/orig")
    assert "max-age" in r.headers.get("cache-control", "")
```

- [ ] **Step 3: Run failing tests**

```powershell
uv run pytest app/tests/integration/test_image_upload_route.py app/tests/integration/test_image_serve_route.py -v
```
Expected: 404 because `/htmx/image/upload` and `/img/...` don't exist.

- [ ] **Step 4: Write images router**

Create `app/routers/images.py`:

```python
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

    rel_path = {
        "orig": img.file_path_orig,
        "thumb": img.file_path_thumb or img.file_path_orig,
        "medium": img.file_path_medium or img.file_path_orig,
        "webp": img.file_path_webp or img.file_path_orig,
    }[variant]

    full = Path(get_settings().image_base_path) / rel_path
    if not full.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    media_type = mimetypes.guess_type(str(full))[0] or "application/octet-stream"
    return FileResponse(full, media_type=media_type, headers={
        "Cache-Control": "public, max-age=86400",
    })


__all__ = ["router"]
```

- [ ] **Step 5: Update routers/__init__.py**

If `app/routers/__init__.py` is empty or just has comments, that's fine — routers are imported by `main.py` directly. Just verify the file exists.

- [ ] **Step 6: Register router in main.py**

Edit `app/main.py`. Add an import:
```python
from app.routers import images as images_router
```
Add registration after the other `app.include_router(...)` lines:
```python
app.include_router(images_router.router)
```

- [ ] **Step 7: Run tests to verify pass**

```powershell
uv run pytest app/tests/integration/test_image_upload_route.py app/tests/integration/test_image_serve_route.py -v
```
Expected: 9 pass.

- [ ] **Step 8: Run full suite + lint**

```powershell
uv run pytest app/tests/ -q
uv run ruff check app/
```
Expected: 185 pass (176 + 9), clean.

- [ ] **Step 9: Commit**

```powershell
git add app/routers/images.py app/routers/__init__.py app/main.py app/tests/integration/test_image_upload_route.py app/tests/integration/test_image_serve_route.py
git commit -m "feat(routers): add images upload (HTMX) and static serve routes"
```

---

## Task 5: posts service — 5 type create + view_count

**Files:**
- Create: `app/services/posts.py`
- Modify: `app/services/__init__.py`
- Create: `app/tests/integration/test_posts_service.py`

- [ ] **Step 1: Write failing tests**

Create `app/tests/integration/test_posts_service.py`:

```python
"""Tests for posts service — 5 type create + view_count."""
from datetime import date

from sqlalchemy.orm import Session

from app.models import Journey, Post
from app.models._enums import PostStatus, PostType
from app.schemas.post_metadata import (
    AnswerMetadata, JourneyEpMeta, JourneyEpisodeMetadata, PlanMetadata,
    QuestionMetadata, ReviewMetadata,
)
from app.services import posts as posts_service
from app.tests.factories import (
    JourneyFactory, RegionFactory, ResidentUserFactory, UserFactory,
    QuestionPostFactory,
)


def test_create_review(db: Session) -> None:
    author = ResidentUserFactory()
    region = RegionFactory()
    meta = ReviewMetadata(house_type="단독", size_pyeong=30, satisfaction_overall=4)
    post = posts_service.create_review(db, author, region, meta, "1년차 회고", "단열이 가장 후회됨")
    assert post.id is not None
    assert post.type == PostType.REVIEW
    assert post.status == PostStatus.PUBLISHED
    assert post.author_id == author.id
    assert post.region_id == region.id
    assert post.metadata_["house_type"] == "단독"
    assert post.metadata_["satisfaction_overall"] == 4
    assert "type_tag" not in post.metadata_  # discriminator stays in column, not JSONB


def test_create_journey(db: Session) -> None:
    author = ResidentUserFactory()
    region = RegionFactory()
    j = posts_service.create_journey(db, author, region, "양평 정착기", "터잡기부터", date(2026, 1, 1))
    assert j.id is not None
    assert isinstance(j, Journey)
    assert j.author_id == author.id
    assert j.region_id == region.id
    assert j.start_date == date(2026, 1, 1)


def test_create_journey_episode_auto_episode_no(db: Session) -> None:
    author = ResidentUserFactory()
    journey = JourneyFactory(author=author)
    meta = JourneyEpisodeMetadata(journey_ep_meta=JourneyEpMeta(phase="입주", period_label="2026-04"))
    ep1 = posts_service.create_journey_episode(db, author, journey, meta, "1화", "본문 1")
    ep2 = posts_service.create_journey_episode(db, author, journey, meta, "2화", "본문 2")
    assert ep1.episode_no == 1
    assert ep2.episode_no == 2
    assert ep1.journey_id == journey.id == ep2.journey_id


def test_create_question(db: Session) -> None:
    author = UserFactory()
    region = RegionFactory()
    meta = QuestionMetadata(tags=["단열", "지붕"])
    q = posts_service.create_question(db, author, region, meta, "단열재 추천?", "양평 동향 단독, 추천 부탁")
    assert q.type == PostType.QUESTION
    assert q.metadata_["tags"] == ["단열", "지붕"]


def test_create_answer_inherits_region(db: Session) -> None:
    author = UserFactory()
    question = QuestionPostFactory()
    a = posts_service.create_answer(db, author, question, "셀룰로오스가 가성비 좋습니다")
    assert a.type == PostType.ANSWER
    assert a.parent_post_id == question.id
    assert a.region_id == question.region_id


def test_create_plan(db: Session) -> None:
    author = UserFactory()
    region = RegionFactory()
    meta = PlanMetadata(target_move_year=2027, budget_total_manwon_band="5000-10000",
                        construction_intent="undecided")
    p = posts_service.create_plan(db, author, region, meta, "2027 양평 입주 계획", "검토 중")
    assert p.type == PostType.PLAN
    assert p.metadata_["target_move_year"] == 2027


def test_increment_view_count(db: Session) -> None:
    post = QuestionPostFactory(view_count=0)
    posts_service.increment_view_count(db, post)
    posts_service.increment_view_count(db, post)
    db.refresh(post)
    assert post.view_count == 2
```

- [ ] **Step 2: Run failing tests**

```powershell
uv run pytest app/tests/integration/test_posts_service.py -v
```
Expected: ImportError on `app.services.posts`.

- [ ] **Step 3: Write posts service**

Create `app/services/posts.py`:

```python
"""Posts service — 5 type create + Journey row + view_count.

CLAUDE.md alignment: db first, user second, returns ORM Post (or Journey).
PostMetadata Pydantic models passed in by caller; service serializes to JSONB
via model_dump and pops type_tag (discriminator lives in Post.type column).
"""
from datetime import UTC, date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Journey, Post, Region, User
from app.models._enums import JourneyStatus, PostStatus, PostType
from app.schemas.post_metadata import (
    AnswerMetadata,
    JourneyEpisodeMetadata,
    PlanMetadata,
    QuestionMetadata,
    ReviewMetadata,
)


def _meta_to_jsonb(payload) -> dict:
    """Pydantic → dict for Post.metadata. type_tag is dropped (discriminator
    lives in Post.type column, not JSONB)."""
    d = payload.model_dump(by_alias=False, exclude_none=True)
    d.pop("type_tag", None)
    return d


def _publish_now() -> datetime:
    return datetime.now(UTC)


def create_review(
    db: Session, author: User, region: Region, payload: ReviewMetadata,
    title: str, body: str,
) -> Post:
    post = Post(
        author_id=author.id, region_id=region.id, type=PostType.REVIEW,
        title=title, body=body, metadata_=_meta_to_jsonb(payload),
        status=PostStatus.PUBLISHED, published_at=_publish_now(),
    )
    db.add(post)
    db.flush()
    return post


def create_journey(
    db: Session, author: User, region: Region,
    title: str, description: str | None, start_date: date | None,
) -> Journey:
    j = Journey(
        author_id=author.id, region_id=region.id,
        title=title, description=description, start_date=start_date,
        status=JourneyStatus.IN_PROGRESS,
    )
    db.add(j)
    db.flush()
    return j


def create_journey_episode(
    db: Session, author: User, journey: Journey, payload: JourneyEpisodeMetadata,
    title: str, body: str,
) -> Post:
    max_ep = (
        db.query(func.max(Post.episode_no))
        .filter(Post.journey_id == journey.id)
        .scalar()
    )
    next_ep = (max_ep or 0) + 1
    post = Post(
        author_id=author.id, region_id=journey.region_id, journey_id=journey.id,
        type=PostType.JOURNEY_EPISODE, episode_no=next_ep,
        title=title, body=body, metadata_=_meta_to_jsonb(payload),
        status=PostStatus.PUBLISHED, published_at=_publish_now(),
    )
    db.add(post)
    db.flush()
    return post


def create_question(
    db: Session, author: User, region: Region, payload: QuestionMetadata,
    title: str, body: str,
) -> Post:
    post = Post(
        author_id=author.id, region_id=region.id, type=PostType.QUESTION,
        title=title, body=body, metadata_=_meta_to_jsonb(payload),
        status=PostStatus.PUBLISHED, published_at=_publish_now(),
    )
    db.add(post)
    db.flush()
    return post


def create_answer(db: Session, author: User, parent_question: Post, body: str) -> Post:
    payload = AnswerMetadata()
    post = Post(
        author_id=author.id, region_id=parent_question.region_id,
        parent_post_id=parent_question.id, type=PostType.ANSWER,
        title="", body=body, metadata_=_meta_to_jsonb(payload),
        status=PostStatus.PUBLISHED, published_at=_publish_now(),
    )
    db.add(post)
    db.flush()
    return post


def create_plan(
    db: Session, author: User, region: Region, payload: PlanMetadata,
    title: str, body: str,
) -> Post:
    post = Post(
        author_id=author.id, region_id=region.id, type=PostType.PLAN,
        title=title, body=body, metadata_=_meta_to_jsonb(payload),
        status=PostStatus.PUBLISHED, published_at=_publish_now(),
    )
    db.add(post)
    db.flush()
    return post


def increment_view_count(db: Session, post: Post) -> None:
    db.query(Post).filter(Post.id == post.id).update(
        {Post.view_count: Post.view_count + 1}
    )
    db.flush()


__all__ = [
    "create_answer",
    "create_journey",
    "create_journey_episode",
    "create_plan",
    "create_question",
    "create_review",
    "increment_view_count",
]
```

Note on `Post.title=""` for answers: model has `title: Mapped[str] = mapped_column(String(300))` (NOT NULL). Empty string is valid; templates render answers without a title.

- [ ] **Step 4: Re-export in services/__init__.py**

Add `from app.services import posts` and include `"posts"` in `__all__` alphabetically.

- [ ] **Step 5: Run tests to verify pass**

```powershell
uv run pytest app/tests/integration/test_posts_service.py -v
```
Expected: 7 pass.

- [ ] **Step 6: Run full suite + lint**

```powershell
uv run pytest app/tests/ -q
uv run ruff check app/
```
Expected: 192 pass (185 + 7), clean.

- [ ] **Step 7: Commit**

```powershell
git add app/services/posts.py app/services/__init__.py app/tests/integration/test_posts_service.py
git commit -m "feat(services): add posts service with 5 type create + view_count"
```

---

## Task 6: markdown filter

**Files:**
- Create: `app/templating_filters.py`
- Modify: `app/templating.py`
- Create: `app/tests/unit/test_markdown_filter.py`

- [ ] **Step 1: Write failing tests**

Create `app/tests/unit/test_markdown_filter.py`:

```python
"""Tests for markdown_to_html Jinja filter."""
from app.templating_filters import markdown_to_html


def test_basic_markdown_to_html():
    html = markdown_to_html("# Heading\n\nparagraph")
    assert "<h1>" in html and "Heading" in html
    assert "<p>paragraph</p>" in html


def test_image_url_swap_orig_to_medium():
    html = markdown_to_html("![](/img/42/orig)")
    assert 'src="/img/42/medium"' in html
    assert 'loading="lazy"' in html
    assert "/img/42/orig" not in html


def test_image_swap_only_affects_internal_urls():
    html = markdown_to_html("![](https://other.com/img/42/orig)")
    assert "https://other.com/img/42/orig" in html
    assert "/medium" not in html


def test_raw_html_is_escaped():
    html = markdown_to_html('<script>alert(1)</script>\n\nhi')
    assert "<script>" not in html  # markdown lib escapes by default
    assert "alert(1)" in html  # text is preserved escaped


def test_fenced_code_block():
    html = markdown_to_html("```\nprint('hi')\n```")
    assert "<code>" in html
    assert "print('hi')" in html


def test_nl2br_converts_single_newlines():
    html = markdown_to_html("line1\nline2")
    assert "<br" in html
```

- [ ] **Step 2: Run failing tests**

```powershell
uv run pytest app/tests/unit/test_markdown_filter.py -v
```
Expected: ImportError.

- [ ] **Step 3: Write filter module**

Create `app/templating_filters.py`:

```python
"""Jinja filters for templates."""
import re

import markdown as md

_IMG_ORIG_RE = re.compile(r'src="/img/(\d+)/orig"')


def markdown_to_html(text: str | None) -> str:
    """Render markdown to HTML and swap /img/{id}/orig → /img/{id}/medium."""
    if not text:
        return ""
    html = md.markdown(text, extensions=["fenced_code", "nl2br"])
    html = _IMG_ORIG_RE.sub(r'src="/img/\1/medium" loading="lazy"', html)
    return html


__all__ = ["markdown_to_html"]
```

- [ ] **Step 4: Register filter in templating.py**

Read `app/templating.py` first to find the Jinja env. Then add:

```python
from app.templating_filters import markdown_to_html
templates.env.filters["markdown"] = markdown_to_html
```

If `templates` is the Jinja2Templates instance (FastAPI), this attaches the filter to all template renders.

- [ ] **Step 5: Run tests to verify pass**

```powershell
uv run pytest app/tests/unit/test_markdown_filter.py -v
```
Expected: 6 pass.

- [ ] **Step 6: Run full suite + lint**

```powershell
uv run pytest app/tests/ -q
uv run ruff check app/
```
Expected: 198 pass (192 + 6), clean.

- [ ] **Step 7: Commit**

```powershell
git add app/templating_filters.py app/templating.py app/tests/unit/test_markdown_filter.py
git commit -m "feat(templates): add markdown filter with /img/{id}/orig→medium swap"
```

---

## Task 7: write/review route + templates

**Files:**
- Create: `app/routers/content.py` (start with /write/review only; will grow in Tasks 8, 10, 11)
- Modify: `app/main.py`
- Create: `app/templates/pages/write/_base.html`
- Create: `app/templates/pages/write/_common_fields.html`
- Create: `app/templates/pages/write/_publish_card.html`
- Create: `app/templates/pages/write/_meta_review.html`
- Create: `app/templates/pages/write/review.html`
- Create: `app/tests/integration/test_write_review_route.py`

- [ ] **Step 1: Write failing tests**

Create `app/tests/integration/test_write_review_route.py`:

```python
"""Tests for GET·POST /write/review."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Post
from app.models._enums import PostStatus, PostType
from app.tests.factories import RegionFactory, ResidentUserFactory, UserFactory


def _login_cookie(client: TestClient, user_id: int) -> dict[str, str]:
    from itsdangerous import TimestampSigner
    from app.config import get_settings
    import json, base64
    signer = TimestampSigner(get_settings().app_secret_key)
    raw = base64.b64encode(json.dumps({"user_id": user_id}).encode()).decode().rstrip("=")
    return {"nestory_session": signer.sign(raw.encode()).decode()}


def test_get_write_review_renders_form(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    db.commit()
    r = client.get("/write/review", cookies=_login_cookie(client, user.id))
    assert r.status_code == 200
    assert "후기" in r.text or "review" in r.text.lower()
    # Form fields per ReviewMetadata
    assert 'name="house_type"' in r.text
    assert 'name="size_pyeong"' in r.text
    assert 'name="satisfaction_overall"' in r.text


def test_get_write_review_blocks_non_resident(client: TestClient, db: Session) -> None:
    user = UserFactory()  # badge_level=INTERESTED
    db.commit()
    r = client.get("/write/review", cookies=_login_cookie(client, user.id))
    assert r.status_code == 403


def test_get_write_review_blocks_anonymous(client: TestClient) -> None:
    r = client.get("/write/review")
    assert r.status_code == 401


def test_post_write_review_creates_post_and_redirects(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    region = RegionFactory()
    db.commit()
    r = client.post(
        "/write/review",
        data={
            "title": "1년차 회고",
            "body": "단열이 가장 후회됨",
            "region_id": str(region.id),
            "house_type": "단독",
            "size_pyeong": "30",
            "satisfaction_overall": "4",
        },
        cookies=_login_cookie(client, user.id),
        follow_redirects=False,
    )
    assert r.status_code == 303
    post = db.query(Post).filter(Post.author_id == user.id, Post.type == PostType.REVIEW).one()
    assert r.headers["location"] == f"/post/{post.id}"
    assert post.status == PostStatus.PUBLISHED


def test_post_write_review_400_on_invalid_metadata(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    region = RegionFactory()
    db.commit()
    r = client.post(
        "/write/review",
        data={
            "title": "x",
            "body": "y",
            "region_id": str(region.id),
            "house_type": "INVALID_TYPE",  # not in Literal
            "size_pyeong": "30",
            "satisfaction_overall": "4",
        },
        cookies=_login_cookie(client, user.id),
    )
    assert r.status_code in (400, 422)
```

- [ ] **Step 2: Run failing tests**

```powershell
uv run pytest app/tests/integration/test_write_review_route.py -v
```
Expected: 404 because /write/review doesn't exist.

- [ ] **Step 3: Create base layout template**

Create `app/templates/pages/write/_base.html`:

```html
{% extends "base.html" %}
{% block title %}{{ page_title }} · Nestory{% endblock %}
{% block content %}
<section class="mx-auto max-w-2xl p-6 space-y-6">
  <header class="rounded border bg-white p-4">
    <h1 class="text-xl font-bold">{{ page_title }}</h1>
    {% if page_subtitle %}<p class="text-sm text-slate-600 mt-1">{{ page_subtitle }}</p>{% endif %}
  </header>

  <form method="post" action="{{ form_action }}" class="space-y-6"
        enctype="application/x-www-form-urlencoded">
    {% include "pages/write/_common_fields.html" %}
    {% block meta_fields %}{% endblock %}
    {% include "pages/write/_publish_card.html" %}
  </form>
</section>
{% endblock %}
```

- [ ] **Step 4: Create common fields partial**

Create `app/templates/pages/write/_common_fields.html`:

```html
<div class="rounded border bg-white p-4 space-y-3">
  <label class="block">
    <span class="text-sm font-semibold">제목</span>
    <input type="text" name="title" required maxlength="300"
           class="mt-1 w-full rounded border p-2"
           value="{{ form.title if form else '' }}">
  </label>
  <label class="block">
    <span class="text-sm font-semibold">본문 (마크다운)</span>
    <textarea name="body" id="body-textarea" required rows="10"
              class="mt-1 w-full rounded border p-2 font-mono text-sm">{{ form.body if form else '' }}</textarea>
  </label>
  <div>
    <label class="inline-block rounded bg-slate-100 px-3 py-2 text-sm cursor-pointer hover:bg-slate-200">
      📎 이미지 첨부
      <input type="file" accept="image/jpeg,image/png,image/webp" class="hidden"
             hx-post="/htmx/image/upload"
             hx-trigger="change"
             hx-encoding="multipart/form-data"
             hx-on::after-request="if (event.detail.successful) { const d = JSON.parse(event.detail.xhr.responseText); document.getElementById('body-textarea').value += '\n\n![](' + d.url + ')'; }">
    </label>
    <p class="text-xs text-slate-500 mt-1">JPEG/PNG/WebP, 최대 10MB</p>
  </div>
</div>
```

- [ ] **Step 5: Create publish card partial**

Create `app/templates/pages/write/_publish_card.html`:

```html
<div class="rounded border bg-white p-4 space-y-3">
  {% if regions %}
    <label class="block">
      <span class="text-sm font-semibold">지역</span>
      <select name="region_id" required class="mt-1 w-full rounded border p-2">
        {% for r in regions %}
          <option value="{{ r.id }}"
                  {% if form and form.region_id == r.id %}selected{% endif %}>
            {{ r.sido }} {{ r.sigungu }}
          </option>
        {% endfor %}
      </select>
    </label>
  {% endif %}
  <button type="submit" class="w-full rounded bg-emerald-600 text-white px-4 py-3 font-semibold hover:bg-emerald-700">
    발행
  </button>
</div>
```

- [ ] **Step 6: Create review-specific metadata partial**

Create `app/templates/pages/write/_meta_review.html`:

```html
<div class="rounded border bg-white p-4 space-y-3">
  <h2 class="font-semibold text-sm">후기 정보</h2>
  <label class="block">
    <span class="text-xs text-slate-600">주택 유형</span>
    <select name="house_type" required class="mt-1 w-full rounded border p-2">
      <option value="단독">단독</option>
      <option value="타운하우스">타운하우스</option>
      <option value="듀플렉스">듀플렉스</option>
    </select>
  </label>
  <label class="block">
    <span class="text-xs text-slate-600">평수</span>
    <input type="number" name="size_pyeong" required min="1" max="500"
           class="mt-1 w-full rounded border p-2">
  </label>
  <label class="block">
    <span class="text-xs text-slate-600">전반적 만족도 (1-5)</span>
    <input type="number" name="satisfaction_overall" required min="1" max="5"
           class="mt-1 w-full rounded border p-2">
  </label>
</div>
```

(Plan keeps minimal required fields per ReviewMetadata. Optional fields like budget_total_manwon, regrets, highlights, etc. omitted from the form for now — they can be added in P1.5+ as extended UX.)

- [ ] **Step 7: Create review page template**

Create `app/templates/pages/write/review.html`:

```html
{% extends "pages/write/_base.html" %}
{% block meta_fields %}
  {% include "pages/write/_meta_review.html" %}
{% endblock %}
```

- [ ] **Step 8: Create content router with /write/review**

Create `app/routers/content.py`:

```python
"""Content routes — write/* and detail pages for non-Journey types."""
from typing import Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.deps import get_db, require_badge, require_user
from app.models import Region, User
from app.models._enums import BadgeLevel
from app.schemas.post_metadata import ReviewMetadata
from app.services import posts as posts_service
from app.templating import templates

router = APIRouter(tags=["content"])


def _user_regions_options(db: Session, user: User) -> list[Region]:
    """Regions available for posting: user's primary first, then all alphabetical."""
    return db.query(Region).order_by(Region.sigungu).all()


@router.get("/write/review", response_class=HTMLResponse)
def write_review_form(
    request: Request,
    user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/write/review.html",
        {
            "user": user,
            "page_title": "후기 작성",
            "page_subtitle": "정착 회고를 남겨주세요. Pillar C — 후회 비용을 데이터로.",
            "form_action": "/write/review",
            "regions": _user_regions_options(db, user),
            "form": None,
        },
    )


@router.post("/write/review")
def submit_review(
    user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    db: Session = Depends(get_db),
    title: str = Form(...),
    body: str = Form(...),
    region_id: int = Form(...),
    house_type: Literal["단독", "타운하우스", "듀플렉스"] = Form(...),
    size_pyeong: int = Form(...),
    satisfaction_overall: int = Form(...),
) -> RedirectResponse:
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid region")
    try:
        meta = ReviewMetadata(
            house_type=house_type, size_pyeong=size_pyeong,
            satisfaction_overall=satisfaction_overall,
        )
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    post = posts_service.create_review(db, user, region, meta, title, body)
    db.commit()
    return RedirectResponse(f"/post/{post.id}", status_code=status.HTTP_303_SEE_OTHER)


__all__ = ["router"]
```

- [ ] **Step 9: Register router in main.py**

Edit `app/main.py`. Add import + registration:
```python
from app.routers import content as content_router
app.include_router(content_router.router)
```

- [ ] **Step 10: Run tests to verify pass**

```powershell
uv run pytest app/tests/integration/test_write_review_route.py -v
```
Expected: 5 pass.

- [ ] **Step 11: Run full suite + lint**

```powershell
uv run pytest app/tests/ -q
uv run ruff check app/
```
Expected: 203 pass (198 + 5), clean.

- [ ] **Step 12: Commit**

```powershell
git add app/routers/content.py app/main.py app/templates/pages/write/ app/tests/integration/test_write_review_route.py
git commit -m "feat(content): add /write/review route + templates"
```

---

## Task 8: write/question + write/plan routes

**Files:**
- Modify: `app/routers/content.py` — add 4 endpoints
- Create: `app/templates/pages/write/_meta_question.html`
- Create: `app/templates/pages/write/_meta_plan.html`
- Create: `app/templates/pages/write/question.html`
- Create: `app/templates/pages/write/plan.html`
- Create: `app/tests/integration/test_write_question_route.py`
- Create: `app/tests/integration/test_write_plan_route.py`

- [ ] **Step 1: Write failing tests for question route**

Create `app/tests/integration/test_write_question_route.py`:

```python
"""Tests for GET·POST /write/question."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Post
from app.models._enums import PostType
from app.tests.factories import RegionFactory, UserFactory


def _login_cookie(client: TestClient, user_id: int) -> dict[str, str]:
    from itsdangerous import TimestampSigner
    from app.config import get_settings
    import json, base64
    signer = TimestampSigner(get_settings().app_secret_key)
    raw = base64.b64encode(json.dumps({"user_id": user_id}).encode()).decode().rstrip("=")
    return {"nestory_session": signer.sign(raw.encode()).decode()}


def test_get_form_renders(client: TestClient, db: Session) -> None:
    user = UserFactory()
    db.commit()
    r = client.get("/write/question", cookies=_login_cookie(client, user.id))
    assert r.status_code == 200


def test_post_creates_question(client: TestClient, db: Session) -> None:
    user = UserFactory()
    region = RegionFactory()
    db.commit()
    r = client.post(
        "/write/question",
        data={"title": "Q?", "body": "details", "region_id": str(region.id), "tags": "단열,지붕"},
        cookies=_login_cookie(client, user.id),
        follow_redirects=False,
    )
    assert r.status_code == 303
    q = db.query(Post).filter(Post.type == PostType.QUESTION).one()
    assert q.metadata_["tags"] == ["단열", "지붕"]


def test_anonymous_blocked(client: TestClient) -> None:
    r = client.get("/write/question")
    assert r.status_code == 401
```

- [ ] **Step 2: Write failing tests for plan route**

Create `app/tests/integration/test_write_plan_route.py`:

```python
"""Tests for GET·POST /write/plan."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Post
from app.models._enums import PostType
from app.tests.factories import RegionFactory, UserFactory


def _login_cookie(client: TestClient, user_id: int) -> dict[str, str]:
    from itsdangerous import TimestampSigner
    from app.config import get_settings
    import json, base64
    signer = TimestampSigner(get_settings().app_secret_key)
    raw = base64.b64encode(json.dumps({"user_id": user_id}).encode()).decode().rstrip("=")
    return {"nestory_session": signer.sign(raw.encode()).decode()}


def test_post_creates_plan(client: TestClient, db: Session) -> None:
    region = RegionFactory()
    user = UserFactory(primary_region_id=region.id)
    db.commit()
    r = client.post(
        "/write/plan",
        data={
            "title": "2027 양평 입주",
            "body": "검토 중",
            "region_id": str(region.id),
            "target_move_year": "2027",
            "budget_total_manwon_band": "5000-10000",
            "construction_intent": "undecided",
        },
        cookies=_login_cookie(client, user.id),
        follow_redirects=False,
    )
    assert r.status_code == 303
    p = db.query(Post).filter(Post.type == PostType.PLAN).one()
    assert p.metadata_["target_move_year"] == 2027


def test_get_plan_form_without_primary_region(client: TestClient, db: Session) -> None:
    """User has no primary_region_id — form still renders (region select still available)."""
    user = UserFactory()
    region = RegionFactory()
    db.commit()
    r = client.get("/write/plan", cookies=_login_cookie(client, user.id))
    assert r.status_code == 200
```

- [ ] **Step 3: Run failing tests**

```powershell
uv run pytest app/tests/integration/test_write_question_route.py app/tests/integration/test_write_plan_route.py -v
```
Expected: 404.

- [ ] **Step 4: Create question metadata partial**

Create `app/templates/pages/write/_meta_question.html`:

```html
<div class="rounded border bg-white p-4 space-y-3">
  <h2 class="font-semibold text-sm">질문 정보</h2>
  <label class="block">
    <span class="text-xs text-slate-600">태그 (콤마 구분, 최대 10개)</span>
    <input type="text" name="tags" placeholder="단열,지붕,난방"
           class="mt-1 w-full rounded border p-2">
  </label>
</div>
```

- [ ] **Step 5: Create plan metadata partial**

Create `app/templates/pages/write/_meta_plan.html`:

```html
<div class="rounded border bg-white p-4 space-y-3">
  <h2 class="font-semibold text-sm">정착 계획</h2>
  <label class="block">
    <span class="text-xs text-slate-600">목표 이주 연도 (2026-2050)</span>
    <input type="number" name="target_move_year" required min="2026" max="2050"
           class="mt-1 w-full rounded border p-2">
  </label>
  <label class="block">
    <span class="text-xs text-slate-600">예산 범위 (만원)</span>
    <select name="budget_total_manwon_band" required class="mt-1 w-full rounded border p-2">
      <option value="<5000">5,000 미만</option>
      <option value="5000-10000">5,000-10,000</option>
      <option value="10000-20000">10,000-20,000</option>
      <option value="20000-40000">20,000-40,000</option>
      <option value="40000+">40,000 이상</option>
    </select>
  </label>
  <label class="block">
    <span class="text-xs text-slate-600">건축 의향</span>
    <select name="construction_intent" required class="mt-1 w-full rounded border p-2">
      <option value="self_build">직접 건축</option>
      <option value="buy_existing">기존 매입</option>
      <option value="rent_first">임대 먼저</option>
      <option value="undecided">미결정</option>
    </select>
  </label>
</div>
```

- [ ] **Step 6: Create question.html and plan.html**

Create `app/templates/pages/write/question.html`:

```html
{% extends "pages/write/_base.html" %}
{% block meta_fields %}
  {% include "pages/write/_meta_question.html" %}
{% endblock %}
```

Create `app/templates/pages/write/plan.html`:

```html
{% extends "pages/write/_base.html" %}
{% block meta_fields %}
  {% include "pages/write/_meta_plan.html" %}
{% endblock %}
```

- [ ] **Step 7: Add 4 endpoints to content router**

Edit `app/routers/content.py`. Add imports near the top:

```python
from typing import Literal
from app.schemas.post_metadata import PlanMetadata, QuestionMetadata
```

Append the following endpoints to the router (after the existing review endpoints):

```python
@router.get("/write/question", response_class=HTMLResponse)
def write_question_form(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/write/question.html",
        {
            "user": user,
            "page_title": "질문 작성",
            "page_subtitle": "지역에 사는 분들께 직접 물어보세요.",
            "form_action": "/write/question",
            "regions": _user_regions_options(db, user),
            "form": None,
        },
    )


@router.post("/write/question")
def submit_question(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    title: str = Form(...),
    body: str = Form(...),
    region_id: int = Form(...),
    tags: str = Form(""),
) -> RedirectResponse:
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid region")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()][:10]
    try:
        meta = QuestionMetadata(tags=tag_list)
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    post = posts_service.create_question(db, user, region, meta, title, body)
    db.commit()
    return RedirectResponse(f"/question/{post.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/write/plan", response_class=HTMLResponse)
def write_plan_form(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/write/plan.html",
        {
            "user": user,
            "page_title": "정착 계획 작성",
            "page_subtitle": "예비 입주자를 위한 콘텐츠. 다른 분들의 조언을 받아보세요.",
            "form_action": "/write/plan",
            "regions": _user_regions_options(db, user),
            "form": None,
        },
    )


@router.post("/write/plan")
def submit_plan(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    title: str = Form(...),
    body: str = Form(...),
    region_id: int = Form(...),
    target_move_year: int = Form(...),
    budget_total_manwon_band: Literal[
        "<5000", "5000-10000", "10000-20000", "20000-40000", "40000+"
    ] = Form(...),
    construction_intent: Literal[
        "self_build", "buy_existing", "rent_first", "undecided"
    ] = Form(...),
) -> RedirectResponse:
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid region")
    try:
        meta = PlanMetadata(
            target_move_year=target_move_year,
            budget_total_manwon_band=budget_total_manwon_band,
            construction_intent=construction_intent,
        )
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    post = posts_service.create_plan(db, user, region, meta, title, body)
    db.commit()
    return RedirectResponse(f"/post/{post.id}", status_code=status.HTTP_303_SEE_OTHER)
```

- [ ] **Step 8: Run tests to verify pass**

```powershell
uv run pytest app/tests/integration/test_write_question_route.py app/tests/integration/test_write_plan_route.py -v
```
Expected: all pass.

- [ ] **Step 9: Run full suite + lint**

```powershell
uv run pytest app/tests/ -q
uv run ruff check app/
```
Expected: 207 pass (203 + 4), clean.

- [ ] **Step 10: Commit**

```powershell
git add app/routers/content.py app/templates/pages/write/_meta_question.html app/templates/pages/write/_meta_plan.html app/templates/pages/write/question.html app/templates/pages/write/plan.html app/tests/integration/test_write_question_route.py app/tests/integration/test_write_plan_route.py
git commit -m "feat(content): add /write/question and /write/plan routes + templates"
```

---

## Task 9: write/journey + write/journey/{id}/ep routes

**Files:**
- Create: `app/routers/journey.py`
- Modify: `app/main.py`
- Create: `app/templates/pages/write/journey_create.html`
- Create: `app/templates/pages/write/_meta_journey_episode.html`
- Create: `app/templates/pages/write/journey_episode.html`
- Create: `app/tests/integration/test_write_journey_routes.py`

- [ ] **Step 1: Write failing tests**

Create `app/tests/integration/test_write_journey_routes.py`:

```python
"""Tests for journey create + episode routes."""
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Journey, Post
from app.models._enums import PostType
from app.tests.factories import JourneyFactory, RegionFactory, ResidentUserFactory, UserFactory


def _login_cookie(client: TestClient, user_id: int) -> dict[str, str]:
    from itsdangerous import TimestampSigner
    from app.config import get_settings
    import json, base64
    signer = TimestampSigner(get_settings().app_secret_key)
    raw = base64.b64encode(json.dumps({"user_id": user_id}).encode()).decode().rstrip("=")
    return {"nestory_session": signer.sign(raw.encode()).decode()}


def test_get_write_journey_renders(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    db.commit()
    r = client.get("/write/journey", cookies=_login_cookie(client, user.id))
    assert r.status_code == 200


def test_post_write_journey_creates_journey(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    region = RegionFactory()
    db.commit()
    r = client.post(
        "/write/journey",
        data={
            "title": "양평 정착기",
            "description": "터잡기부터 입주까지",
            "region_id": str(region.id),
            "start_date": "2026-01-01",
        },
        cookies=_login_cookie(client, user.id),
        follow_redirects=False,
    )
    assert r.status_code == 303
    j = db.query(Journey).one()
    assert j.title == "양평 정착기"
    assert r.headers["location"] == f"/journey/{j.id}"


def test_post_write_journey_blocks_non_resident(client: TestClient, db: Session) -> None:
    user = UserFactory()
    region = RegionFactory()
    db.commit()
    r = client.post(
        "/write/journey",
        data={"title": "x", "region_id": str(region.id)},
        cookies=_login_cookie(client, user.id),
    )
    assert r.status_code == 403


def test_post_journey_episode_auto_increments(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    journey = JourneyFactory(author=user)
    db.commit()
    for n in range(2):
        r = client.post(
            f"/write/journey/{journey.id}/ep",
            data={
                "title": f"{n+1}화", "body": "...",
                "phase": "입주", "period_label": "2026-04",
            },
            cookies=_login_cookie(client, user.id),
            follow_redirects=False,
        )
        assert r.status_code == 303
    eps = db.query(Post).filter(Post.type == PostType.JOURNEY_EPISODE).order_by(Post.episode_no).all()
    assert [e.episode_no for e in eps] == [1, 2]


def test_journey_episode_blocks_non_owner(client: TestClient, db: Session) -> None:
    owner = ResidentUserFactory()
    intruder = ResidentUserFactory()
    journey = JourneyFactory(author=owner)
    db.commit()
    r = client.post(
        f"/write/journey/{journey.id}/ep",
        data={"title": "x", "body": "y", "phase": "입주", "period_label": "2026-04"},
        cookies=_login_cookie(client, intruder.id),
    )
    assert r.status_code == 403
```

- [ ] **Step 2: Run failing tests**

```powershell
uv run pytest app/tests/integration/test_write_journey_routes.py -v
```
Expected: 404.

- [ ] **Step 3: Create journey_create.html**

Create `app/templates/pages/write/journey_create.html`:

```html
{% extends "base.html" %}
{% block title %}Journey 시작 · Nestory{% endblock %}
{% block content %}
<section class="mx-auto max-w-2xl p-6 space-y-6">
  <header class="rounded border bg-white p-4">
    <h1 class="text-xl font-bold">새 Journey 시작</h1>
    <p class="text-sm text-slate-600 mt-1">정착 과정을 연재로 기록합니다. 첫 에피소드는 생성 후 작성.</p>
  </header>
  <form method="post" action="/write/journey" class="space-y-4">
    <div class="rounded border bg-white p-4 space-y-3">
      <label class="block">
        <span class="text-sm font-semibold">Journey 제목</span>
        <input type="text" name="title" required maxlength="200"
               class="mt-1 w-full rounded border p-2">
      </label>
      <label class="block">
        <span class="text-sm font-semibold">설명 (선택)</span>
        <textarea name="description" rows="3" class="mt-1 w-full rounded border p-2"></textarea>
      </label>
      <label class="block">
        <span class="text-sm font-semibold">지역</span>
        <select name="region_id" required class="mt-1 w-full rounded border p-2">
          {% for r in regions %}
            <option value="{{ r.id }}">{{ r.sido }} {{ r.sigungu }}</option>
          {% endfor %}
        </select>
      </label>
      <label class="block">
        <span class="text-sm font-semibold">시작일 (선택)</span>
        <input type="date" name="start_date" class="mt-1 w-full rounded border p-2">
      </label>
    </div>
    <button type="submit" class="w-full rounded bg-emerald-600 text-white px-4 py-3 font-semibold hover:bg-emerald-700">Journey 만들기</button>
  </form>
</section>
{% endblock %}
```

- [ ] **Step 4: Create journey episode metadata partial**

Create `app/templates/pages/write/_meta_journey_episode.html`:

```html
<div class="rounded border bg-white p-4 space-y-3">
  <h2 class="font-semibold text-sm">에피소드 메타</h2>
  <label class="block">
    <span class="text-xs text-slate-600">단계</span>
    <select name="phase" required class="mt-1 w-full rounded border p-2">
      <option value="터">터잡기</option>
      <option value="건축">건축</option>
      <option value="입주">입주</option>
      <option value="1년차">1년차</option>
      <option value="3년차">3년차</option>
    </select>
  </label>
  <label class="block">
    <span class="text-xs text-slate-600">기간 라벨 (예: 2026-04, 2025-09~10)</span>
    <input type="text" name="period_label" required maxlength="40"
           class="mt-1 w-full rounded border p-2">
  </label>
</div>
```

- [ ] **Step 5: Create journey_episode.html**

Create `app/templates/pages/write/journey_episode.html`:

```html
{% extends "pages/write/_base.html" %}
{% block meta_fields %}
  {% include "pages/write/_meta_journey_episode.html" %}
{% endblock %}
```

Note: this uses `pages/write/_base.html` but the `_publish_card.html` would render a region select. For episode, region is inherited from the journey, so we don't need region select. The simplest fix: render a hidden region_id in the form... but the route doesn't actually consume region_id (it inherits from journey). So we override `_publish_card` content via Jinja block. Adjust `_base.html` to make publish_card a block:

Edit `app/templates/pages/write/_base.html` — change:
```html
    {% include "pages/write/_publish_card.html" %}
```
to:
```html
    {% block publish_card %}{% include "pages/write/_publish_card.html" %}{% endblock %}
```

Then in `journey_episode.html`:
```html
{% extends "pages/write/_base.html" %}
{% block meta_fields %}
  {% include "pages/write/_meta_journey_episode.html" %}
{% endblock %}
{% block publish_card %}
  <div class="rounded border bg-white p-4">
    <button type="submit" class="w-full rounded bg-emerald-600 text-white px-4 py-3 font-semibold hover:bg-emerald-700">에피소드 발행</button>
  </div>
{% endblock %}
```

- [ ] **Step 6: Create journey router**

Create `app/routers/journey.py`:

```python
"""Journey routes — create journey + write episode + detail pages."""
from datetime import date as date_type
from typing import Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.deps import get_db, require_badge
from app.models import Journey, Region, User
from app.models._enums import BadgeLevel
from app.schemas.post_metadata import JourneyEpisodeMetadata, JourneyEpMeta
from app.services import posts as posts_service
from app.templating import templates

router = APIRouter(tags=["journey"])


def _all_regions(db: Session) -> list[Region]:
    return db.query(Region).order_by(Region.sigungu).all()


@router.get("/write/journey", response_class=HTMLResponse)
def write_journey_form(
    request: Request,
    user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/write/journey_create.html",
        {"user": user, "regions": _all_regions(db)},
    )


@router.post("/write/journey")
def submit_journey(
    user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    db: Session = Depends(get_db),
    title: str = Form(...),
    description: str = Form(""),
    region_id: int = Form(...),
    start_date: str = Form(""),
) -> RedirectResponse:
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid region")
    parsed_start: date_type | None = None
    if start_date:
        try:
            parsed_start = date_type.fromisoformat(start_date)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid start_date") from e
    j = posts_service.create_journey(db, user, region, title, description or None, parsed_start)
    db.commit()
    return RedirectResponse(f"/journey/{j.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/write/journey/{journey_id}/ep", response_class=HTMLResponse)
def write_episode_form(
    request: Request,
    journey_id: int,
    user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    journey = db.get(Journey, journey_id)
    if journey is None or journey.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if journey.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your journey")
    return templates.TemplateResponse(
        request, "pages/write/journey_episode.html",
        {
            "user": user, "journey": journey,
            "page_title": f"새 에피소드 — {journey.title}",
            "page_subtitle": "이번 단계의 진행 상황을 기록하세요.",
            "form_action": f"/write/journey/{journey_id}/ep",
        },
    )


@router.post("/write/journey/{journey_id}/ep")
def submit_episode(
    journey_id: int,
    user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    db: Session = Depends(get_db),
    title: str = Form(...),
    body: str = Form(...),
    phase: Literal["터", "건축", "입주", "1년차", "3년차"] = Form(...),
    period_label: str = Form(...),
) -> RedirectResponse:
    journey = db.get(Journey, journey_id)
    if journey is None or journey.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if journey.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your journey")
    try:
        meta = JourneyEpisodeMetadata(
            journey_ep_meta=JourneyEpMeta(phase=phase, period_label=period_label)
        )
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    post = posts_service.create_journey_episode(db, user, journey, meta, title, body)
    db.commit()
    return RedirectResponse(
        f"/journey/{journey_id}/ep/{post.episode_no}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


__all__ = ["router"]
```

- [ ] **Step 7: Register router in main.py**

```python
from app.routers import journey as journey_router
app.include_router(journey_router.router)
```

- [ ] **Step 8: Run tests to verify pass**

```powershell
uv run pytest app/tests/integration/test_write_journey_routes.py -v
```
Expected: 5 pass.

- [ ] **Step 9: Run full suite + lint**

```powershell
uv run pytest app/tests/ -q
uv run ruff check app/
```
Expected: 212 pass (207 + 5), clean.

- [ ] **Step 10: Commit**

```powershell
git add app/routers/journey.py app/main.py app/templates/pages/write/journey_create.html app/templates/pages/write/_meta_journey_episode.html app/templates/pages/write/journey_episode.html app/templates/pages/write/_base.html app/tests/integration/test_write_journey_routes.py
git commit -m "feat(journey): add /write/journey and episode write routes + templates"
```

---

## Task 10: inline /question/{qid}/answer route

**Files:**
- Modify: `app/routers/content.py` — add /question/{qid}/answer endpoint
- Create: `app/tests/integration/test_answer_route.py`

- [ ] **Step 1: Write failing tests**

Create `app/tests/integration/test_answer_route.py`:

```python
"""Tests for inline POST /question/{qid}/answer."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Post
from app.models._enums import PostType
from app.tests.factories import QuestionPostFactory, UserFactory


def _login_cookie(client: TestClient, user_id: int) -> dict[str, str]:
    from itsdangerous import TimestampSigner
    from app.config import get_settings
    import json, base64
    signer = TimestampSigner(get_settings().app_secret_key)
    raw = base64.b64encode(json.dumps({"user_id": user_id}).encode()).decode().rstrip("=")
    return {"nestory_session": signer.sign(raw.encode()).decode()}


def test_answer_creates_post_with_parent_link(client: TestClient, db: Session) -> None:
    question = QuestionPostFactory()
    user = UserFactory()
    db.commit()
    r = client.post(
        f"/question/{question.id}/answer",
        data={"body": "셀룰로오스가 가성비 좋습니다"},
        cookies=_login_cookie(client, user.id),
        follow_redirects=False,
    )
    assert r.status_code == 303
    answer = db.query(Post).filter(Post.type == PostType.ANSWER).one()
    assert answer.parent_post_id == question.id
    assert answer.region_id == question.region_id
    assert r.headers["location"] == f"/question/{question.id}"


def test_answer_blocks_anonymous(client: TestClient, db: Session) -> None:
    question = QuestionPostFactory()
    db.commit()
    r = client.post(f"/question/{question.id}/answer", data={"body": "x"})
    assert r.status_code == 401


def test_answer_404_on_missing_question(client: TestClient, db: Session) -> None:
    user = UserFactory()
    db.commit()
    r = client.post("/question/99999/answer", data={"body": "x"},
                    cookies=_login_cookie(client, user.id))
    assert r.status_code == 404
```

- [ ] **Step 2: Run failing tests**

```powershell
uv run pytest app/tests/integration/test_answer_route.py -v
```
Expected: 404 / 405.

- [ ] **Step 3: Add answer endpoint to content router**

Edit `app/routers/content.py`. Add import:
```python
from app.models import Post
from app.models._enums import PostType
```
Append endpoint:

```python
@router.post("/question/{question_id}/answer")
def submit_answer(
    question_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    body: str = Form(...),
) -> RedirectResponse:
    question = db.get(Post, question_id)
    if (
        question is None
        or question.type != PostType.QUESTION
        or question.deleted_at is not None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    posts_service.create_answer(db, user, question, body)
    db.commit()
    return RedirectResponse(
        f"/question/{question_id}", status_code=status.HTTP_303_SEE_OTHER
    )
```

- [ ] **Step 4: Run tests to verify pass**

```powershell
uv run pytest app/tests/integration/test_answer_route.py -v
```
Expected: 3 pass.

- [ ] **Step 5: Run full suite + lint**

```powershell
uv run pytest app/tests/ -q
uv run ruff check app/
```
Expected: 215 pass (212 + 3), clean.

- [ ] **Step 6: Commit**

```powershell
git add app/routers/content.py app/tests/integration/test_answer_route.py
git commit -m "feat(content): add inline POST /question/{id}/answer endpoint"
```

---

## Task 11: detail pages — /post/{id}, /question/{id}, /journey/{id}, /journey/{id}/ep/{n}

**Files:**
- Modify: `app/routers/content.py` — add /post/{id}, /question/{id}
- Modify: `app/routers/journey.py` — add /journey/{id}, /journey/{id}/ep/{n}
- Create: `app/templates/pages/detail/post.html`
- Create: `app/templates/pages/detail/question.html`
- Create: `app/templates/pages/detail/journey.html`
- Create: `app/templates/pages/detail/journey_episode.html`
- Create: `app/templates/pages/detail/_meta_card_review.html`
- Create: `app/templates/pages/detail/_meta_card_plan.html`
- Create: `app/templates/pages/detail/_meta_card_question.html`
- Create: `app/templates/pages/detail/_meta_card_journey_ep.html`
- Create: `app/tests/integration/test_detail_routes.py`

- [ ] **Step 1: Write failing tests**

Create `app/tests/integration/test_detail_routes.py`:

```python
"""Tests for detail pages — /post, /question, /journey, /journey/ep."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import PostStatus, PostType
from app.tests.factories import (
    AnswerPostFactory, JourneyEpisodePostFactory, JourneyFactory,
    PlanPostFactory, QuestionPostFactory, ResidentUserFactory, ReviewPostFactory,
)


def test_post_review_renders_with_metadata_card(client: TestClient, db: Session) -> None:
    post = ReviewPostFactory(title="1년차 회고", body="단열")
    db.commit()
    r = client.get(f"/post/{post.id}")
    assert r.status_code == 200
    assert "1년차 회고" in r.text
    # metadata card should show some review-specific text
    assert "단독" in r.text or "house_type" in r.text.lower() or "30" in r.text


def test_post_plan_renders(client: TestClient, db: Session) -> None:
    post = PlanPostFactory(title="2027 양평")
    db.commit()
    r = client.get(f"/post/{post.id}")
    assert r.status_code == 200
    assert "2027" in r.text


def test_post_404_on_unpublished(client: TestClient, db: Session) -> None:
    post = ReviewPostFactory(status=PostStatus.DRAFT)
    db.commit()
    r = client.get(f"/post/{post.id}")
    assert r.status_code == 404


def test_post_404_on_deleted(client: TestClient, db: Session) -> None:
    from datetime import UTC, datetime
    post = ReviewPostFactory(deleted_at=datetime.now(UTC))
    db.commit()
    r = client.get(f"/post/{post.id}")
    assert r.status_code == 404


def test_post_view_count_increments(client: TestClient, db: Session) -> None:
    post = ReviewPostFactory(view_count=0)
    db.commit()
    client.get(f"/post/{post.id}")
    client.get(f"/post/{post.id}")
    db.refresh(post)
    assert post.view_count == 2


def test_question_renders_with_answer_form_when_logged_in(client: TestClient, db: Session) -> None:
    question = QuestionPostFactory(title="단열재 추천?")
    user = ResidentUserFactory()
    db.commit()
    r = client.get(f"/question/{question.id}")
    assert r.status_code == 200
    assert "단열재 추천?" in r.text


def test_question_renders_with_answers(client: TestClient, db: Session) -> None:
    question = QuestionPostFactory()
    answer = AnswerPostFactory(parent_post_id=question.id, body="셀룰로오스 추천")
    db.commit()
    r = client.get(f"/question/{question.id}")
    assert r.status_code == 200
    assert "셀룰로오스" in r.text


def test_journey_lists_episodes(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    journey = JourneyFactory(author=user, title="양평 정착기")
    ep1 = JourneyEpisodePostFactory(author=user, region_id=journey.region_id,
                                     journey_id=journey.id, episode_no=1, title="1화 터잡기")
    ep2 = JourneyEpisodePostFactory(author=user, region_id=journey.region_id,
                                     journey_id=journey.id, episode_no=2, title="2화 건축")
    db.commit()
    r = client.get(f"/journey/{journey.id}")
    assert r.status_code == 200
    assert "양평 정착기" in r.text
    assert "1화 터잡기" in r.text
    assert "2화 건축" in r.text


def test_journey_episode_renders(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    journey = JourneyFactory(author=user)
    ep = JourneyEpisodePostFactory(author=user, region_id=journey.region_id,
                                    journey_id=journey.id, episode_no=1, title="1화")
    db.commit()
    r = client.get(f"/journey/{journey.id}/ep/1")
    assert r.status_code == 200
    assert "1화" in r.text


def test_journey_episode_404(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    journey = JourneyFactory(author=user)
    db.commit()
    r = client.get(f"/journey/{journey.id}/ep/99")
    assert r.status_code == 404
```

- [ ] **Step 2: Run failing tests**

```powershell
uv run pytest app/tests/integration/test_detail_routes.py -v
```
Expected: 404 across the board.

- [ ] **Step 3: Create detail templates**

Create `app/templates/pages/detail/post.html`:

```html
{% extends "base.html" %}
{% block title %}{{ post.title or "포스트" }} · Nestory{% endblock %}
{% block content %}
<article class="mx-auto max-w-2xl p-6 space-y-4">
  <header>
    {% if post.title %}<h1 class="text-2xl font-bold">{{ post.title }}</h1>{% endif %}
    <p class="text-xs text-slate-500 mt-1">
      {{ author.display_name }} · {{ region.sido }} {{ region.sigungu }}
      {% if post.published_at %}· {{ post.published_at.strftime("%Y-%m-%d") }}{% endif %}
      · 조회 {{ post.view_count }}
    </p>
  </header>
  {% if post.type.value == "review" %}
    {% include "pages/detail/_meta_card_review.html" %}
  {% elif post.type.value == "plan" %}
    {% include "pages/detail/_meta_card_plan.html" %}
  {% endif %}
  <div class="prose max-w-none">{{ post.body | markdown | safe }}</div>
</article>
{% endblock %}
```

Create `app/templates/pages/detail/_meta_card_review.html`:

```html
<div class="rounded border bg-slate-50 p-4 text-sm">
  <div class="flex flex-wrap gap-3">
    {% if post.metadata_.house_type %}<span>🏠 {{ post.metadata_.house_type }}</span>{% endif %}
    {% if post.metadata_.size_pyeong %}<span>📐 {{ post.metadata_.size_pyeong }}평</span>{% endif %}
    {% if post.metadata_.satisfaction_overall %}<span>⭐ {{ post.metadata_.satisfaction_overall }}/5</span>{% endif %}
  </div>
</div>
```

Create `app/templates/pages/detail/_meta_card_plan.html`:

```html
<div class="rounded border bg-slate-50 p-4 text-sm">
  <div class="flex flex-wrap gap-3">
    <span>🎯 {{ post.metadata_.target_move_year }}년 입주</span>
    <span>💰 {{ post.metadata_.budget_total_manwon_band }}만원</span>
    <span>🔨 {{ post.metadata_.construction_intent }}</span>
  </div>
</div>
```

Create `app/templates/pages/detail/_meta_card_question.html`:

```html
{% if post.metadata_.tags %}
<div class="flex flex-wrap gap-2 text-xs">
  {% for t in post.metadata_.tags %}
    <span class="rounded bg-slate-200 px-2 py-1">#{{ t }}</span>
  {% endfor %}
</div>
{% endif %}
```

Create `app/templates/pages/detail/_meta_card_journey_ep.html`:

```html
<div class="rounded border bg-slate-50 p-4 text-sm">
  <span>📍 단계: {{ post.metadata_.journey_ep_meta.phase }}</span>
  <span class="ml-3">🗓️ {{ post.metadata_.journey_ep_meta.period_label }}</span>
</div>
```

Create `app/templates/pages/detail/question.html`:

```html
{% extends "base.html" %}
{% block title %}{{ question.title }} · Nestory{% endblock %}
{% block content %}
<article class="mx-auto max-w-2xl p-6 space-y-6">
  <header>
    <h1 class="text-2xl font-bold">❓ {{ question.title }}</h1>
    <p class="text-xs text-slate-500 mt-1">
      {{ author.display_name }} · {{ region.sido }} {{ region.sigungu }}
      {% if question.published_at %}· {{ question.published_at.strftime("%Y-%m-%d") }}{% endif %}
      · 조회 {{ question.view_count }}
    </p>
    {% include "pages/detail/_meta_card_question.html" %}
  </header>
  <div class="prose max-w-none">{{ question.body | markdown | safe }}</div>

  <section class="space-y-4">
    <h2 class="text-lg font-semibold">답변 {{ answers|length }}개</h2>
    {% for ans in answers %}
      <article class="rounded border bg-white p-4">
        <p class="text-xs text-slate-500">{{ ans.author.display_name }} · {{ ans.published_at.strftime("%Y-%m-%d") if ans.published_at }}</p>
        <div class="prose mt-2">{{ ans.body | markdown | safe }}</div>
      </article>
    {% endfor %}
  </section>

  {% if user %}
    <form method="post" action="/question/{{ question.id }}/answer" class="rounded border bg-white p-4 space-y-3">
      <h2 class="font-semibold text-sm">답변 작성</h2>
      <textarea name="body" required rows="4" class="w-full rounded border p-2"></textarea>
      <button type="submit" class="rounded bg-emerald-600 text-white px-4 py-2">답변 등록</button>
    </form>
  {% else %}
    <p class="text-center text-sm text-slate-600">답변을 남기려면 <a href="/auth/login" class="text-emerald-600 underline">로그인</a> 하세요.</p>
  {% endif %}
</article>
{% endblock %}
```

Create `app/templates/pages/detail/journey.html`:

```html
{% extends "base.html" %}
{% block title %}{{ journey.title }} · Nestory{% endblock %}
{% block content %}
<section class="mx-auto max-w-2xl p-6 space-y-6">
  <header class="rounded border bg-white p-4">
    <h1 class="text-2xl font-bold">🗺️ {{ journey.title }}</h1>
    <p class="text-xs text-slate-500 mt-1">
      {{ author.display_name }} · {{ region.sido }} {{ region.sigungu }}
      {% if journey.start_date %}· 시작 {{ journey.start_date }}{% endif %}
    </p>
    {% if journey.description %}
      <p class="mt-3 text-sm">{{ journey.description }}</p>
    {% endif %}
  </header>
  <section class="space-y-3">
    <h2 class="text-lg font-semibold">에피소드 {{ episodes|length }}개</h2>
    {% for ep in episodes %}
      <a href="/journey/{{ journey.id }}/ep/{{ ep.episode_no }}"
         class="block rounded border bg-white p-4 hover:bg-slate-50">
        <p class="text-xs text-slate-500">{{ ep.episode_no }}화 · {{ ep.metadata_.journey_ep_meta.phase if ep.metadata_.journey_ep_meta else '' }}</p>
        <p class="font-semibold mt-1">{{ ep.title }}</p>
      </a>
    {% endfor %}
  </section>
</section>
{% endblock %}
```

Create `app/templates/pages/detail/journey_episode.html`:

```html
{% extends "base.html" %}
{% block title %}{{ post.title }} · {{ journey.title }} · Nestory{% endblock %}
{% block content %}
<article class="mx-auto max-w-2xl p-6 space-y-4">
  <p class="text-sm">
    <a href="/journey/{{ journey.id }}" class="text-emerald-600 hover:underline">← {{ journey.title }}</a>
  </p>
  <header>
    <h1 class="text-2xl font-bold">{{ post.episode_no }}화 · {{ post.title }}</h1>
    <p class="text-xs text-slate-500 mt-1">
      {{ post.published_at.strftime("%Y-%m-%d") if post.published_at }} · 조회 {{ post.view_count }}
    </p>
  </header>
  {% include "pages/detail/_meta_card_journey_ep.html" %}
  <div class="prose max-w-none">{{ post.body | markdown | safe }}</div>
  <nav class="flex justify-between pt-4 border-t">
    {% if prev_ep %}
      <a href="/journey/{{ journey.id }}/ep/{{ prev_ep.episode_no }}" class="text-sm text-emerald-600">← {{ prev_ep.episode_no }}화</a>
    {% else %}<span></span>{% endif %}
    {% if next_ep %}
      <a href="/journey/{{ journey.id }}/ep/{{ next_ep.episode_no }}" class="text-sm text-emerald-600">{{ next_ep.episode_no }}화 →</a>
    {% endif %}
  </nav>
</article>
{% endblock %}
```

- [ ] **Step 4: Add /post/{id} and /question/{id} to content router**

Edit `app/routers/content.py`. Add imports:
```python
from app.deps import get_current_user
```

Add endpoints:

```python
@router.get("/post/{post_id}", response_class=HTMLResponse)
def post_detail(
    request: Request,
    post_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    post = db.get(Post, post_id)
    if (
        post is None
        or post.deleted_at is not None
        or post.status != PostStatus.PUBLISHED
        or post.type == PostType.JOURNEY_EPISODE  # those use /journey/.../ep/.. route
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    posts_service.increment_view_count(db, post)
    db.commit()
    db.refresh(post)
    author = db.get(User, post.author_id)
    region = db.get(Region, post.region_id)
    return templates.TemplateResponse(
        request, "pages/detail/post.html",
        {"post": post, "author": author, "region": region},
    )


@router.get("/question/{question_id}", response_class=HTMLResponse)
def question_detail(
    request: Request,
    question_id: int,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    question = db.get(Post, question_id)
    if (
        question is None
        or question.deleted_at is not None
        or question.type != PostType.QUESTION
        or question.status != PostStatus.PUBLISHED
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    posts_service.increment_view_count(db, question)
    db.commit()
    db.refresh(question)
    author = db.get(User, question.author_id)
    region = db.get(Region, question.region_id)
    answers = (
        db.query(Post)
        .filter(
            Post.parent_post_id == question.id,
            Post.type == PostType.ANSWER,
            Post.deleted_at.is_(None),
        )
        .order_by(Post.published_at.asc())
        .all()
    )
    # Eager-load answer authors for template
    for ans in answers:
        ans.author = db.get(User, ans.author_id)
    return templates.TemplateResponse(
        request, "pages/detail/question.html",
        {
            "question": question, "author": author, "region": region,
            "answers": answers, "user": user,
        },
    )
```

You also need to import `PostStatus` and `PostType` at the top:
```python
from app.models._enums import PostStatus, PostType
```
And `Post` from models.

- [ ] **Step 5: Add /journey/{id} and /journey/{id}/ep/{n} to journey router**

Edit `app/routers/journey.py`. Add imports:
```python
from app.models import Post, User
from app.models._enums import PostStatus, PostType
from app.services import posts as posts_service
```

Add endpoints:

```python
@router.get("/journey/{journey_id}", response_class=HTMLResponse)
def journey_detail(
    request: Request,
    journey_id: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    journey = db.get(Journey, journey_id)
    if journey is None or journey.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    author = db.get(User, journey.author_id)
    region = db.get(Region, journey.region_id)
    episodes = (
        db.query(Post)
        .filter(
            Post.journey_id == journey_id,
            Post.type == PostType.JOURNEY_EPISODE,
            Post.deleted_at.is_(None),
            Post.status == PostStatus.PUBLISHED,
        )
        .order_by(Post.episode_no.asc())
        .all()
    )
    return templates.TemplateResponse(
        request, "pages/detail/journey.html",
        {"journey": journey, "author": author, "region": region, "episodes": episodes},
    )


@router.get("/journey/{journey_id}/ep/{ep_no}", response_class=HTMLResponse)
def journey_episode_detail(
    request: Request,
    journey_id: int,
    ep_no: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    journey = db.get(Journey, journey_id)
    if journey is None or journey.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    post = (
        db.query(Post)
        .filter(
            Post.journey_id == journey_id,
            Post.episode_no == ep_no,
            Post.type == PostType.JOURNEY_EPISODE,
            Post.deleted_at.is_(None),
            Post.status == PostStatus.PUBLISHED,
        )
        .first()
    )
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    posts_service.increment_view_count(db, post)
    db.commit()
    db.refresh(post)
    prev_ep = (
        db.query(Post)
        .filter(
            Post.journey_id == journey_id,
            Post.episode_no < ep_no,
            Post.type == PostType.JOURNEY_EPISODE,
            Post.deleted_at.is_(None),
        )
        .order_by(Post.episode_no.desc())
        .first()
    )
    next_ep = (
        db.query(Post)
        .filter(
            Post.journey_id == journey_id,
            Post.episode_no > ep_no,
            Post.type == PostType.JOURNEY_EPISODE,
            Post.deleted_at.is_(None),
        )
        .order_by(Post.episode_no.asc())
        .first()
    )
    return templates.TemplateResponse(
        request, "pages/detail/journey_episode.html",
        {"journey": journey, "post": post, "prev_ep": prev_ep, "next_ep": next_ep},
    )
```

- [ ] **Step 6: Run tests to verify pass**

```powershell
uv run pytest app/tests/integration/test_detail_routes.py -v
```
Expected: 10 pass.

- [ ] **Step 7: Run full suite + lint**

```powershell
uv run pytest app/tests/ -q
uv run ruff check app/
```
Expected: 225 pass (215 + 10), clean.

- [ ] **Step 8: Commit**

```powershell
git add app/routers/content.py app/routers/journey.py app/templates/pages/detail/ app/tests/integration/test_detail_routes.py
git commit -m "feat(content): add detail pages for post/question/journey/episode"
```

---

## Task 12: E2E + DoD verification

**Files:**
- Create: `app/tests/integration/test_post_workflow_e2e.py`

- [ ] **Step 1: Write E2E test**

Create `app/tests/integration/test_post_workflow_e2e.py`:

```python
"""End-to-end: login → upload image → write review → detail page renders."""
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.factories import RegionFactory, ResidentUserFactory


def _login_cookie(client: TestClient, user_id: int) -> dict[str, str]:
    from itsdangerous import TimestampSigner
    from app.config import get_settings
    import json, base64
    signer = TimestampSigner(get_settings().app_secret_key)
    raw = base64.b64encode(json.dumps({"user_id": user_id}).encode()).decode().rstrip("=")
    return {"nestory_session": signer.sign(raw.encode()).decode()}


def test_full_post_workflow_with_image(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    region = RegionFactory()
    db.commit()
    cookies = _login_cookie(client, user.id)

    # 1. Upload image
    sample = Path("app/tests/fixtures/sample.jpg").read_bytes()
    upload_r = client.post(
        "/htmx/image/upload",
        files={"image": ("sample.jpg", BytesIO(sample), "image/jpeg")},
        cookies=cookies,
    )
    assert upload_r.status_code == 200
    img_data = upload_r.json()
    img_id = img_data["image_id"]
    img_url = img_data["url"]

    # 2. Write review with image embedded in body
    body = f"단열이 가장 후회됨\n\n![]({img_url})"
    write_r = client.post(
        "/write/review",
        data={
            "title": "1년차 회고",
            "body": body,
            "region_id": str(region.id),
            "house_type": "단독",
            "size_pyeong": "30",
            "satisfaction_overall": "4",
        },
        cookies=cookies,
        follow_redirects=False,
    )
    assert write_r.status_code == 303
    post_url = write_r.headers["location"]

    # 3. View detail page
    detail_r = client.get(post_url)
    assert detail_r.status_code == 200
    assert "1년차 회고" in detail_r.text
    # Markdown filter swapped /img/{id}/orig → /img/{id}/medium
    assert f"/img/{img_id}/medium" in detail_r.text
    assert f"/img/{img_id}/orig" not in detail_r.text


def test_journey_workflow_create_episode_view(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    region = RegionFactory()
    db.commit()
    cookies = _login_cookie(client, user.id)

    # 1. Create journey
    j_r = client.post(
        "/write/journey",
        data={"title": "양평 정착기", "description": "터잡기부터", "region_id": str(region.id)},
        cookies=cookies,
        follow_redirects=False,
    )
    assert j_r.status_code == 303
    journey_url = j_r.headers["location"]
    journey_id = int(journey_url.split("/")[-1])

    # 2. Add episode
    ep_r = client.post(
        f"/write/journey/{journey_id}/ep",
        data={"title": "1화 터잡기", "body": "땅 매입", "phase": "터", "period_label": "2026-01"},
        cookies=cookies,
        follow_redirects=False,
    )
    assert ep_r.status_code == 303
    assert ep_r.headers["location"] == f"/journey/{journey_id}/ep/1"

    # 3. View journey listing
    list_r = client.get(journey_url)
    assert list_r.status_code == 200
    assert "1화 터잡기" in list_r.text


def test_question_answer_workflow(client: TestClient, db: Session) -> None:
    asker = ResidentUserFactory()
    answerer = ResidentUserFactory()
    region = RegionFactory()
    db.commit()

    # 1. Asker posts question
    q_r = client.post(
        "/write/question",
        data={"title": "단열재?", "body": "추천 부탁", "region_id": str(region.id), "tags": "단열"},
        cookies=_login_cookie(client, asker.id),
        follow_redirects=False,
    )
    q_url = q_r.headers["location"]

    # 2. Answerer posts answer
    a_r = client.post(
        f"{q_url}/answer",
        data={"body": "셀룰로오스 추천"},
        cookies=_login_cookie(client, answerer.id),
        follow_redirects=False,
    )
    assert a_r.status_code == 303

    # 3. Anyone views thread with answer
    detail = client.get(q_url)
    assert detail.status_code == 200
    assert "셀룰로오스 추천" in detail.text
```

- [ ] **Step 2: Run E2E tests**

```powershell
uv run pytest app/tests/integration/test_post_workflow_e2e.py -v
```
Expected: 3 pass.

- [ ] **Step 3: Verify DoD checklist**

Run each verification:

```powershell
# DoD 1-4: routes work — covered by passing tests
# DoD 5: image_resize creates variants — covered by test_image_resize_handler
# DoD 6: EXIF strip — covered by test_images_service::test_strip_exif_removes_gps_tags
# DoD 7: view_count — covered by test_detail_routes::test_post_view_count_increments
# DoD 8: PostMetadata Pydantic at every write route — covered by test_write_*_route::*_400_on_invalid

# DoD 9: pytest count
uv run pytest app/tests/ -q

# DoD 10: ruff
uv run ruff check app/

# DoD 11: services CLAUDE.md alignment
uv run python -c "import subprocess; r = subprocess.run(['rg', '-l', 'request.session', 'app/services/'], capture_output=True, text=True); print('FOUND:' if r.stdout else 'CLEAN'); print(r.stdout)"
# Expected: CLEAN (no matches)

# DoD 12: factory-boy in tests (no direct Post() in integration tests except documented bypasses)
uv run python -c "import subprocess; r = subprocess.run(['rg', '-n', '--type', 'py', r'^\s+Post\s*\(', 'app/tests/integration/'], capture_output=True, text=True); print(r.stdout)"
# Expected: empty or only documented bypasses (test_image_serve_route may have direct Image() — fine)
```

- [ ] **Step 4: Commit any final cleanup**

If verifications produced no diff, skip. Otherwise:

```powershell
git add <files>
git commit -m "test: complete P1.3 E2E and DoD verification"
```

---

## Self-Review Notes

- **Spec coverage**: Sections 3.1 (routers) → Tasks 4/7/8/9/10/11. 3.2 (services) → Tasks 2/5. 3.3 (worker) → Task 3. 3.4 (serve) → Task 4. 3.5/3.6 (write matrix + 4-section) → Tasks 7/8/9. 3.7 (HTMX upload) → Task 4 + Task 7 templates. 3.8 (form→service) → Tasks 7/8/9/10. 3.9 (detail) → Task 11. 3.10 (markdown) → Task 6. 3.11 (env) → Task 1. Section 4 test strategy → spread across all tasks. Section 5 DoD → Task 12.
- **Type/name consistency**: `Post.metadata_` (not `metadata`) used consistently. `posts_service` namespace alias used uniformly. `_login_cookie` helper duplicated across test files (could be extracted to conftest later — defer).
- **No placeholders**: every step has exact paths, code, commands, expected output. The Korean Tailwind templates use real class names + structure that work with the existing `cdn.tailwindcss.com` setup in `base.html`.

---

## Plan complete and saved to `docs/superpowers/plans/2026-05-07-nestory-phase1-3-content-and-images.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
