"""P1.4 E2E workflow tests — exercise the full discovery + interaction surface."""
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import PostStatus
from app.tests.factories import (
    JourneyEpisodePostFactory,
    JourneyFactory,
    PilotRegionFactory,
    QuestionPostFactory,
    RegionVerifiedUserFactory,
    ResidentUserFactory,
    ReviewPostFactory,
    UserFactory,
    add_journey_follow,
)


def test_anonymous_discovery_flow(client: TestClient, db: Session) -> None:
    """A visitor lands on /, browses to /discover, picks a hub, opens a tab,
    runs a search, and clicks through to a detail page — all anonymous."""
    region = PilotRegionFactory(slug="e2e-yangpyeong", sigungu="양평군")
    resident = ResidentUserFactory(
        username="e2e-resident",
        primary_region_id=region.id,
    )
    review = ReviewPostFactory(
        author=resident, region=region,
        title="E2E 양평 후기 단열 후회",
        body="단열을 더 두껍게 했어야 했다.",
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        view_count=100,
    )
    db.commit()

    # 1. Home (anonymous)
    r = client.get("/")
    assert r.status_code == 200
    assert "Nestory" in r.text  # marketing landing

    # 2. /discover
    r = client.get("/discover")
    assert r.status_code == 200
    assert region.sigungu in r.text

    # 3. /hub/{slug}
    r = client.get(f"/hub/{region.slug}")
    assert r.status_code == 200
    assert review.title in r.text

    # 4. /hub/{slug}/reviews tab
    r = client.get(f"/hub/{region.slug}/reviews")
    assert r.status_code == 200
    assert review.title in r.text

    # 5. /search
    r = client.get("/search?q=양평")
    assert r.status_code == 200
    # The search form is always rendered; result section may have title
    assert review.title in r.text

    # 6. Click into the review detail
    r = client.get(f"/post/{review.id}")
    assert r.status_code == 200
    assert review.title in r.text


def test_logged_in_interaction_flow(client: TestClient, db: Session, login) -> None:
    """A logged-in user likes a post, scraps another, comments, then verifies
    those interactions appear on detail pages and on /me/scraps."""
    region = PilotRegionFactory(slug="e2e-hongcheon", sigungu="홍천군")
    resident = ResidentUserFactory(
        username="e2e-author",
        primary_region_id=region.id,
    )
    actor = RegionVerifiedUserFactory(
        username="e2e-actor",
        primary_region_id=region.id,
    )
    review = ReviewPostFactory(
        author=resident, region=region,
        title="E2E 홍천 후기 단열",
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
    )
    db.commit()

    login(actor.id)

    # 1. Like the review
    r = client.post(f"/post/{review.id}/like")
    assert r.status_code == 200
    assert "like-btn-" in r.text  # HTMX returned the like button partial

    # 2. Scrap the review
    r = client.post(f"/post/{review.id}/scrap")
    assert r.status_code == 200
    assert "scrap-btn-" in r.text

    # 3. Comment on the review
    r = client.post(
        f"/post/{review.id}/comment",
        data={"body": "정말 도움 됐습니다, 감사합니다!"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/post/{review.id}#comments"

    # 4. Detail page now shows the comment
    r = client.get(f"/post/{review.id}")
    assert r.status_code == 200
    assert "정말 도움 됐습니다" in r.text

    # 5. /u/{username}/scraps — actor sees the scrapped review
    r = client.get(f"/u/{actor.username}/scraps")
    assert r.status_code == 200
    assert review.title in r.text


def test_anonymous_cannot_like_or_comment(client: TestClient, db: Session) -> None:
    """Verify auth gates on interaction routes — anonymous → 401."""
    region = PilotRegionFactory(slug="e2e-anon-region")
    resident = ResidentUserFactory()
    review = ReviewPostFactory(
        author=resident, region=region,
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
    )
    db.commit()

    r = client.post(f"/post/{review.id}/like")
    assert r.status_code == 401

    r = client.post(f"/post/{review.id}/comment", data={"body": "anonymous comment"})
    assert r.status_code == 401


def test_followed_journey_appears_on_home(client: TestClient, db: Session, login) -> None:
    """Logged-in user with a Journey follow sees its new episode on /."""
    region = PilotRegionFactory(slug="e2e-follow-region")
    author = ResidentUserFactory()
    follower = UserFactory()
    journey = JourneyFactory(
        author=author, region=region,
        title="E2E 팔로우 저니",
    )
    JourneyEpisodePostFactory(
        journey=journey, author=author, region=region,
        episode_no=1, title="E2E 팔로우 에피소드 1",
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
    )
    add_journey_follow(db, follower, journey)
    db.commit()

    login(follower.id)
    r = client.get("/")
    assert r.status_code == 200
    assert "E2E 팔로우 에피소드 1" in r.text


def test_search_filter_combinations(client: TestClient, db: Session) -> None:
    """Verify search supports region + type filter combinations."""
    region_a = PilotRegionFactory(slug="e2e-search-a", sigungu="검색A")
    region_b = PilotRegionFactory(slug="e2e-search-b", sigungu="검색B")
    user = ResidentUserFactory()

    review_in_a = ReviewPostFactory(
        author=user, region=region_a,
        title="검색E2E후기A 단열",
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
    )
    question_in_a = QuestionPostFactory(
        author=user, region=region_a,
        title="검색E2E질문A 단열",
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
    )
    review_in_b = ReviewPostFactory(
        author=user, region=region_b,
        title="검색E2E후기B 단열",
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
    )
    db.commit()

    # Region A filter
    r = client.get(f"/search?q=단열&region={region_a.slug}")
    assert r.status_code == 200
    assert review_in_a.title in r.text
    assert question_in_a.title in r.text
    assert review_in_b.title not in r.text

    # Region A + type=review
    r = client.get(f"/search?q=단열&region={region_a.slug}&type=review")
    assert r.status_code == 200
    assert review_in_a.title in r.text
    assert question_in_a.title not in r.text
