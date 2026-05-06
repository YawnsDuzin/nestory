from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Comment, Post, Region, User
from app.models._enums import CommentStatus, PostType


def _seed(db: Session) -> tuple[User, Post]:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    r = Region(sido="경기", sigungu="양평군", slug=f"yp-{u.username}")
    db.add_all([u, r])
    db.flush()
    p = Post(author_id=u.id, region_id=r.id, type=PostType.REVIEW, title="t", body="b")
    db.add(p)
    db.flush()
    return u, p


def test_create_top_level_comment(db: Session) -> None:
    u, p = _seed(db)
    c = Comment(post_id=p.id, author_id=u.id, body="좋은 후기네요")
    db.add(c)
    db.flush()
    assert c.id is not None
    assert c.parent_id is None
    assert c.status == CommentStatus.VISIBLE


def test_threaded_reply(db: Session) -> None:
    u, p = _seed(db)
    parent = Comment(post_id=p.id, author_id=u.id, body="원댓글")
    db.add(parent)
    db.flush()
    reply = Comment(post_id=p.id, author_id=u.id, parent_id=parent.id, body="답글")
    db.add(reply)
    db.flush()
    assert reply.parent_id == parent.id


def test_soft_delete_comment(db: Session) -> None:
    u, p = _seed(db)
    c = Comment(post_id=p.id, author_id=u.id, body="x")
    db.add(c)
    db.flush()
    c.deleted_at = datetime.now(UTC)
    db.flush()
    assert c.deleted_at is not None
