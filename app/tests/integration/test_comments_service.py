"""Integration tests for comments service (create + list).

NOTE: These tests require a running Postgres instance.
      They CANNOT be executed on a no-Docker PC — run on docker-up PC.
"""
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.models._enums import CommentStatus
from app.services import comments as svc
from app.services.comments import MAX_BODY, CommentValidationError
from app.tests.factories import CommentFactory, ReviewPostFactory, UserFactory

# ---------------------------------------------------------------------------
# create_comment — top-level
# ---------------------------------------------------------------------------


def test_create_comment_top_level(db: Session) -> None:
    post = ReviewPostFactory()
    user = UserFactory()
    comment = svc.create_comment(db, post, user, "좋은 글이네요")
    assert comment.id is not None
    assert comment.post_id == post.id
    assert comment.author_id == user.id
    assert comment.body == "좋은 글이네요"
    assert comment.parent_id is None


def test_create_comment_strips_whitespace(db: Session) -> None:
    post = ReviewPostFactory()
    user = UserFactory()
    comment = svc.create_comment(db, post, user, "  hi  ")
    assert comment.body == "hi"


def test_create_comment_empty_body_raises(db: Session) -> None:
    post = ReviewPostFactory()
    user = UserFactory()
    with pytest.raises(CommentValidationError):
        svc.create_comment(db, post, user, "")


def test_create_comment_whitespace_only_body_raises(db: Session) -> None:
    post = ReviewPostFactory()
    user = UserFactory()
    with pytest.raises(CommentValidationError):
        svc.create_comment(db, post, user, "   ")


def test_create_comment_too_long_body_raises(db: Session) -> None:
    post = ReviewPostFactory()
    user = UserFactory()
    with pytest.raises(CommentValidationError):
        svc.create_comment(db, post, user, "a" * (MAX_BODY + 1))


# ---------------------------------------------------------------------------
# create_comment — replies
# ---------------------------------------------------------------------------


def test_create_comment_with_valid_parent(db: Session) -> None:
    post = ReviewPostFactory()
    user = UserFactory()
    parent = CommentFactory(post=post, author=user)
    reply = svc.create_comment(db, post, user, "답글입니다", parent_id=parent.id)
    assert reply.parent_id == parent.id
    assert reply.post_id == post.id


def test_create_comment_unknown_parent_raises(db: Session) -> None:
    post = ReviewPostFactory()
    user = UserFactory()
    with pytest.raises(CommentValidationError):
        svc.create_comment(db, post, user, "댓글", parent_id=99999)


def test_create_comment_parent_from_other_post_raises(db: Session) -> None:
    post = ReviewPostFactory()
    other_post = ReviewPostFactory()
    user = UserFactory()
    parent = CommentFactory(post=other_post, author=user)
    with pytest.raises(CommentValidationError):
        svc.create_comment(db, post, user, "댓글", parent_id=parent.id)


def test_create_comment_nested_reply_raises(db: Session) -> None:
    """1-level only: cannot reply to a reply."""
    post = ReviewPostFactory()
    user = UserFactory()
    parent = CommentFactory(post=post, author=user)
    reply = CommentFactory(post=post, author=user, parent=parent)
    with pytest.raises(CommentValidationError):
        svc.create_comment(db, post, user, "중첩 댓글", parent_id=reply.id)


# ---------------------------------------------------------------------------
# list_comments — filtering
# ---------------------------------------------------------------------------


def test_list_comments_visible_only(db: Session) -> None:
    post = ReviewPostFactory()
    user = UserFactory()
    visible = CommentFactory(post=post, author=user, status=CommentStatus.VISIBLE)
    CommentFactory(post=post, author=user, status=CommentStatus.HIDDEN)
    result = svc.list_comments(db, post)
    ids = [c.id for c in result]
    assert visible.id in ids
    assert len(ids) == 1


def test_list_comments_excludes_soft_deleted(db: Session) -> None:
    post = ReviewPostFactory()
    user = UserFactory()
    alive = CommentFactory(post=post, author=user)
    CommentFactory(post=post, author=user, deleted_at=datetime.now(UTC))
    result = svc.list_comments(db, post)
    ids = [c.id for c in result]
    assert alive.id in ids
    assert len(ids) == 1


# ---------------------------------------------------------------------------
# list_comments — ordering
# ---------------------------------------------------------------------------


def test_list_comments_orders_top_level_before_replies_then_by_time(
    db: Session,
) -> None:
    """Order: top-level A, top-level B, then reply A1.

    Even though A1 is created after A (in between A and B creation time),
    all top-levels appear before any replies, so result = [A, B, A1].
    """
    post = ReviewPostFactory()
    user = UserFactory()
    comment_a = CommentFactory(post=post, author=user, body="A")
    reply_a1 = CommentFactory(post=post, author=user, body="A1", parent=comment_a)
    comment_b = CommentFactory(post=post, author=user, body="B")

    result = svc.list_comments(db, post)
    ids = [c.id for c in result]
    # top-levels (A and B) must come before the reply (A1)
    assert ids.index(comment_a.id) < ids.index(reply_a1.id)
    assert ids.index(comment_b.id) < ids.index(reply_a1.id)
    # total count = 3
    assert len(ids) == 3
