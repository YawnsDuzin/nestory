"""Integration tests for hub_overview, hub_tab_posts, and region_neighbors services.

Covers:
- get_region_by_slug — known slug returns Region, unknown returns None
- hub_overview counts published posts by type (DRAFT excluded)
- hub_overview resident_count includes RESIDENT and EX_RESIDENT only
- hub_overview popular_reviews ordered by view_count DESC
- hub_overview excludes posts from other regions
- hub_tab_posts pagination (page 1 full = 20, page 2 partial)
- hub_tab_posts sort=popular ordered by view_count DESC
- hub_tab_posts excludes DRAFT and soft-deleted posts
- region_neighbors returns only RESIDENT / EX_RESIDENT, excludes other region

NOTE: These tests require a running Postgres instance.
      They CANNOT be executed on a no-Docker PC — run on docker-up PC.
"""
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import BadgeLevel
from app.models._enums import PostStatus, PostType
from app.services import hub as hub_service
from app.tests.factories import (
    JourneyEpisodePostFactory,
    PilotRegionFactory,
    QuestionPostFactory,
    RegionFactory,
    ResidentUserFactory,
    ReviewPostFactory,
    UserFactory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _published_review(region, *, view_count=0, **kwargs):
    """Shorthand: PUBLISHED ReviewPost."""
    return ReviewPostFactory(
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        region=region,
        view_count=view_count,
        **kwargs,
    )


def _published_journey_ep(region, *, published_at=None, **kwargs):
    """Shorthand: PUBLISHED JourneyEpisodePost."""
    return JourneyEpisodePostFactory(
        status=PostStatus.PUBLISHED,
        published_at=published_at or datetime.now(UTC),
        region=region,
        **kwargs,
    )


def _published_question(region, **kwargs):
    """Shorthand: PUBLISHED QuestionPost."""
    return QuestionPostFactory(
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        region=region,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 1. get_region_by_slug
# ---------------------------------------------------------------------------


def test_get_region_by_slug_returns_region(db: Session) -> None:
    """Known slug must return the matching Region."""
    region = RegionFactory(slug="gyeonggi-yangpyeong")
    db.flush()

    result = hub_service.get_region_by_slug(db, "gyeonggi-yangpyeong")
    assert result is not None
    assert result.id == region.id


def test_get_region_by_slug_unknown_returns_none(db: Session) -> None:
    """Unknown slug must return None."""
    result = hub_service.get_region_by_slug(db, "no-such-region-slug")
    assert result is None


# ---------------------------------------------------------------------------
# 2. hub_overview counts
# ---------------------------------------------------------------------------


def test_hub_overview_counts_published_posts_by_type(db: Session) -> None:
    """Published REVIEW/JOURNEY_EPISODE/QUESTION each count as 1; DRAFT excluded."""
    region = PilotRegionFactory(slug="hub-overview-counts")

    _published_review(region)
    _published_journey_ep(region)
    _published_question(region)

    # DRAFT post — must NOT be counted
    ReviewPostFactory(
        status=PostStatus.DRAFT,
        region=region,
    )
    db.flush()

    overview = hub_service.hub_overview(db, region)
    assert overview.review_count == 1
    assert overview.journey_count == 1
    assert overview.question_count == 1


# ---------------------------------------------------------------------------
# 3. resident_count includes RESIDENT and EX_RESIDENT
# ---------------------------------------------------------------------------


def test_hub_overview_resident_count_includes_resident_and_ex_resident(db: Session) -> None:
    """resident_count = RESIDENT + EX_RESIDENT; INTERESTED excluded."""
    region = RegionFactory(slug="hub-resident-count")

    # 2 RESIDENT users
    ResidentUserFactory(primary_region_id=region.id)
    ResidentUserFactory(primary_region_id=region.id)

    # 1 EX_RESIDENT user
    UserFactory(
        badge_level=BadgeLevel.EX_RESIDENT,
        primary_region_id=region.id,
    )

    # 1 INTERESTED user — must NOT count
    UserFactory(
        badge_level=BadgeLevel.INTERESTED,
        primary_region_id=region.id,
    )

    db.flush()

    overview = hub_service.hub_overview(db, region)
    assert overview.resident_count == 3


# ---------------------------------------------------------------------------
# 4. popular_reviews ordered by view_count DESC
# ---------------------------------------------------------------------------


def test_hub_overview_popular_reviews_ordered_by_view_count_desc(db: Session) -> None:
    """popular_reviews must be sorted by view_count descending."""
    region = RegionFactory(slug="hub-popular-reviews")

    _published_review(region, view_count=10)
    _published_review(region, view_count=100)
    _published_review(region, view_count=50)
    db.flush()

    overview = hub_service.hub_overview(db, region)
    assert len(overview.popular_reviews) == 3
    counts = [p.view_count for p in overview.popular_reviews]
    assert counts == sorted(counts, reverse=True)


# ---------------------------------------------------------------------------
# 5. hub_overview excludes other regions
# ---------------------------------------------------------------------------


def test_hub_overview_excludes_other_region(db: Session) -> None:
    """Posts from a different region must not affect counts."""
    region_a = RegionFactory(slug="hub-region-a")
    region_b = RegionFactory(slug="hub-region-b")

    _published_review(region_a)
    # 3 posts for region_b — must NOT appear in region_a overview
    _published_review(region_b)
    _published_review(region_b)
    _published_review(region_b)
    db.flush()

    overview = hub_service.hub_overview(db, region_a)
    assert overview.review_count == 1
    for post in overview.popular_reviews:
        assert post.region_id == region_a.id


# ---------------------------------------------------------------------------
# 6. hub_tab_posts — pagination
# ---------------------------------------------------------------------------


def test_hub_tab_posts_pagination(db: Session) -> None:
    """Page 1 must have PAGE_SIZE posts; page 2 must have the remainder."""
    region = RegionFactory(slug="hub-tab-pagination")

    for _ in range(22):
        _published_review(region)
    db.flush()

    posts_p1, total_p1 = hub_service.hub_tab_posts(
        db, region, PostType.REVIEW, page=1
    )
    posts_p2, total_p2 = hub_service.hub_tab_posts(
        db, region, PostType.REVIEW, page=2
    )

    assert total_p1 == total_p2  # same total
    assert total_p1 >= 22
    assert len(posts_p1) == hub_service.PAGE_SIZE
    assert len(posts_p2) >= 2

    p1_ids = {p.id for p in posts_p1}
    p2_ids = {p.id for p in posts_p2}
    assert p1_ids.isdisjoint(p2_ids)


# ---------------------------------------------------------------------------
# 7. hub_tab_posts — sort=popular
# ---------------------------------------------------------------------------


def test_hub_tab_posts_sort_popular_orders_by_view_count(db: Session) -> None:
    """sort='popular' must return the highest-view post first."""
    region = RegionFactory(slug="hub-tab-popular")

    _published_review(region, view_count=1)
    high = _published_review(region, view_count=777)
    _published_review(region, view_count=200)
    db.flush()

    posts, total = hub_service.hub_tab_posts(
        db, region, PostType.REVIEW, sort="popular"
    )
    assert total >= 3
    assert posts[0].id == high.id


# ---------------------------------------------------------------------------
# 8. hub_tab_posts — excludes DRAFT and soft-deleted
# ---------------------------------------------------------------------------


def test_hub_tab_posts_excludes_draft_and_deleted(db: Session) -> None:
    """DRAFT and soft-deleted posts must never appear in hub_tab_posts."""
    region = RegionFactory(slug="hub-tab-exclusion")

    published = _published_review(region)

    # DRAFT
    ReviewPostFactory(status=PostStatus.DRAFT, region=region)

    # Soft-deleted published post
    ReviewPostFactory(
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        deleted_at=datetime.now(UTC),
        region=region,
    )
    db.flush()

    posts, total = hub_service.hub_tab_posts(db, region, PostType.REVIEW)
    assert total == 1
    assert posts[0].id == published.id


# ---------------------------------------------------------------------------
# 9. region_neighbors — only RESIDENT / EX_RESIDENT; capped; other region excluded
# ---------------------------------------------------------------------------


def test_region_neighbors_returns_resident_and_ex_resident_only(db: Session) -> None:
    """INTERESTED users and users from other regions must not be in results."""
    region = RegionFactory(slug="hub-neighbors")
    other_region = RegionFactory(slug="hub-neighbors-other")

    resident = ResidentUserFactory(primary_region_id=region.id)
    ex_resident = UserFactory(
        badge_level=BadgeLevel.EX_RESIDENT,
        primary_region_id=region.id,
    )

    # INTERESTED in same region — must be excluded
    UserFactory(badge_level=BadgeLevel.INTERESTED, primary_region_id=region.id)

    # RESIDENT in different region — must be excluded
    ResidentUserFactory(primary_region_id=other_region.id)

    db.flush()

    neighbors = hub_service.region_neighbors(db, region)
    neighbor_ids = {u.id for u in neighbors}

    assert resident.id in neighbor_ids
    assert ex_resident.id in neighbor_ids
    # Both non-qualifying users excluded
    assert len(neighbors) == 2
