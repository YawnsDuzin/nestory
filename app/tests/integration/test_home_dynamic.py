"""Home `/` route renders dynamic data from feed_service.home_data."""
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import PostStatus
from app.tests.factories import (
    JourneyEpisodePostFactory,
    JourneyFactory,
    PilotRegionFactory,
    RegionFactory,
    ResidentUserFactory,
    ReviewPostFactory,
    add_journey_follow,
)


def test_home_anonymous_renders_recommended_regions(client: TestClient, db: Session) -> None:
    PilotRegionFactory(slug="rec-region-1", sigungu="추천양평")
    PilotRegionFactory(slug="rec-region-2", sigungu="추천홍천")
    db.commit()
    r = client.get("/")
    assert r.status_code == 200
    assert "추천양평" in r.text
    assert "추천홍천" in r.text


def test_home_anonymous_renders_popular_reviews(client: TestClient, db: Session) -> None:
    """상위 3개는 hero 캐러셀 슬라이드, 4번째부터는 '인기 후기' 그리드에 노출."""
    region = PilotRegionFactory(slug="rec-pop-region")
    user = ResidentUserFactory()
    # 1순위 — hero 캐러셀 첫 슬라이드. 첫 단락이 인용에 노출.
    ReviewPostFactory(
        author=user, region=region, title="홈인기리뷰페이처드",
        body="featured 인용 카드에 들어갈 본문입니다.",
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC), view_count=999,
    )
    # 2~4순위 채워서 그리드에 노출될 4번째 post 확보
    for i in range(3):
        ReviewPostFactory(
            author=user, region=region, title=f"홈인기리뷰{i}",
            status=PostStatus.PUBLISHED,
            published_at=datetime.now(UTC), view_count=500 - i,
        )
    # 5순위 — 인기 후기 그리드 카드에 노출. 카드는 제목/본문 머리를 표시.
    ReviewPostFactory(
        author=user, region=region, title="홈인기리뷰그리드",
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC), view_count=100,
    )
    db.commit()
    r = client.get("/")
    assert r.status_code == 200
    # 5순위 review의 title이 "인기 후기" 그리드 카드에 표시
    assert "홈인기리뷰그리드" in r.text
    # 1순위 review의 첫 단락이 hero 캐러셀 슬라이드에 표시
    assert "featured 인용 카드에 들어갈 본문입니다" in r.text


def test_home_logged_in_user_sees_followed_journey_episodes(
    client: TestClient, db: Session, login
) -> None:
    region = RegionFactory(slug="follow-region")
    user = ResidentUserFactory()
    journey = JourneyFactory(author=user, region=region, title="팔로우저니홈테스트")
    JourneyEpisodePostFactory(
        journey=journey, author=user, region=region,
        episode_no=1, title="홈팔로우에피소드",
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
    )
    add_journey_follow(db, user, journey)
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200
    assert "홈팔로우에피소드" in r.text


def test_home_logged_in_user_with_no_follows_renders_without_error(
    client: TestClient, db: Session, login
) -> None:
    user = ResidentUserFactory()
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200


def test_home_anonymous_user_marketing_sections_still_render(
    client: TestClient, db: Session
) -> None:
    """4 Pillar / Persona / Bottom CTA should still appear for anonymous users."""
    r = client.get("/")
    assert r.status_code == 200
    assert "Nestory가 다른 이유" in r.text  # 4 Pillar heading
    assert "당신은 어떤 분이신가요?" in r.text  # Persona heading


def test_home_logged_in_shows_mixed_feed_section(
    client: TestClient, db: Session, login
) -> None:
    """로그인 + 시드 → '오늘의 발견' 섹션 + 카드 노출."""
    user = ResidentUserFactory()
    region = RegionFactory(slug="hd-mf")
    ReviewPostFactory(
        region=region, status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC), title="펄스피드후기카드",
    )
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200
    assert "오늘의 발견" in r.text
    assert "펄스피드후기카드" in r.text


