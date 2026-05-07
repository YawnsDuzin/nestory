from sqlalchemy.orm import Session

from app.models._enums import ImageStatus
from app.tests.factories import ImageFactory


def test_create_image_defaults_to_processing(db: Session) -> None:
    img = ImageFactory(
        file_path_orig="/media/orig/2026/05/abc.jpg",
        status=ImageStatus.PROCESSING,
    )

    assert img.id is not None
    assert img.status == ImageStatus.PROCESSING
    assert img.order_idx == 0
    assert img.uploaded_at is not None
    assert img.post_id is None


def test_image_can_have_all_size_paths(db: Session) -> None:
    img = ImageFactory(
        file_path_orig="/media/orig/x.jpg",
        file_path_thumb="/media/thumb/x.jpg",
        file_path_medium="/media/medium/x.jpg",
        file_path_webp="/media/webp/x.webp",
        status=ImageStatus.READY,
        width=1920,
        height=1080,
    )
    assert img.status == ImageStatus.READY
    assert img.file_path_webp.endswith(".webp")
