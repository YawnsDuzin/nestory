from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Image, User
from app.models._enums import ImageStatus


def _make_user(db: Session) -> User:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    db.add(u)
    db.flush()
    return u


def test_create_image_defaults_to_processing(db: Session) -> None:
    u = _make_user(db)
    img = Image(owner_id=u.id, file_path_orig="/media/orig/2026/05/abc.jpg")
    db.add(img)
    db.flush()

    assert img.id is not None
    assert img.status == ImageStatus.PROCESSING
    assert img.order_idx == 0
    assert img.uploaded_at is not None
    assert img.post_id is None


def test_image_can_have_all_size_paths(db: Session) -> None:
    u = _make_user(db)
    img = Image(
        owner_id=u.id,
        file_path_orig="/media/orig/x.jpg",
        file_path_thumb="/media/thumb/x.jpg",
        file_path_medium="/media/medium/x.jpg",
        file_path_webp="/media/webp/x.webp",
        status=ImageStatus.READY,
        width=1920,
        height=1080,
    )
    db.add(img)
    db.flush()
    assert img.status == ImageStatus.READY
    assert img.file_path_webp.endswith(".webp")