def test_home_logged_in_empty_state_when_no_content(
    client: TestClient, db: Session, login
) -> None:
    """후보 0개 → empty state CTA 노출."""
    user = ResidentUserFactory()
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200
    assert "아직 추천할 콘텐츠가 없어요" in r.text


def test_home_logged_in_renders_fab(
    client: TestClient, db: Session, login
) -> None:
    """FAB 버튼 + 4 entry link 노출."""
    user = ResidentUserFactory()
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200
    assert 'aria-label="쓰기 메뉴 열기"' in r.text
    assert "/write/review" in r.text
    assert "/write/journey" in r.text
    assert "/write/question" in r.text
    assert "/write/plan" in r.text


def test_home_anonymous_no_fab(client: TestClient, db: Session) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert 'aria-label="쓰기 메뉴 열기"' not in r.text


def test_home_region_activity_card_shows_counters(
    client: TestClient, db: Session, login
) -> None:
    """시군 카드에 주간 카운터 라벨이 보인다."""
    user = ResidentUserFactory()
    region = PilotRegionFactory(slug="hd-ra", sigungu="활동시군")
    ReviewPostFactory(
        region=region, status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC) - timedelta(days=1), title="활동시군주간",
    )
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200
    assert "활동시군" in r.text
    assert "이번 주" in r.text
    assert "새 후기" in r.text


# ---------------------------------------------------------------------------
# 2026-05-14 Home Visual Uplift — Hero / Quick Write / Region Spotlight
# ---------------------------------------------------------------------------


def test_home_hero_card_shows_user_stats(
    client: TestClient, db: Session, login
) -> None:
    """로그인 시 hero status card에 회고/계획/답변 stat 라벨 노출."""
    user = ResidentUserFactory()
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200
    assert "회고" in r.text
    assert "정착계획" in r.text
    assert "답변" in r.text


def test_home_quick_write_4_cards_logged_in(
    client: TestClient, db: Session, login
) -> None:
    """B) Quick Write 4-카드 entry가 본문에 노출."""
    user = ResidentUserFactory()
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200
    # 4-카드 텍스트 (FAB과 별개 — 본문 시각 entry)
    assert "후기 작성" in r.text
    assert "Journey 시작" in r.text
    assert "질문하기" in r.text
    assert "정착 계획" in r.text


def test_home_quick_write_locks_resident_only_for_non_resident(
    client: TestClient, db: Session, login
) -> None:
    """거주자 미인증자에겐 후기/Journey quick-write 카드에 lock 마커."""
    from app.tests.factories import RegionVerifiedUserFactory
    user = RegionVerifiedUserFactory()
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200
    # quick_write 카드의 lock 마커
    assert "🔒 거주자" in r.text


def test_home_region_spotlight_chip(
    client: TestClient, db: Session, login
) -> None:
    """첫 시군은 spotlight 카드로 노출 — '내 시군' chip + '허브 보기' CTA."""
    user = ResidentUserFactory()
    region = PilotRegionFactory(slug="hd-spot", sigungu="스포트시군")
    ReviewPostFactory(
        region=region, status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC) - timedelta(days=1),
    )
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200
    assert "내 시군" in r.text
    assert "스포트시군" in r.text
    assert "허브 보기" in r.text


def test_home_post_card_review_shows_regret_chip(
    client: TestClient, db: Session, login
) -> None:
    """D) review post에 regret_items가 있으면 '후회 N건' chip 노출."""
    user = ResidentUserFactory()
    region = RegionFactory(slug="hd-regret")
    review = ReviewPostFactory(
        region=region, status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC), title="후회카드테스트",
    )
    # PostFactory의 기본 metadata는 type별 valid 메타. regret_items를 직접 주입.
    review.metadata_ = {
        **(review.metadata_ or {}),
        "regret_items": [
            {"category": "design", "cost_krw_band": "100-500", "time_months_band": "1-3"},
            {"category": "build", "cost_krw_band": "500-2000", "time_months_band": "3-6"},
        ],
    }
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200
    assert "후회카드테스트" in r.text
    assert "후회 2건" in r.text
