"""Integration tests for search_posts service.

Covers:
- 한글 부분일치 (e.g. "양평" in body "양평군 동향에 단열")
- 오타 허용 (trgm — "양펑" → "양평" similarity > 0.07)
- region_id 필터 (other region excluded)
- type 필터 (REVIEW only)
- sort=latest / sort=popular / sort=relevance
- page=2 pagination (page 1 full, page 2 partial)
- 빈 쿼리 / 1글자 쿼리 short-circuit (total=0, no DB round-trip)
- DRAFT post 제외
- deleted_at 있는 post 제외
- 다른 region의 post는 region 필터 시 제외

NOTE: These tests require a running Postgres with pg_trgm extension and
      the P1.4 Task 1 GIN indexes applied (migration e1ad6f3c4a92).
      They CANNOT be executed on a no-Docker PC — run on docker-up PC.
"""
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models._enums import PostStatus, PostType
from app.services import search as search_service
from app.tests.factories import (
    QuestionPostFactory,
    RegionFactory,
    ReviewPostFactory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _published_review(title: str, body: str, region, **kwargs):
    """Shorthand: PUBLISHED ReviewPost with explicit title/body/region."""
    kwargs.setdefault("published_at", datetime.now(UTC))
    return ReviewPostFactory(
        title=title,
        body=body,
        status=PostStatus.PUBLISHED,
        region=region,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# 1. 한글 부분일치 — FTS path
# ---------------------------------------------------------------------------


def test_korean_partial_match_fts(db: Session) -> None:
    """"양평" in tsquery should match body "양평군 동향에 단열"."""
    region = RegionFactory()
    _published_review("양평군 1년차 후기", "양평군 동향에 단열이 가장 후회됨", region)
    db.flush()

    result = search_service.search_posts(db, "양평")
    assert result.total >= 1
    titles = [p.title for p in result.posts]
    assert any("양평" in t for t in titles)


# ---------------------------------------------------------------------------
# 2. 오타 허용 — trgm similarity path
# ---------------------------------------------------------------------------


def test_typo_tolerance_trgm(db: Session) -> None:
    """"양펑" is a near-typo of "양평" — trgm similarity should catch it."""
    region = RegionFactory()
    _published_review("양평 이사 후기", "양평에서의 1년, 후회는 없다", region)
    db.flush()

    result = search_service.search_posts(db, "양펑")
    # trgm similarity("양펑", "양평 이사 후기") ≈ 0.09 which is > SIMILARITY_THRESHOLD (0.07)
    # 한국어는 영어보다 trigram 밀도가 낮아 임계값 0.07로 조정 (PRD §6.3 보강)
    assert result.total >= 1


# ---------------------------------------------------------------------------
# 3. region_id 필터
# ---------------------------------------------------------------------------


def test_region_filter_excludes_other_region(db: Session) -> None:
    """With region_id filter, posts in other regions must not appear."""
    region_a = RegionFactory(slug="region-a")
    region_b = RegionFactory(slug="region-b")
    _published_review("양평 후기 A지역", "양평에서 좋은 하루", region_a)
    _published_review("양평 후기 B지역", "양평의 봄, 아름다운 곳", region_b)
    db.flush()

    result = search_service.search_posts(db, "양평", region_id=region_a.id)
    assert result.total >= 1
    for post in result.posts:
        assert post.region_id == region_a.id


# ---------------------------------------------------------------------------
# 4. type 필터
# ---------------------------------------------------------------------------


def test_type_filter_review_only(db: Session) -> None:
    """type=REVIEW filter must exclude QUESTION posts even if they match."""
    region = RegionFactory()
    _published_review("양평 단열 후기", "단열 시공 후기", region)
    QuestionPostFactory(
        title="양평 단열재 추천?",
        body="양평 지역 단열재 추천 부탁드립니다",
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        region=region,
    )
    db.flush()

    result = search_service.search_posts(db, "양평", post_type=PostType.REVIEW)
    assert result.total >= 1
    for post in result.posts:
        assert post.type == PostType.REVIEW


# ---------------------------------------------------------------------------
# 5. 정렬 — latest
# ---------------------------------------------------------------------------


def test_sort_latest(db: Session) -> None:
    """sort=latest must return the most recently published post first."""
    region = RegionFactory()
    _published_review(
        "양평 오래된 글", "단열 후기 오래된",
        region,
        published_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    newer = _published_review(
        "양평 최신 글", "단열 후기 최신",
        region,
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    db.flush()

    result = search_service.search_posts(db, "양평", sort="latest")
    assert result.total >= 2
    # Newest should come first
    assert result.posts[0].id == newer.id


# ---------------------------------------------------------------------------
# 6. 정렬 — popular
# ---------------------------------------------------------------------------


def test_sort_popular(db: Session) -> None:
    """sort=popular must return the post with highest view_count first."""
    region = RegionFactory()
    _published_review("양평 글 조회 낮음", "양평 단열", region, view_count=1)
    high_views = _published_review("양평 글 조회 높음", "양평 단열", region, view_count=999)
    db.flush()

    result = search_service.search_posts(db, "양평", sort="popular")
    assert result.total >= 2
    assert result.posts[0].id == high_views.id


# ---------------------------------------------------------------------------
# 7. 정렬 — relevance (default)
# ---------------------------------------------------------------------------


def test_sort_relevance_default(db: Session) -> None:
    """sort=relevance (default) must return a SearchResult without error."""
    region = RegionFactory()
    _published_review("양평 관련도 테스트", "양평 단열 관련 글", region)
    db.flush()

    result = search_service.search_posts(db, "양평")  # default sort="relevance"
    assert result.total >= 1
    assert isinstance(result.posts[0].title, str)


# ---------------------------------------------------------------------------
# 8. 페이지네이션 — page=2
# ---------------------------------------------------------------------------


def test_pagination_page_2(db: Session) -> None:
    """Page 2 must return posts beyond the first PAGE_SIZE slice."""
    region = RegionFactory()
    # Create 22 posts — enough to fill page 1 (20) and spill into page 2
    for i in range(22):
        _published_review(f"양평 글 {i:02d}", f"양평 단열 본문 {i}", region)
    db.flush()

    page1 = search_service.search_posts(db, "양평", page=1)
    page2 = search_service.search_posts(db, "양평", page=2)

    assert page1.total == page2.total  # same total count
    assert page1.total >= 22
    assert len(page1.posts) == search_service.PAGE_SIZE
    assert len(page2.posts) >= 2  # at least the overflow posts
    # No overlap between pages
    page1_ids = {p.id for p in page1.posts}
    page2_ids = {p.id for p in page2.posts}
    assert page1_ids.isdisjoint(page2_ids)


# ---------------------------------------------------------------------------
# 9. 빈 쿼리 short-circuit
# ---------------------------------------------------------------------------


def test_empty_query_short_circuit(db: Session) -> None:
    """Empty string query must return total=0, no posts, without DB query."""
    result = search_service.search_posts(db, "")
    assert result.total == 0
    assert result.posts == []
    assert result.page == 1


def test_single_char_query_short_circuit(db: Session) -> None:
    """Single-character query is below MIN_QUERY_LEN — must short-circuit."""
    result = search_service.search_posts(db, "a")
    assert result.total == 0
    assert result.posts == []


def test_whitespace_only_query_short_circuit(db: Session) -> None:
    """Whitespace-only query normalizes to "" — must short-circuit."""
    result = search_service.search_posts(db, "   ")
    assert result.total == 0
    assert result.posts == []


# ---------------------------------------------------------------------------
# 10. DRAFT post 제외
# ---------------------------------------------------------------------------


def test_draft_post_excluded(db: Session) -> None:
    """DRAFT posts must never appear in search results."""
    region = RegionFactory()
    ReviewPostFactory(
        title="양평 드래프트 글",
        body="양평에 관한 미발행 글",
        status=PostStatus.DRAFT,
        region=region,
    )
    db.flush()

    result = search_service.search_posts(db, "양평")
    for post in result.posts:
        assert post.status == PostStatus.PUBLISHED


# ---------------------------------------------------------------------------
# 11. deleted_at 있는 post 제외
# ---------------------------------------------------------------------------


def test_soft_deleted_post_excluded(db: Session) -> None:
    """Soft-deleted posts (deleted_at IS NOT NULL) must be excluded."""
    region = RegionFactory()
    ReviewPostFactory(
        title="양평 삭제된 글",
        body="양평 삭제 테스트 본문",
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        deleted_at=datetime.now(UTC),  # soft-deleted
        region=region,
    )
    db.flush()

    result = search_service.search_posts(db, "양평")
    for post in result.posts:
        assert post.deleted_at is None


# ---------------------------------------------------------------------------
# 12. 다른 region 필터 시 제외
# ---------------------------------------------------------------------------


def test_other_region_excluded_with_filter(db: Session) -> None:
    """Only posts matching region_id must be included when filter is applied."""
    region_target = RegionFactory(slug="target-region")
    region_other = RegionFactory(slug="other-region")

    target_post = _published_review("양평 타겟 지역 글", "양평 단열 공사", region_target)
    _published_review("양평 다른 지역 글", "양평 다른 지역 단열", region_other)
    db.flush()

    result = search_service.search_posts(db, "양평", region_id=region_target.id)
    post_ids = [p.id for p in result.posts]
    assert target_post.id in post_ids
    for post in result.posts:
        assert post.region_id == region_target.id
