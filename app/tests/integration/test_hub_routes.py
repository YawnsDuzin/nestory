"""Integration tests for /hub/{slug} routes — home + 4 tab pages.

Tests:
- test_hub_home_returns_200_with_overview_data
- test_hub_home_unknown_slug_returns_404
- test_hub_reviews_tab_returns_200
- test_hub_journeys_tab_returns_200
- test_hub_questions_tab_returns_200
- test_hub_neighbors_tab_returns_200_with_residents
- test_hub_neighbors_excludes_interested_users
- test_hub_isolates_regions
- test_hub_pagination_query_param
- test_hub_sort_query_param_popular

NOTE: Requires a running Postgres instance.
      Cannot be executed on a no-Docker PC — run on docker-up PC.
"""
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import PostStatus
from app.models.user import BadgeLevel
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


def _published_review(region, **kwargs):
    return ReviewPostFactory(
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        region=region,
        **kwargs,
    )


def _published_journey_ep(region, **kwargs):
    return JourneyEpisodePostFactory(
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        region=region,
        **kwargs,
    )


def _published_question(region, **kwargs):
    return QuestionPostFactory(
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        region=region,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# hub home
# ---------------------------------------------------------------------------


def test_hub_home_returns_200_with_overview_data(
    client: TestClient, db: Session
) -> None:
    """GET /hub/{slug} returns 200 and shows region name + post titles."""
    region = PilotRegionFactory(slug="test-hub-home", sigungu="양평군")
    _published_review(region, title="양평 후기 제목")
    _published_journey_ep(region, title="양평 Journey 제목")
    _published_question(region, title="양평 질문 제목")
    db.commit()

    r = client.get(f"/hub/{region.slug}")
    assert r.status_code == 200
    assert region.sigungu in r.text
    assert "양평 후기 제목" in r.text
    assert "양평 Journey 제목" in r.text
    assert "양평 질문 제목" in r.text


def test_hub_home_unknown_slug_returns_404(client: TestClient, db: Session) -> None:
    """GET /hub/no-such-slug must return 404."""
    r = client.get("/hub/no-such-slug-xyz")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Tab pages — basic 200 check
# ---------------------------------------------------------------------------


def test_hub_reviews_tab_returns_200(client: TestClient, db: Session) -> None:
    """GET /hub/{slug}/reviews returns 200."""
    region = RegionFactory(slug="test-hub-reviews", sigungu="가평군")
    _published_review(region, title="가평 후기")
    db.commit()

    r = client.get(f"/hub/{region.slug}/reviews")
    assert r.status_code == 200
    assert "가평 후기" in r.text


def test_hub_journeys_tab_returns_200(client: TestClient, db: Session) -> None:
    """GET /hub/{slug}/journeys returns 200."""
    region = RegionFactory(slug="test-hub-journeys", sigungu="춘천시")
    _published_journey_ep(region, title="춘천 Journey")
    db.commit()

    r = client.get(f"/hub/{region.slug}/journeys")
    assert r.status_code == 200
    assert "춘천 Journey" in r.text


def test_hub_questions_tab_returns_200(client: TestClient, db: Session) -> None:
    """GET /hub/{slug}/questions returns 200."""
    region = RegionFactory(slug="test-hub-questions", sigungu="홍천군")
    _published_question(region, title="홍천 질문")
    db.commit()

    r = client.get(f"/hub/{region.slug}/questions")
    assert r.status_code == 200
    assert "홍천 질문" in r.text


# ---------------------------------------------------------------------------
# Neighbors tab
# ---------------------------------------------------------------------------


def test_hub_neighbors_tab_returns_200_with_residents(
    client: TestClient, db: Session
) -> None:
    """GET /hub/{slug}/neighbors returns 200 and shows RESIDENT username."""
    region = RegionFactory(slug="test-hub-neighbors", sigungu="고성군")
    resident = ResidentUserFactory(primary_region_id=region.id)
    db.commit()

    r = client.get(f"/hub/{region.slug}/neighbors")
    assert r.status_code == 200
    assert resident.username in r.text


def test_hub_neighbors_excludes_interested_users(
    client: TestClient, db: Session
) -> None:
    """INTERESTED users must not appear on the neighbors tab."""
    region = RegionFactory(slug="test-hub-neighbors-excl", sigungu="인제군")
    interested = UserFactory(
        badge_level=BadgeLevel.INTERESTED,
        primary_region_id=region.id,
    )
    db.commit()

    r = client.get(f"/hub/{region.slug}/neighbors")
    assert r.status_code == 200
    assert interested.username not in r.text


# ---------------------------------------------------------------------------
# Region isolation
# ---------------------------------------------------------------------------


def test_hub_isolates_regions(client: TestClient, db: Session) -> None:
    """Posts from region A must not appear in region B's reviews tab."""
    region_a = RegionFactory(slug="test-hub-iso-a", sigungu="이천시")
    region_b = RegionFactory(slug="test-hub-iso-b", sigungu="여주시")
    _published_review(region_a, title="이천 후기 ONLY_A")
    db.commit()

    r_a = client.get(f"/hub/{region_a.slug}/reviews")
    r_b = client.get(f"/hub/{region_b.slug}/reviews")

    assert r_a.status_code == 200
    assert "ONLY_A" in r_a.text

    assert r_b.status_code == 200
    assert "ONLY_A" not in r_b.text
    # Empty state message should appear for region B
    assert "아직 후기가 없습니다" in r_b.text


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


def test_hub_pagination_query_param(client: TestClient, db: Session) -> None:
    """Page 2 should have fewer cards than page 1 when there are 22 posts."""
    region = RegionFactory(slug="test-hub-pagination", sigungu="수원시")
    for _ in range(22):
        _published_review(region)
    db.commit()

    r1 = client.get(f"/hub/{region.slug}/reviews?page=1")
    r2 = client.get(f"/hub/{region.slug}/reviews?page=2")
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Page 1 has more post-card entries than page 2
    count_p1 = r1.text.count('rounded border bg-white p-4')
    count_p2 = r2.text.count('rounded border bg-white p-4')
    assert count_p1 > count_p2


# ---------------------------------------------------------------------------
# Sort query param
# ---------------------------------------------------------------------------


def test_hub_sort_query_param_popular(client: TestClient, db: Session) -> None:
    """GET /hub/{slug}/reviews?sort=popular returns 200 without error."""
    region = RegionFactory(slug="test-hub-sort-popular", sigungu="성남시")
    _published_review(region, title="인기 후기", view_count=100)
    _published_review(region, title="평범 후기", view_count=1)
    db.commit()

    r = client.get(f"/hub/{region.slug}/reviews?sort=popular")
    assert r.status_code == 200
    # Both titles visible
    assert "인기 후기" in r.text
    assert "평범 후기" in r.text
