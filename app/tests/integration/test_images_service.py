"""Tests for the synchronous image upload pipeline."""
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Job
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
    assert all(tag != 34853 for tag in exif)


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


def test_validate_upload_aborts_early_on_oversize_streaming() -> None:
    """Streaming a body larger than max_upload_size aborts before full read."""
    settings = get_settings()
    # Build a stream that's 2x the limit but reports as one big blob
    huge = b"\xff\xd8\xff" + b"\x00" * (settings.max_upload_size + 100)
    f = UploadFile(filename="huge.jpg", file=BytesIO(huge), size=len(huge))
    with pytest.raises(HTTPException) as exc:
        images_service.validate_upload(f)
    assert exc.value.status_code == 400
