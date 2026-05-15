"""update_* / soft_delete_post 서비스 함수 단위 테스트."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models._enums import PostStatus, PostType
from app.schemas.post_metadata import QuestionMetadata
from app.services import posts as posts_service
from app.tests.factories import PostFactory, UserFactory


def test_update_question_changes_title_body_tags(db: Session) -> None:
    author = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
        title="기존 제목", body="기존 본문",
        metadata_={"__post_type__": "question", "tags": ["old"]},
    )
    db.flush()
    payload = QuestionMetadata(tags=["new1", "new2"])
    updated = posts_service.update_question(
        db, post, payload=payload, title="새 제목", body="새 본문"
    )
    assert updated.title == "새 제목"
    assert updated.body == "새 본문"
    assert updated.metadata_["tags"] == ["new1", "new2"]
    assert updated.edited_at is not None
    assert updated.type == PostType.QUESTION  # 불변
    assert updated.author_id == author.id     # 불변


def test_update_question_sets_edited_at_close_to_now(db: Session) -> None:
    post = PostFactory(type=PostType.QUESTION, status=PostStatus.PUBLISHED)
    db.flush()
    before = datetime.now(UTC)
    posts_service.update_question(
        db, post,
        payload=QuestionMetadata(tags=[]),
        title="t", body="b",
    )
    after = datetime.now(UTC)
    assert post.edited_at is not None
    assert before <= post.edited_at <= after
