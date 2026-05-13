"""Integration tests for home_data and global_feed services.

Covers:
- recommended_regions ordered by is_pilot DESC, id ASC
- popular_reviews ordered by view_count DESC
- global_feed pagination (page 1 = 20, page 2 = remainder)
- global_feed ordered by published_at DESC
- global_feed excludes DRAFT and soft-deleted posts
- home_mixed_feed scoring / diversity / filtering
- region_activity_summary counts and ordering

NOTE: Tests 1/4/5/6 (recent_journeys, followed_episodes) were removed in
      perf(feed) commit — those HomeData fields no longer exist.

NOTE: These tests require a running Postgres instance.
      They CANNOT be executed on a no-Docker PC — run on docker-up PC.
"""
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models._enums import PostStatus, PostType
from app.services import feed as feed_service
from app.services.feed import RegionActivity, home_mixed_feed, region_activity_summary
from app.tests.factories import (
    JourneyEpisodePostFactory,
    JourneyFactory,
    PilotRegionFactory,
    QuestionPostFactory,
    RegionFactory,
    ReviewPostFactory,
    UserFactory,
    UserInterestRegionFactory,
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


# ---------------------------------------------------------------------------
# 10. featured_testimonial — popular_reviews[0] 와 일치
# ---------------------------------------------------------------------------


def test_home_data_featured_testimonial_matches_popular_reviews_first(
    db: Session,
) -> None:
    """featured_testimonial은 popular_reviews[0] (가장 인기 review) 과 동일 instance."""
    region = RegionFactory(slug="feed-featured-match")
    _published_review(region, view_count=10)
    top = _published_review(region, view_count=999)
    _published_review(region, view_count=50)
    db.flush()

    data = feed_service.home_data(db, None)
    assert data.popular_reviews[0].id == top.id
    assert data.featured_testimonial is not None
    assert data.featured_testimonial.id == top.id


# ---------------------------------------------------------------------------
# 11. featured_testimonial — published review 0건이면 None
# ---------------------------------------------------------------------------


def test_home_data_featured_testimonial_none_when_no_reviews(db: Session) -> None:
    """published REVIEW가 하나도 없으면 featured_testimonial == None."""
    # 어떤 region·user도 추가하지 않음. _cleanup_db autouse fixture 가 비움.
    data = feed_service.home_data(db, None)
    assert data.popular_reviews == []
    assert data.featured_testimonial is None


# ---------------------------------------------------------------------------
# 12. RegionActivity — region_activity_summary
# ---------------------------------------------------------------------------


def test_region_activity_counts_within_7d_window(db: Session) -> None:
    """RegionActivity는 7일 내 published review·question을 카운트한다."""
    region = RegionFactory(slug="ra-region")
    now = datetime.now(UTC)
    # 7일 내 — 카운트
    _published_review(region, published_at=now - timedelta(days=1))
    _published_review(region, published_at=now - timedelta(days=6))
    QuestionPostFactory(
        region=region, status=PostStatus.PUBLISHED, published_at=now - timedelta(days=2)
    )
    # 7일 밖 — 제외
    _published_review(region, published_at=now - timedelta(days=8))
    # DRAFT — 제외
    ReviewPostFactory(region=region, status=PostStatus.DRAFT)
    db.flush()

    result = region_activity_summary(db, [region])
    assert len(result) == 1
    assert isinstance(result[0], RegionActivity)
    assert result[0].region.id == region.id
    assert result[0].new_reviews_7d == 2
    assert result[0].new_questions_7d == 1


def test_region_activity_returns_zero_for_inactive_region(db: Session) -> None:
    """활동 없는 시군은 카운터 0/0으로 반환."""
    region = RegionFactory(slug="ra-quiet")
    db.flush()
    result = region_activity_summary(db, [region])
    assert result[0].new_reviews_7d == 0
    assert result[0].new_questions_7d == 0


def test_region_activity_preserves_input_order(db: Session) -> None:
    """입력 region 순서 그대로 RegionActivity를 반환."""
    r1 = RegionFactory(slug="ra-a")
    r2 = RegionFactory(slug="ra-b")
    r3 = RegionFactory(slug="ra-c")
    db.flush()
    result = region_activity_summary(db, [r2, r3, r1])
    assert [ra.region.id for ra in result] == [r2.id, r3.id, r1.id]


# ---------------------------------------------------------------------------
# 13. home_mixed_feed — limit 준수
# ---------------------------------------------------------------------------


def test_home_mixed_feed_returns_max_limit(db: Session) -> None:
    """후보가 충분할 때 limit 개수까지만 반환."""
    user = UserFactory()
    region = RegionFactory(slug="mf-region")
    for i in range(15):
        _published_review(region, view_count=i)
    db.flush()
    feed = home_mixed_feed(db, user, limit=8)
    assert len(feed) == 8


# ---------------------------------------------------------------------------
# 14. home_mixed_feed — 3가지 타입 혼합
# ---------------------------------------------------------------------------


def test_home_mixed_feed_includes_all_three_types(db: Session) -> None:
    """review + journey_episode + question을 혼합한다."""
    user = UserFactory()
    region = RegionFactory(slug="mf-types")
    journey = JourneyFactory(author=user, region=region)
    for _ in range(3):
        _published_review(region)
    for _ in range(3):
        _published_episode(region, journey)
    for _ in range(3):
        QuestionPostFactory(
            region=region, status=PostStatus.PUBLISHED,
            published_at=datetime.now(UTC),
        )
    db.flush()
    feed = home_mixed_feed(db, user, limit=9)
    types = {p.type for p in feed}
    assert PostType.REVIEW in types
    assert PostType.JOURNEY_EPISODE in types
    assert PostType.QUESTION in types


# ---------------------------------------------------------------------------
# 15. home_mixed_feed — 팔로우 journey 부스트
# ---------------------------------------------------------------------------


def test_home_mixed_feed_boosts_followed_journey(db: Session) -> None:
    """팔로우 중인 journey의 ep가 비-팔로우 동시점 ep보다 상위."""
    user = UserFactory()
    region = RegionFactory(slug="mf-follow")
    same_published = datetime.now(UTC) - timedelta(days=3)
    followed_j = JourneyFactory(author=UserFactory(), region=region, title="팔로우저니")
    other_j = JourneyFactory(author=UserFactory(), region=region, title="다른저니")
    followed_ep = _published_episode(
        region, followed_j, published_at=same_published, title="팔로우에피"
    )
    other_ep = _published_episode(
        region, other_j, published_at=same_published, title="비팔로우에피"
    )
    add_journey_follow(db, user, followed_j)
    db.flush()

    feed = home_mixed_feed(db, user, limit=8)
    followed_idx = next(i for i, p in enumerate(feed) if p.id == followed_ep.id)
    other_idx = next(i for i, p in enumerate(feed) if p.id == other_ep.id)
    assert followed_idx < other_idx


# ---------------------------------------------------------------------------
# 16. home_mixed_feed — 관심 시군 부스트
# ---------------------------------------------------------------------------


def test_home_mixed_feed_boosts_interest_region(db: Session) -> None:
    """관심 시군 post가 비-관심 시군 동시점 post보다 상위."""
    user = UserFactory()
    interest_region = RegionFactory(slug="mf-interest")
    other_region = RegionFactory(slug="mf-other")
    same_published = datetime.now(UTC) - timedelta(days=3)
    interest_post = _published_review(
        interest_region, published_at=same_published, title="관심후기"
    )
    other_post = _published_review(
        other_region, published_at=same_published, title="비관심후기"
    )
    UserInterestRegionFactory(user=user, region=interest_region)
    db.flush()

    feed = home_mixed_feed(db, user, limit=8)
    interest_idx = next(i for i, p in enumerate(feed) if p.id == interest_post.id)
    other_idx = next(i for i, p in enumerate(feed) if p.id == other_post.id)
    assert interest_idx < other_idx


# ---------------------------------------------------------------------------
# 17. home_mixed_feed — DRAFT·삭제 제외
# ---------------------------------------------------------------------------


def test_home_mixed_feed_excludes_draft_and_deleted(db: Session) -> None:
    user = UserFactory()
    region = RegionFactory(slug="mf-excl")
    ReviewPostFactory(region=region, status=PostStatus.DRAFT, title="드래프트")
    _published_review(region, title="삭제됨").deleted_at = datetime.now(UTC)
    _published_review(region, title="공개")
    db.flush()
    feed = home_mixed_feed(db, user, limit=8)
    titles = {p.title for p in feed}
    assert "공개" in titles
    assert "드래프트" not in titles
    assert "삭제됨" not in titles


# ---------------------------------------------------------------------------
# 18. home_mixed_feed — 콘텐츠 없을 때 빈 리스트
# ---------------------------------------------------------------------------


def test_home_mixed_feed_empty_when_no_content(db: Session) -> None:
    user = UserFactory()
    db.flush()
    assert home_mixed_feed(db, user, limit=8) == []


# ---------------------------------------------------------------------------
# 19. home_mixed_feed — 14일 윈도 밖 post 제외
# ---------------------------------------------------------------------------


def test_home_mixed_feed_excludes_old_posts(db: Session) -> None:
    """14일 윈도 밖 post는 후보 제외."""
    user = UserFactory()
    region = RegionFactory(slug="mf-old")
    old = _published_review(
        region, published_at=datetime.now(UTC) - timedelta(days=20), title="옛글"
    )
    recent = _published_review(
        region, published_at=datetime.now(UTC) - timedelta(days=1), title="새글"
    )
    db.flush()
    feed = home_mixed_feed(db, user, limit=8)
    ids = {p.id for p in feed}
    assert recent.id in ids
    assert old.id not in ids


# ---------------------------------------------------------------------------
# 20. home_data — mixed_feed (로그인 사용자)
# ---------------------------------------------------------------------------


def test_home_data_includes_mixed_feed_for_logged_in(db: Session) -> None:
    user = UserFactory()
    region = RegionFactory(slug="hd-region")
    _published_review(region, title="피드후기")
    db.flush()
    data = feed_service.home_data(db, user)
    assert len(data.mixed_feed) >= 1
    assert any(p.title == "피드후기" for p in data.mixed_feed)


# ---------------------------------------------------------------------------
# 21. home_data — mixed_feed 비로그인 시 빈 리스트
# ---------------------------------------------------------------------------


def test_home_data_empty_mixed_feed_for_anon(db: Session) -> None:
    region = RegionFactory(slug="hd-anon")
    _published_review(region)
    db.flush()
    data = feed_service.home_data(db, None)
    assert data.mixed_feed == []


# ---------------------------------------------------------------------------
# 22. home_data — region_activity 와 recommended_regions 1:1 정렬 일치
# ---------------------------------------------------------------------------


def test_home_data_region_activity_aligned_with_recommended(db: Session) -> None:
    """region_activity와 recommended_regions의 길이·순서가 일치.

    region_activity는 로그인 사용자에게만 계산된다 (anon → []).
    """
    user = UserFactory()
    PilotRegionFactory(slug="hd-r1")
    PilotRegionFactory(slug="hd-r2")
    db.flush()
    data = feed_service.home_data(db, user)
    assert len(data.region_activity) == len(data.recommended_regions)
    for ra, region in zip(data.region_activity, data.recommended_regions, strict=True):
        assert ra.region.id == region.id


# ---------------------------------------------------------------------------
# 23. home_data — UserInterestRegion 있으면 recommended_regions 상위 우선
# ---------------------------------------------------------------------------


def test_home_data_prefers_user_interest_regions(db: Session) -> None:
    """로그인 시 UserInterestRegion이 있으면 recommended_regions 상위에 포함."""
    user = UserFactory()
    interest = RegionFactory(slug="hd-interest", is_pilot=False, sigungu="관심시군")
    # pilot region은 default 정렬상 우선이지만, interest region이 더 상위여야 함
    PilotRegionFactory(slug="hd-pilot-1")
    UserInterestRegionFactory(user=user, region=interest)
    db.flush()
    data = feed_service.home_data(db, user)
    assert data.recommended_regions[0].id == interest.id
