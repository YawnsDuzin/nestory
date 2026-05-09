"""Integration tests verifying alert rows are created at trigger sites.

Tests:
- test_create_comment_emits_post_comment_to_post_author
- test_create_comment_self_does_not_emit
- test_create_journey_episode_fans_out_to_followers
- test_create_journey_episode_skips_self_follower
- test_create_answer_emits_to_question_author
- test_create_answer_self_does_not_emit

NOTE: Requires running Postgres.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Journey, Notification
from app.models._enums import (
    JourneyStatus,
    NotificationType,
    PostStatus,
)
from app.models.interaction import journey_follows
from app.schemas.post_metadata import (
    JourneyEpisodeMetadata,
)
from app.services.comments import create_comment
from app.services.posts import create_answer, create_journey_episode
from app.tests.factories import (
    QuestionPostFactory,
    RegionFactory,
    ResidentUserFactory,
    ReviewPostFactory,
    UserFactory,
)


def _notif_for(db: Session, user_id: int) -> list[Notification]:
    return list(
        db.scalars(
            select(Notification).where(Notification.user_id == user_id)
        ).all()
    )


def test_create_comment_emits_post_comment_to_post_author(db: Session) -> None:
    author = UserFactory()
    commenter = UserFactory()
    post = ReviewPostFactory(author=author, status=PostStatus.PUBLISHED)
    db.flush()
    create_comment(db, post, commenter, "좋은 글 잘 봤습니다")
    notifs = _notif_for(db, author.id)
    assert len(notifs) == 1
    n = notifs[0]
    assert n.type == NotificationType.POST_COMMENT
    assert n.source_user_id == commenter.id
    assert n.target_type == "post"
    assert n.target_id == post.id


def test_create_comment_self_does_not_emit(db: Session) -> None:
    author = UserFactory()
    post = ReviewPostFactory(author=author, status=PostStatus.PUBLISHED)
    db.flush()
    create_comment(db, post, author, "내 글에 댓글")
    assert _notif_for(db, author.id) == []


def test_create_journey_episode_fans_out_to_followers(db: Session) -> None:
    author = ResidentUserFactory()
    region = RegionFactory()
    follower_a = UserFactory()
    follower_b = UserFactory()
    journey = Journey(
        author_id=author.id,
        region_id=region.id,
        title="My Journey",
        slug="my-journey",
        status=JourneyStatus.IN_PROGRESS,
    )
    db.add(journey)
    db.flush()
    db.execute(
        journey_follows.insert(),
        [
            {"user_id": follower_a.id, "journey_id": journey.id},
            {"user_id": follower_b.id, "journey_id": journey.id},
        ],
    )
    db.flush()

    create_journey_episode(
        db,
        author=author,
        journey=journey,
        payload=JourneyEpisodeMetadata(),
        title="Episode 1",
        body="첫 회차",
    )
    assert len(_notif_for(db, follower_a.id)) == 1
    assert len(_notif_for(db, follower_b.id)) == 1
    a_notif = _notif_for(db, follower_a.id)[0]
    assert a_notif.type == NotificationType.JOURNEY_NEW_EPISODE
    assert a_notif.source_user_id == author.id


def test_create_journey_episode_skips_self_follower(db: Session) -> None:
    """If author somehow follows their own journey, helper self-skip protects."""
    author = ResidentUserFactory()
    region = RegionFactory()
    journey = Journey(
        author_id=author.id,
        region_id=region.id,
        title="Self J",
        slug="self-j",
        status=JourneyStatus.IN_PROGRESS,
    )
    db.add(journey)
    db.flush()
    db.execute(
        journey_follows.insert(),
        {"user_id": author.id, "journey_id": journey.id},
    )
    db.flush()

    create_journey_episode(
        db,
        author=author,
        journey=journey,
        payload=JourneyEpisodeMetadata(),
        title="Self ep",
        body="본인 글",
    )
    assert _notif_for(db, author.id) == []


def test_create_answer_emits_to_question_author(db: Session) -> None:
    asker = UserFactory()
    answerer = UserFactory()
    question = QuestionPostFactory(author=asker, status=PostStatus.PUBLISHED)
    db.flush()
    create_answer(db, answerer, question, "여기 답변입니다")
    notifs = _notif_for(db, asker.id)
    assert len(notifs) == 1
    n = notifs[0]
    assert n.type == NotificationType.QUESTION_ANSWERED
    assert n.source_user_id == answerer.id
    assert n.target_type == "post"
    assert n.target_id == question.id


def test_create_answer_self_does_not_emit(db: Session) -> None:
    asker = UserFactory()
    question = QuestionPostFactory(author=asker, status=PostStatus.PUBLISHED)
    db.flush()
    create_answer(db, asker, question, "self answer")
    assert _notif_for(db, asker.id) == []
