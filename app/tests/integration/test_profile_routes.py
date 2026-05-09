"""Integration tests for /u/{username} profile routes.

Tests:
- test_profile_home_returns_200
- test_profile_unknown_username_returns_404
- test_profile_posts_tab_returns_200_with_posts
- test_profile_journeys_tab_returns_200
- test_profile_scraps_owner_can_view
- test_profile_scraps_other_user_returns_403
- test_profile_scraps_anonymous_user_returns_401
- test_profile_excludes_soft_deleted_user

NOTE: Requires a running Postgres instance.
      Cannot be executed on a no-Docker PC — run on docker-up PC.
"""
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import PostStatus
from app.tests.factories import (
    JourneyEpisodePostFactory,
    JourneyFactory,
    ResidentUserFactory,
    ReviewPostFactory,
    UserFactory,
    add_post_scrap,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _published_review(author, **kwargs):
    return ReviewPostFactory(
        author=author,
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        **kwargs,
    )


def _published_journey_ep(author, journey, **kwargs):
    return JourneyEpisodePostFactory(
        author=author,
        region_id=journey.region_id,
        journey_id=journey.id,
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Profile home
# ---------------------------------------------------------------------------


def test_profile_home_returns_200(client: TestClient, db: Session) -> None:
    """GET /u/{username} returns 200 and shows username."""
    user = UserFactory(username="testuserprofile")
    db.commit()

    r = client.get(f"/u/{user.username}")
    assert r.status_code == 200
    assert user.username in r.text


def test_profile_unknown_username_returns_404(
    client: TestClient, db: Session
) -> None:
    """GET /u/no-such-user returns 404."""
    r = client.get("/u/no-such-user-xyz-9999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Posts tab
# ---------------------------------------------------------------------------


def test_profile_posts_tab_returns_200_with_posts(
    client: TestClient, db: Session
) -> None:
    """GET /u/{username}/posts returns 200 and shows the user's review posts."""
    user = ResidentUserFactory()
    _published_review(user, title="내 첫 번째 후기")
    _published_review(user, title="내 두 번째 후기")
    db.commit()

    r = client.get(f"/u/{user.username}/posts")
    assert r.status_code == 200
    assert "내 첫 번째 후기" in r.text
    assert "내 두 번째 후기" in r.text


# ---------------------------------------------------------------------------
# Journeys tab
# ---------------------------------------------------------------------------


def test_profile_journeys_tab_returns_200(client: TestClient, db: Session) -> None:
    """GET /u/{username}/journeys returns 200 and shows journey episodes."""
    user = ResidentUserFactory()
    journey = JourneyFactory(author=user, title="나의 Journey")
    _published_journey_ep(user, journey, episode_no=1, title="1화 시작")
    db.commit()

    r = client.get(f"/u/{user.username}/journeys")
    assert r.status_code == 200
    assert "1화 시작" in r.text


# ---------------------------------------------------------------------------
# Scraps tab — owner-only
# ---------------------------------------------------------------------------


def test_profile_scraps_owner_can_view(
    client: TestClient, db: Session, login
) -> None:
    """Owner can view their own scraps tab."""
    user = UserFactory()
    post = _published_review(ResidentUserFactory(), title="스크랩할 후기")
    db.commit()
    add_post_scrap(db, user, post)
    db.commit()

    login(user.id)
    r = client.get(f"/u/{user.username}/scraps")
    assert r.status_code == 200
    assert "스크랩할 후기" in r.text


def test_profile_scraps_other_user_returns_403(
    client: TestClient, db: Session, login
) -> None:
    """Another logged-in user cannot view someone else's scraps — 403."""
    owner = UserFactory()
    other = UserFactory()
    db.commit()

    login(other.id)
    r = client.get(f"/u/{owner.username}/scraps")
    assert r.status_code == 403


def test_profile_scraps_anonymous_user_returns_401(
    client: TestClient, db: Session
) -> None:
    """Anonymous user accessing /scraps gets 401."""
    user = UserFactory()
    db.commit()

    r = client.get(f"/u/{user.username}/scraps")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# Soft-deleted user
# ---------------------------------------------------------------------------


def test_profile_excludes_soft_deleted_user(
    client: TestClient, db: Session
) -> None:
    """GET /u/{username} for a soft-deleted user returns 404."""
    user = UserFactory(deleted_at=datetime.now(UTC))
    db.commit()

    r = client.get(f"/u/{user.username}")
    assert r.status_code == 404
