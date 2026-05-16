from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models._enums import PostStatus, PostType
from app.tests.factories import (
    AnswerPostFactory,
    JourneyEpisodePostFactory,
    JourneyFactory,
    PlanPostFactory,
    PostFactory,
    QuestionPostFactory,
    ResidentUserFactory,
    ReviewPostFactory,
)


def test_create_review_post_with_metadata(db: Session) -> None:
    p = ReviewPostFactory(
        title="1년차 후기",
        body="단열이 가장 후회됨",
        metadata_={"satisfaction_overall": 4, "regrets": ["단열"]},
    )
    assert p.id is not None
    assert p.status == PostStatus.DRAFT
    assert p.view_count == 0
    assert p.metadata_["satisfaction_overall"] == 4


def test_plan_post_type(db: Session) -> None:
    p = PlanPostFactory(
        title="우리 가족 정착 계획",
        body="2027년 양평 입주 검토",
        metadata_={"target_move_year": 2027, "open_to_advice": True},
    )
    assert p.type == PostType.PLAN


def test_question_with_parent_link(db: Session) -> None:
    q = QuestionPostFactory(title="Q", body="?")
    a = AnswerPostFactory(
        author_id=q.author_id,
        region_id=q.region_id,
        parent_post=q,
        title="A",
        body="!",
    )
    assert a.parent_post_id == q.id


def test_journey_episode_no_unique_constraint(db: Session) -> None:
    """Two episodes with same (journey_id, episode_no) raises IntegrityError.

    Replaces the previous non-unique ix_posts_journey_episode index with a
    UNIQUE constraint to fight the create_journey_episode race (max+1 then
    INSERT).
    """
    user = ResidentUserFactory()
    journey = JourneyFactory(author=user)
    JourneyEpisodePostFactory(
        author=user, region_id=journey.region_id,
        journey_id=journey.id, episode_no=1, title="1화", body="x",
    )
    db.flush()

    # Factory's create() calls db.flush() internally — IntegrityError raises there.
    with pytest.raises(IntegrityError):
        JourneyEpisodePostFactory(
            author=user, region_id=journey.region_id,
            journey_id=journey.id, episode_no=1, title="dup", body="y",
        )
    db.rollback()


def test_journey_episode_no_uniqueness_does_not_block_null_journey(db: Session) -> None:
    """Non-journey posts (journey_id=NULL) can share NULL — Postgres NULL semantics."""
    # Two REVIEW posts both have journey_id=NULL — must not collide
    ReviewPostFactory(title="r1", body="x")
    ReviewPostFactory(title="r2", body="y")
    db.flush()  # no IntegrityError


def test_post_edited_at_defaults_to_none(db: Session) -> None:
    """edited_at은 created/published 시점엔 None — 수정 발생 시에만 세팅."""
    post = PostFactory(type=PostType.QUESTION, status=PostStatus.PUBLISHED)
    db.flush()
    db.refresh(post)
    assert post.edited_at is None


def test_post_edited_at_settable(db: Session) -> None:
    """edited_at은 timezone-aware datetime을 수용해야 한다."""
    post = PostFactory()
    db.flush()
    now = datetime.now(UTC)
    post.edited_at = now
    db.flush()
    db.refresh(post)
    assert post.edited_at == now
