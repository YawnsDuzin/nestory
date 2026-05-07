"""Integration tests for /feed route — global published post feed.

Tests:
- test_feed_returns_200_with_posts
- test_feed_anonymous_user_works
- test_feed_logged_in_user_works
- test_feed_pagination_query_param
- test_feed_excludes_drafts

NOTE: Requires a running Postgres instance.
      Cannot be executed on a no-Docker PC — run on docker-up PC.
"""
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import PostStatus
from app.tests.factories import (
    ResidentUserFactory,
    ReviewPostFactory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _published(title: str = "", **kwargs) -> ReviewPostFactory:
    kw = dict(
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
    )
    if title:
        kw["title"] = title
    kw.update(kwargs)
    return ReviewPostFactory(**kw)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_feed_returns_200_with_posts(client: TestClient, db: Session) -> None:
    """GET /feed returns 200 and renders all 3 published post titles."""
    _published("피드 글 A")
    _published("피드 글 B")
    _published("피드 글 C")
    db.commit()

    r = client.get("/feed")
    assert r.status_code == 200
    assert "피드 글 A" in r.text
    assert "피드 글 B" in r.text
    assert "피드 글 C" in r.text


def test_feed_anonymous_user_works(client: TestClient, db: Session) -> None:
    """GET /feed without a session cookie should return 200."""
    _published("익명 피드 테스트")
    db.commit()

    r = client.get("/feed")
    assert r.status_code == 200


def test_feed_logged_in_user_works(
    client: TestClient, db: Session, login
) -> None:
    """GET /feed with a logged-in ResidentUser should return 200."""
    user = ResidentUserFactory()
    _published("로그인 피드 테스트")
    db.commit()

    login(user.id)
    r = client.get("/feed")
    assert r.status_code == 200


def test_feed_pagination_query_param(client: TestClient, db: Session) -> None:
    """Page 2 should have fewer post cards than page 1 when there are 22 posts."""
    for _ in range(22):
        _published()
    db.commit()

    r1 = client.get("/feed?page=1")
    r2 = client.get("/feed?page=2")
    assert r1.status_code == 200
    assert r2.status_code == 200
    # post_card.html renders a distinctive class; count occurrences per page
    count_p1 = r1.text.count("rounded border bg-white p-4")
    count_p2 = r2.text.count("rounded border bg-white p-4")
    assert count_p1 > count_p2


def test_feed_excludes_drafts(client: TestClient, db: Session) -> None:
    """DRAFT posts must not appear in the feed."""
    _published("공개 글")
    ReviewPostFactory(status=PostStatus.DRAFT, title="임시저장 글")
    db.commit()

    r = client.get("/feed")
    assert r.status_code == 200
    assert "공개 글" in r.text
    assert "임시저장 글" not in r.text
