"""Posts service — 5 type create + Journey row + view_count.

CLAUDE.md alignment: db first, user second, returns ORM Post (or Journey).
PostMetadata Pydantic models passed in by caller; service serializes to JSONB
via model_dump and pops type_tag (discriminator lives in Post.type column).
"""
from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Journey, Post, Region, User
from app.models._enums import JourneyStatus, NotificationType, PostStatus, PostType
from app.models.interaction import journey_follows
from app.schemas.post_metadata import (
    AnswerMetadata,
    JourneyEpisodeMetadata,
    PlanMetadata,
    QuestionMetadata,
    ReviewMetadata,
)
from app.services.notifications import create_notification

BODY_MAX_LENGTH = 50_000  # ~50KB markdown — abuse prevention


def validate_body_length(body: str) -> None:
    """Raise HTTP 400 if body exceeds BODY_MAX_LENGTH bytes (UTF-8)."""
    if len(body.encode("utf-8")) > BODY_MAX_LENGTH:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"본문이 너무 깁니다 (최대 {BODY_MAX_LENGTH:,} 바이트)",
        )


def _meta_to_jsonb(payload) -> dict:
    """Pydantic → dict for Post.metadata. type_tag is dropped (discriminator
    lives in Post.type column, not JSONB)."""
    d = payload.model_dump(by_alias=False, exclude_none=True)
    d.pop("type_tag", None)
    return d


def _publish_now() -> datetime:
    return datetime.now(UTC)


def create_review(
    db: Session, author: User, region: Region, payload: ReviewMetadata,
    title: str, body: str,
) -> Post:
    post = Post(
        author_id=author.id, region_id=region.id, type=PostType.REVIEW,
        title=title, body=body, metadata_=_meta_to_jsonb(payload),
        status=PostStatus.PUBLISHED, published_at=_publish_now(),
    )
    db.add(post)
    db.flush()
    return post


def create_journey(
    db: Session, author: User, region: Region,
    title: str, description: str | None, start_date: date | None,
) -> Journey:
    j = Journey(
        author_id=author.id, region_id=region.id,
        title=title, description=description, start_date=start_date,
        status=JourneyStatus.IN_PROGRESS,
    )
    db.add(j)
    db.flush()
    return j


def create_journey_episode(
    db: Session, author: User, journey: Journey, payload: JourneyEpisodeMetadata,
    title: str, body: str,
) -> Post:
    max_ep = (
        db.query(func.max(Post.episode_no))
        .filter(Post.journey_id == journey.id)
        .scalar()
    )
    next_ep = (max_ep or 0) + 1
    post = Post(
        author_id=author.id, region_id=journey.region_id, journey_id=journey.id,
        type=PostType.JOURNEY_EPISODE, episode_no=next_ep,
        title=title, body=body, metadata_=_meta_to_jsonb(payload),
        status=PostStatus.PUBLISHED, published_at=_publish_now(),
    )
    db.add(post)
    db.flush()
    followers = list(
        db.scalars(
            select(User)
            .join(journey_follows, User.id == journey_follows.c.user_id)
            .where(journey_follows.c.journey_id == journey.id)
        ).all()
    )
    for follower in followers:
        create_notification(
            db,
            recipient=follower,
            type=NotificationType.JOURNEY_NEW_EPISODE,
            source_user=author,
            target_type="post",
            target_id=post.id,
        )
    return post


def create_question(
    db: Session, author: User, region: Region, payload: QuestionMetadata,
    title: str, body: str,
) -> Post:
    post = Post(
        author_id=author.id, region_id=region.id, type=PostType.QUESTION,
        title=title, body=body, metadata_=_meta_to_jsonb(payload),
        status=PostStatus.PUBLISHED, published_at=_publish_now(),
    )
    db.add(post)
    db.flush()
    return post


def create_answer(db: Session, author: User, parent_question: Post, body: str) -> Post:
    payload = AnswerMetadata()
    post = Post(
        author_id=author.id, region_id=parent_question.region_id,
        parent_post_id=parent_question.id, type=PostType.ANSWER,
        title="", body=body, metadata_=_meta_to_jsonb(payload),
        status=PostStatus.PUBLISHED, published_at=_publish_now(),
    )
    db.add(post)
    db.flush()
    question_author = db.get(User, parent_question.author_id)
    if question_author is not None:
        create_notification(
            db,
            recipient=question_author,
            type=NotificationType.QUESTION_ANSWERED,
            source_user=author,
            target_type="post",
            target_id=parent_question.id,
        )
    return post


def create_plan(
    db: Session, author: User, region: Region, payload: PlanMetadata,
    title: str, body: str,
) -> Post:
    post = Post(
        author_id=author.id, region_id=region.id, type=PostType.PLAN,
        title=title, body=body, metadata_=_meta_to_jsonb(payload),
        status=PostStatus.PUBLISHED, published_at=_publish_now(),
    )
    db.add(post)
    db.flush()
    return post


def increment_view_count(db: Session, post: Post) -> None:
    db.query(Post).filter(Post.id == post.id).update(
        {Post.view_count: Post.view_count + 1}
    )
    db.flush()


__all__ = [
    "BODY_MAX_LENGTH",
    "create_answer",
    "create_journey",
    "create_journey_episode",
    "create_plan",
    "create_question",
    "create_review",
    "increment_view_count",
    "validate_body_length",
]
