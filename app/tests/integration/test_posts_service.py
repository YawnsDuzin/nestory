"""Tests for posts service — 5 type create + view_count."""
from datetime import date

from sqlalchemy.orm import Session

from app.models import Journey
from app.models._enums import PostStatus, PostType
from app.schemas.post_metadata import (
    JourneyEpisodeMetadata,
    JourneyEpMeta,
    PlanMetadata,
    QuestionMetadata,
    ReviewMetadata,
)
from app.services import posts as posts_service
from app.tests.factories import (
    JourneyFactory,
    QuestionPostFactory,
    RegionFactory,
    ResidentUserFactory,
    UserFactory,
)


def test_create_review(db: Session) -> None:
    author = ResidentUserFactory()
    region = RegionFactory()
    meta = ReviewMetadata(house_type="단독", size_pyeong=30, satisfaction_overall=4)
    post = posts_service.create_review(db, author, region, meta, "1년차 회고", "단열이 가장 후회됨")
    assert post.id is not None
    assert post.type == PostType.REVIEW
    assert post.status == PostStatus.PUBLISHED
    assert post.author_id == author.id
    assert post.region_id == region.id
    assert post.metadata_["house_type"] == "단독"
    assert post.metadata_["satisfaction_overall"] == 4
    assert "type_tag" not in post.metadata_  # discriminator stays in column, not JSONB


def test_create_journey(db: Session) -> None:
    author = ResidentUserFactory()
    region = RegionFactory()
    j = posts_service.create_journey(
        db, author, region, "양평 정착기", "터잡기부터", date(2026, 1, 1),
    )
    assert j.id is not None
    assert isinstance(j, Journey)
    assert j.author_id == author.id
    assert j.region_id == region.id
    assert j.start_date == date(2026, 1, 1)


def test_create_journey_episode_auto_episode_no(db: Session) -> None:
    author = ResidentUserFactory()
    journey = JourneyFactory(author=author)
    meta = JourneyEpisodeMetadata(
        journey_ep_meta=JourneyEpMeta(phase="입주", period_label="2026-04"),
    )
    ep1 = posts_service.create_journey_episode(db, author, journey, meta, "1화", "본문 1")
    ep2 = posts_service.create_journey_episode(db, author, journey, meta, "2화", "본문 2")
    assert ep1.episode_no == 1
    assert ep2.episode_no == 2
    assert ep1.journey_id == journey.id == ep2.journey_id


def test_create_question(db: Session) -> None:
    author = UserFactory()
    region = RegionFactory()
    meta = QuestionMetadata(tags=["단열", "지붕"])
    q = posts_service.create_question(
        db, author, region, meta, "단열재 추천?", "양평 동향 단독, 추천 부탁",
    )
    assert q.type == PostType.QUESTION
    assert q.metadata_["tags"] == ["단열", "지붕"]


def test_create_answer_inherits_region(db: Session) -> None:
    author = UserFactory()
    question = QuestionPostFactory()
    a = posts_service.create_answer(db, author, question, "셀룰로오스가 가성비 좋습니다")
    assert a.type == PostType.ANSWER
    assert a.parent_post_id == question.id
    assert a.region_id == question.region_id


def test_create_plan(db: Session) -> None:
    author = UserFactory()
    region = RegionFactory()
    meta = PlanMetadata(target_move_year=2027, budget_total_manwon_band="5000-10000",
                        construction_intent="undecided")
    p = posts_service.create_plan(db, author, region, meta, "2027 양평 입주 계획", "검토 중")
    assert p.type == PostType.PLAN
    assert p.metadata_["target_move_year"] == 2027


def test_increment_view_count(db: Session) -> None:
    post = QuestionPostFactory(view_count=0)
    posts_service.increment_view_count(db, post)
    posts_service.increment_view_count(db, post)
    db.refresh(post)
    assert post.view_count == 2
