"""Integration tests for home_data and global_feed services.

Covers:
- Anonymous user has empty followed_episodes
- recommended_regions ordered by is_pilot DESC, id ASC
- popular_reviews ordered by view_count DESC
- recent_journeys ordered by published_at DESC
- Logged-in user: followed_episodes only from journeys the user follows
- followed_episodes excludes DRAFT episodes
- global_feed pagination (page 1 = 20, page 2 = remainder)
- global_feed ordered by published_at DESC
- global_feed excludes DRAFT and soft-deleted posts

NOTE: These tests require a running Postgres instance.
      They CANNOT be executed on a no-Docker PC — run on docker-up PC.
"""
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models._enums import PostStatus
from app.services import feed as feed_service
from app.tests.factories import (
    JourneyEpisodePostFactory,
    JourneyFactory,
    PilotRegionFactory,
    RegionFactory,
    ReviewPostFactory,
    UserFactory,
    add_journey_follow,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _published_review(region, *, view_count=0, **kwargs):
    """Shorthand: PUBLISHED ReviewPost."""
    kwargs.setdefault("published_at", datetime.now(UTC))
    return ReviewPostFactory(
        status=PostStatus.PUBLISHED,
        region=region,
        view_count=view_count,
        **kwargs,
    )


def _published_episode(region, journey, *, published_at=None, **kwargs):
    """Shorthand: PUBLISHED JourneyEpisodePost."""
    return JourneyEpisodePostFactory(
        status=PostStatus.PUBLISHED,
        published_at=published_at or datetime.now(UTC),
        region=region,
        journey=journey,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 1. Anonymous user — empty followed_episodes
# ---------------------------------------------------------------------------


def test_home_data_anonymous_user_has_empty_followed_episodes(db: Session) -> None:
    """home_data(db, None) must return followed_episodes == []."""
    data = feed_service.home_data(db, None)
    assert data.followed_episodes == []


# ---------------------------------------------------------------------------
# 2. recommended_regions — pilot first, then id ASC
# ---------------------------------------------------------------------------


def test_home_data_pilot_regions_first_then_id_order(db: Session) -> None:
    """recommended_regions must be ordered is_pilot DESC, id ASC."""
    non_pilot = RegionFactory(slug="feed-region-non-pilot")
    pilot = PilotRegionFactory(slug="feed-region-pilot")
    db.flush()

    data = feed_service.home_data(db, None)
    # Pilot region must precede non-pilot
    ids = [r.id for r in data.recommended_regions]
    pilot_index = ids.index(pilot.id)
    non_pilot_index = ids.index(non_pilot.id)
    assert pilot_index < non_pilot_index


# ---------------------------------------------------------------------------
# 3. popular_reviews — ordered by view_count DESC
# ---------------------------------------------------------------------------


def test_home_data_popular_reviews_view_count_desc(db: Session) -> None:
    """popular_reviews must be ordered by view_count descending."""
    region = RegionFactory(slug="feed-popular-reviews")
    _published_review(region, view_count=10)
    top = _published_review(region, view_count=500)
    _published_review(region, view_count=50)
    db.flush()

    data = feed_service.home_data(db, None)
    assert len(data.popular_reviews) >= 3
    # Highest-viewed post must be first
    assert data.popular_reviews[0].id == top.id


# ---------------------------------------------------------------------------
# 4. recent_journeys — ordered by published_at DESC
# ---------------------------------------------------------------------------


def test_home_data_recent_journeys_published_at_desc(db: Session) -> None:
    """recent_journeys must be ordered by published_at descending."""
    region = RegionFactory(slug="feed-recent-journeys")
    journey = JourneyFactory(region=region)

    older = _published_episode(
        region, journey,
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    newer = _published_episode(
        region, journey,
        published_at=datetime(2026, 3, 1, tzinfo=UTC),
    )
    db.flush()

    data = feed_service.home_data(db, None)
    ep_ids = [p.id for p in data.recent_journeys]
    assert newer.id in ep_ids
    assert older.id in ep_ids
    # Newer must appear before older
    assert ep_ids.index(newer.id) < ep_ids.index(older.id)


# ---------------------------------------------------------------------------
# 5. Logged-in user — followed_episodes only from followed journeys
# ---------------------------------------------------------------------------


def test_home_data_logged_in_user_followed_episodes_only_followed_journeys(
    db: Session,
) -> None:
    """Only episodes belonging to journeys the user follows must appear."""
    region = RegionFactory(slug="feed-followed-eps")
    user = UserFactory()

    journey_followed = JourneyFactory(region=region)
    journey_other = JourneyFactory(region=region)

    followed_ep = _published_episode(region, journey_followed)
    other_ep = _published_episode(region, journey_other)
    db.flush()

    add_journey_follow(db, user, journey_followed)
    db.flush()

    data = feed_service.home_data(db, user)
    ep_ids = {p.id for p in data.followed_episodes}
    assert followed_ep.id in ep_ids
    assert other_ep.id not in ep_ids


# ---------------------------------------------------------------------------
# 6. followed_episodes — DRAFT excluded
# ---------------------------------------------------------------------------


def test_home_data_followed_episodes_excludes_draft(db: Session) -> None:
    """DRAFT episodes must not appear in followed_episodes."""
    region = RegionFactory(slug="feed-followed-draft")
    user = UserFactory()
    journey = JourneyFactory(region=region)

    published_ep = _published_episode(region, journey)
    # DRAFT episode in the same followed journey
    JourneyEpisodePostFactory(
        status=PostStatus.DRAFT,
        region=region,
        journey=journey,
    )
    db.flush()

    add_journey_follow(db, user, journey)
    db.flush()

    data = feed_service.home_data(db, user)
    ep_ids = {p.id for p in data.followed_episodes}
    assert published_ep.id in ep_ids
    for ep in data.followed_episodes:
        assert ep.status == PostStatus.PUBLISHED


# ---------------------------------------------------------------------------
# 7. global_feed — pagination
# ---------------------------------------------------------------------------


def test_global_feed_pagination(db: Session) -> None:
    """Page 1 must have 20 posts; page 2 must have the remainder (2)."""
    region = RegionFactory(slug="feed-global-pagination")
    for _ in range(22):
        _published_review(region)
    db.flush()

    posts_p1, total_p1 = feed_service.global_feed(db, page=1)
    posts_p2, total_p2 = feed_service.global_feed(db, page=2)

    assert total_p1 == total_p2
    assert total_p1 >= 22
    assert len(posts_p1) == feed_service.PAGE_SIZE
    assert len(posts_p2) >= 2

    p1_ids = {p.id for p in posts_p1}
    p2_ids = {p.id for p in posts_p2}
    assert p1_ids.isdisjoint(p2_ids)


# ---------------------------------------------------------------------------
# 8. global_feed — ordered by published_at DESC
# ---------------------------------------------------------------------------


def test_global_feed_orders_by_published_at_desc(db: Session) -> None:
    """global_feed must return the most recently published post first."""
    region = RegionFactory(slug="feed-global-order")
    older = _published_review(
        region,
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    newer = _published_review(
        region,
        published_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    db.flush()

    posts, _ = feed_service.global_feed(db, page=1)
    post_ids = [p.id for p in posts]
    assert newer.id in post_ids
    assert older.id in post_ids
    assert post_ids.index(newer.id) < post_ids.index(older.id)


# ---------------------------------------------------------------------------
# 9. global_feed — excludes DRAFT and soft-deleted
# ---------------------------------------------------------------------------


def test_global_feed_excludes_drafts_and_soft_deleted(db: Session) -> None:
    """DRAFT posts and soft-deleted posts must never appear in global_feed."""
    region = RegionFactory(slug="feed-global-exclusion")

    published = _published_review(region)

    ReviewPostFactory(status=PostStatus.DRAFT, region=region)
    ReviewPostFactory(
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        deleted_at=datetime.now(UTC),
        region=region,
    )
    db.flush()

    posts, total = feed_service.global_feed(db, page=1)
    post_ids = [p.id for p in posts]
    assert published.id in post_ids
    for p in posts:
        assert p.status == PostStatus.PUBLISHED
        assert p.deleted_at is None
