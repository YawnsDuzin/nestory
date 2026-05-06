from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Comment
from app.models._enums import CommentStatus
from app.tests.factories import ReviewPostFactory


def test_create_top_level_comment(db: Session) -> None:
    p = ReviewPostFactory()
    c = Comment(post_id=p.id, author_id=p.author_id, body="좋은 후기네요")
    db.add(c)
    db.flush()
    assert c.id is not None
    assert c.parent_id is None
    assert c.status == CommentStatus.VISIBLE


def test_threaded_reply(db: Session) -> None:
    p = ReviewPostFactory()
    parent = Comment(post_id=p.id, author_id=p.author_id, body="원댓글")
    db.add(parent)
    db.flush()
    reply = Comment(post_id=p.id, author_id=p.author_id, parent_id=parent.id, body="답글")
    db.add(reply)
    db.flush()
    assert reply.parent_id == parent.id


def test_soft_delete_comment(db: Session) -> None:
    p = ReviewPostFactory()
    c = Comment(post_id=p.id, author_id=p.author_id, body="x")
    db.add(c)
    db.flush()
    c.deleted_at = datetime.now(UTC)
    db.flush()
    assert c.deleted_at is not None
