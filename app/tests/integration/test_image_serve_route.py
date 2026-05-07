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


def test_serve_invalid_variant_returns_404(client: TestClient, db: Session) -> None:
    img_id, _ = _make_real_image_files(db)
    r = client.get(f"/img/{img_id}/large")  # not in whitelist
    assert r.status_code == 404
