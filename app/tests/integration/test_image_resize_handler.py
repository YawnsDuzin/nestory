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
from app.workers.handlers import import_handlers
from app.workers.runner import process_one

# Register all handlers so process_one() can dispatch them when this test
# module runs standalone (full-suite runs already import via test_worker_e2e).
import_handlers()


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
    img = ImageFactory(
        owner=user,
        file_path_orig="images/does-not-exist/orig.jpg",
        status=ImageStatus.PROCESSING,
    )
    queue.enqueue(db, JobKind.IMAGE_RESIZE, {"image_id": img.id})
    db.commit()

    process_one()

    db.refresh(img)
    assert img.status == ImageStatus.FAILED
    job = db.query(Job).filter(Job.kind == JobKind.IMAGE_RESIZE).order_by(Job.id.desc()).first()
    assert job.status in (JobStatus.FAILED, JobStatus.QUEUED)  # depending on retry policy
