from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models._enums import CommentStatus
from app.tests.factories import CommentFactory


def test_create_top_level_comment(db: Session) -> None:
    c = CommentFactory(body="좋은 후기네요")
    assert c.id is not None
    assert c.parent_id is None
    assert c.status == CommentStatus.VISIBLE


def test_threaded_reply(db: Session) -> None:
    parent = CommentFactory(body="원댓글")
    reply = CommentFactory(
        post_id=parent.post_id,
        author_id=parent.author_id,
        parent_id=parent.id,
        body="답글",
    )
    assert reply.parent_id == parent.id


def test_soft_delete_comment(db: Session) -> None:
    c = CommentFactory(body="x")
    c.deleted_at = datetime.now(UTC)
    db.flush()
    assert c.deleted_at is not None
