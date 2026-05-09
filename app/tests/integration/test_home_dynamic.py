"""Home `/` route renders dynamic data from feed_service.home_data."""
from datetime import UTC, datetime

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
    region = PilotRegionFactory(slug="rec-pop-region")
    user = ResidentUserFactory()
    ReviewPostFactory(
        author=user, region=region, title="홈인기리뷰테스트",
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC), view_count=999,
    )
    db.commit()
    r = client.get("/")
    assert r.status_code == 200
    assert "홈인기리뷰테스트" in r.text


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
