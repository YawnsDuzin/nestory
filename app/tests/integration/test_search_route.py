"""Integration tests for /search route — full-text + trgm search with filters.

Tests:
- test_search_empty_query_returns_form_only
- test_search_with_query_returns_matching_post
- test_search_filter_by_region
- test_search_filter_by_type
- test_search_no_results_renders_empty_state
- test_search_xss_in_query_is_escaped
- test_search_invalid_type_param_ignored
- test_search_anonymous_user_works

NOTE: Requires a running Postgres instance with pg_trgm extension.
      Cannot be executed on a no-Docker PC — run on docker-up PC.
"""
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import PostStatus
from app.tests.factories import (
    PilotRegionFactory,
    QuestionPostFactory,
    RegionFactory,
    ReviewPostFactory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _published_review(region=None, **kwargs):
    kw = dict(
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
    )
    if region is not None:
        kw["region"] = region
    kw.update(kwargs)
    return ReviewPostFactory(**kw)


def _published_question(region=None, **kwargs):
    kw = dict(
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
    )
    if region is not None:
        kw["region"] = region
    kw.update(kwargs)
    return QuestionPostFactory(**kw)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_search_empty_query_returns_form_only(
    client: TestClient, db: Session
) -> None:
    """GET /search with no q param renders the form but no result section."""
    r = client.get("/search")
    assert r.status_code == 200
    # Form must be present
    assert '<form' in r.text
    assert 'name="q"' in r.text
    # No result count line (result is None → no result section rendered)
    assert "검색 결과가 없습니다" not in r.text


def test_search_with_query_returns_matching_post(
    client: TestClient, db: Session
) -> None:
    """GET /search?q=양평 returns the post whose title contains '양평'."""
    _published_review(title="양평 단독주택 후기", body="전원생활 1년 후기입니다")
    db.commit()

    r = client.get("/search?q=양평")
    assert r.status_code == 200
    assert "양평 단독주택 후기" in r.text


def test_search_filter_by_region(client: TestClient, db: Session) -> None:
    """GET /search?q=...&region={slug} returns only posts for that region."""
    region_a = PilotRegionFactory(slug="search-region-a", sigungu="양평군")
    region_b = RegionFactory(slug="search-region-b", sigungu="영월군")
    _published_review(region=region_a, title="양평 후기 ONLY_A")
    _published_review(region=region_b, title="영월 후기 ONLY_B")
    db.commit()

    r = client.get(f"/search?q=후기&region={region_a.slug}")
    assert r.status_code == 200
    assert "ONLY_A" in r.text
    assert "ONLY_B" not in r.text


def test_search_filter_by_type(client: TestClient, db: Session) -> None:
    """GET /search?q=...&type=review returns only review posts, not questions."""
    _published_review(title="후기글 REVIEW_MATCH")
    _published_question(title="질문글 QUESTION_MATCH")
    db.commit()

    r = client.get("/search?q=MATCH&type=review")
    assert r.status_code == 200
    assert "REVIEW_MATCH" in r.text
    assert "QUESTION_MATCH" not in r.text


def test_search_no_results_renders_empty_state(
    client: TestClient, db: Session
) -> None:
    """A query that matches nothing shows the empty-state message."""
    db.commit()

    r = client.get("/search?q=존재하지않는쿼리XYZABC")
    assert r.status_code == 200
    assert "검색 결과가 없습니다" in r.text


def test_search_xss_in_query_is_escaped(
    client: TestClient, db: Session
) -> None:
    """XSS payload in ?q must be HTML-escaped — raw <script> must not appear."""
    db.commit()

    r = client.get("/search?q=<script>alert(1)</script>")
    assert r.status_code == 200
    assert "<script>alert(1)</script>" not in r.text


def test_search_invalid_type_param_ignored(
    client: TestClient, db: Session
) -> None:
    """An unknown ?type= value is silently ignored (treated as no type filter)."""
    _published_review(title="타입필터 없음 후기")
    db.commit()

    r = client.get("/search?q=후기&type=invalid_type")
    assert r.status_code == 200
    assert "타입필터 없음 후기" in r.text


def test_search_anonymous_user_works(client: TestClient, db: Session) -> None:
    """GET /search without a session cookie should return 200."""
    _published_review(title="익명 검색 후기")
    db.commit()

    r = client.get("/search?q=익명")
    assert r.status_code == 200
