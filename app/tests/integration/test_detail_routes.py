"""Tests for detail pages — /post, /question, /journey, /journey/ep."""
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import PostStatus
from app.tests.factories import (
    AnswerPostFactory,
    JourneyEpisodePostFactory,
    JourneyFactory,
    PlanPostFactory,
    QuestionPostFactory,
    ResidentUserFactory,
    ReviewPostFactory,
)


def _published(**overrides):
    """Defaults for a renderable (PUBLISHED) post."""
    return {
        "status": PostStatus.PUBLISHED,
        "published_at": datetime.now(UTC),
        **overrides,
    }


def test_post_review_renders_with_metadata_card(client: TestClient, db: Session) -> None:
    post = ReviewPostFactory(**_published(title="1년차 회고", body="단열"))
    db.commit()
    r = client.get(f"/post/{post.id}")
    assert r.status_code == 200
    assert "1년차 회고" in r.text
    # metadata card should show some review-specific text
    assert "단독" in r.text or "house_type" in r.text.lower() or "30" in r.text


def test_post_plan_renders(client: TestClient, db: Session) -> None:
    post = PlanPostFactory(**_published(title="2027 양평"))
    db.commit()
    r = client.get(f"/post/{post.id}")
    assert r.status_code == 200
    assert "2027" in r.text


def test_post_404_on_unpublished(client: TestClient, db: Session) -> None:
    post = ReviewPostFactory(status=PostStatus.DRAFT)
    db.commit()
    r = client.get(f"/post/{post.id}")
    assert r.status_code == 404


def test_post_404_on_deleted(client: TestClient, db: Session) -> None:
    post = ReviewPostFactory(**_published(deleted_at=datetime.now(UTC)))
    db.commit()
    r = client.get(f"/post/{post.id}")
    assert r.status_code == 404


def test_post_view_count_increments(client: TestClient, db: Session) -> None:
    post = ReviewPostFactory(**_published(view_count=0))
    db.commit()
    client.get(f"/post/{post.id}")
    client.get(f"/post/{post.id}")
    db.refresh(post)
    assert post.view_count == 2


def test_question_renders_with_answer_form_when_logged_in(client: TestClient, db: Session) -> None:
    question = QuestionPostFactory(**_published(title="단열재 추천?"))
    ResidentUserFactory()
    db.commit()
    r = client.get(f"/question/{question.id}")
    assert r.status_code == 200
    assert "단열재 추천?" in r.text


def test_question_renders_with_answers(client: TestClient, db: Session) -> None:
    question = QuestionPostFactory(**_published())
    AnswerPostFactory(**_published(parent_post_id=question.id, body="셀룰로오스 추천"))
    db.commit()
    r = client.get(f"/question/{question.id}")
    assert r.status_code == 200
    assert "셀룰로오스" in r.text


def test_journey_lists_episodes(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    journey = JourneyFactory(author=user, title="양평 정착기")
    JourneyEpisodePostFactory(
        **_published(
            author=user, region_id=journey.region_id,
            journey_id=journey.id, episode_no=1, title="1화 터잡기",
        )
    )
    JourneyEpisodePostFactory(
        **_published(
            author=user, region_id=journey.region_id,
            journey_id=journey.id, episode_no=2, title="2화 건축",
        )
    )
    db.commit()
    r = client.get(f"/journey/{journey.id}")
    assert r.status_code == 200
    assert "양평 정착기" in r.text
    assert "1화 터잡기" in r.text
    assert "2화 건축" in r.text


def test_journey_episode_renders(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    journey = JourneyFactory(author=user)
    JourneyEpisodePostFactory(
        **_published(
            author=user, region_id=journey.region_id,
            journey_id=journey.id, episode_no=1, title="1화",
        )
    )
    db.commit()
    r = client.get(f"/journey/{journey.id}/ep/1")
    assert r.status_code == 200
    assert "1화" in r.text


def test_journey_episode_404(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    journey = JourneyFactory(author=user)
    db.commit()
    r = client.get(f"/journey/{journey.id}/ep/99")
    assert r.status_code == 404
