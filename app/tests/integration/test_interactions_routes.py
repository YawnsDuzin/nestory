"""Integration tests for like/scrap toggle HTMX endpoints.

Tests:
- test_like_returns_200_with_button_partial
- test_like_anonymous_returns_401
- test_unlike_returns_200
- test_scrap_returns_200
- test_unscrap_returns_200
- test_like_unknown_post_returns_404
- test_like_self_post_works

NOTE: Requires a running Postgres instance.
      Cannot be executed on a no-Docker PC — run on docker-up PC.
"""
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import PostStatus
from app.tests.factories import (
    ReviewPostFactory,
    UserFactory,
    add_post_like,
    add_post_scrap,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _published_review(author=None, **kwargs):
    kw = dict(status=PostStatus.PUBLISHED, published_at=datetime.now(UTC))
    if author is not None:
        kw["author"] = author
    kw.update(kwargs)
    return ReviewPostFactory(**kw)


# ---------------------------------------------------------------------------
# Like
# ---------------------------------------------------------------------------


def test_like_returns_200_with_button_partial(
    client: TestClient, db: Session, login
) -> None:
    """POST /post/{id}/like returns 200 and swaps like_button partial (HTMX)."""
    user = UserFactory()
    post = _published_review()
    db.commit()

    login(user.id)
    r = client.post(f"/post/{post.id}/like")
    assert r.status_code == 200
    # Partial contains the button ID used by hx-target
    assert f"like-btn-{post.id}" in r.text


def test_like_anonymous_returns_401(client: TestClient, db: Session) -> None:
    """POST /post/{id}/like without login returns 401."""
    post = _published_review()
    db.commit()

    r = client.post(f"/post/{post.id}/like")
    assert r.status_code == 401


def test_unlike_returns_200(client: TestClient, db: Session, login) -> None:
    """POST /post/{id}/unlike returns 200 with button partial (unliked state)."""
    user = UserFactory()
    post = _published_review()
    db.commit()
    add_post_like(db, user, post)
    db.commit()

    login(user.id)
    r = client.post(f"/post/{post.id}/unlike")
    assert r.status_code == 200
    assert f"like-btn-{post.id}" in r.text


# ---------------------------------------------------------------------------
# Scrap
# ---------------------------------------------------------------------------


def test_scrap_returns_200(client: TestClient, db: Session, login) -> None:
    """POST /post/{id}/scrap returns 200 with scrap_button partial."""
    user = UserFactory()
    post = _published_review()
    db.commit()

    login(user.id)
    r = client.post(f"/post/{post.id}/scrap")
    assert r.status_code == 200
    assert f"scrap-btn-{post.id}" in r.text


def test_unscrap_returns_200(client: TestClient, db: Session, login) -> None:
    """POST /post/{id}/unscrap returns 200 with scrap_button partial."""
    user = UserFactory()
    post = _published_review()
    db.commit()
    add_post_scrap(db, user, post)
    db.commit()

    login(user.id)
    r = client.post(f"/post/{post.id}/unscrap")
    assert r.status_code == 200
    assert f"scrap-btn-{post.id}" in r.text


# ---------------------------------------------------------------------------
# 404 guard
# ---------------------------------------------------------------------------


def test_like_unknown_post_returns_404(
    client: TestClient, db: Session, login
) -> None:
    """POST /post/99999/like for non-existent post returns 404."""
    user = UserFactory()
    db.commit()

    login(user.id)
    r = client.post("/post/99999/like")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Self-like allowed
# ---------------------------------------------------------------------------


def test_like_self_post_works(client: TestClient, db: Session, login) -> None:
    """Author can like their own post — no rule prevents it in P1.4."""
    user = UserFactory()
    post = _published_review(author=user)
    db.commit()

    login(user.id)
    r = client.post(f"/post/{post.id}/like")
    assert r.status_code == 200
    assert f"like-btn-{post.id}" in r.text
