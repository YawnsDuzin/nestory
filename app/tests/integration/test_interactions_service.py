"""Integration tests for interactions service (like/scrap toggles).

NOTE: These tests require a running Postgres instance.
      They CANNOT be executed on a no-Docker PC — run on docker-up PC.
"""
from sqlalchemy.orm import Session

from app.services import interactions as svc
from app.tests.factories import ReviewPostFactory, UserFactory

# ---------------------------------------------------------------------------
# Like tests
# ---------------------------------------------------------------------------


def test_toggle_like_first_call_returns_true(db: Session) -> None:
    user = UserFactory()
    post = ReviewPostFactory()
    result = svc.toggle_like(db, post, user)
    assert result is True


def test_toggle_like_second_call_returns_false(db: Session) -> None:
    user = UserFactory()
    post = ReviewPostFactory()
    first = svc.toggle_like(db, post, user)
    second = svc.toggle_like(db, post, user)
    assert first is True
    assert second is False


def test_toggle_like_idempotent_creates_only_one_row(db: Session) -> None:
    user = UserFactory()
    post = ReviewPostFactory()
    svc.toggle_like(db, post, user)
    assert svc.like_count(db, post.id) == 1
    svc.toggle_like(db, post, user)
    assert svc.like_count(db, post.id) == 0


def test_toggle_like_does_not_affect_other_user(db: Session) -> None:
    user_a = UserFactory()
    user_b = UserFactory()
    post = ReviewPostFactory()
    svc.toggle_like(db, post, user_a)
    assert svc.is_liked_by(db, post.id, user_b.id) is False
    assert svc.like_count(db, post.id) == 1


# ---------------------------------------------------------------------------
# Scrap tests
# ---------------------------------------------------------------------------


def test_toggle_scrap_first_call_returns_true(db: Session) -> None:
    user = UserFactory()
    post = ReviewPostFactory()
    result = svc.toggle_scrap(db, post, user)
    assert result is True


def test_toggle_scrap_second_call_returns_false(db: Session) -> None:
    user = UserFactory()
    post = ReviewPostFactory()
    first = svc.toggle_scrap(db, post, user)
    second = svc.toggle_scrap(db, post, user)
    assert first is True
    assert second is False


def test_scrap_count_zero_initially(db: Session) -> None:
    post = ReviewPostFactory()
    assert svc.scrap_count(db, post.id) == 0


def test_is_scrapped_by_unknown_user_returns_false(db: Session) -> None:
    user = UserFactory()
    post = ReviewPostFactory()
    # user never scrapped post
    assert svc.is_scrapped_by(db, post.id, user.id) is False
