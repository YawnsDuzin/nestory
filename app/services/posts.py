"""Posts service — 5 type create + Journey row + view_count.

CLAUDE.md alignment: db first, user second, returns ORM Post (or Journey).
PostMetadata Pydantic models passed in by caller; service serializes to JSONB
via model_dump and pops type_tag (discriminator lives in Post.type column).
"""
from datetime import UTC, date, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, selectinload

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
    cover_image_id: int | None = None,
) -> Journey:
    j = Journey(
        author_id=author.id, region_id=region.id,
        title=title, description=description, start_date=start_date,
        cover_image_id=cover_image_id,
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


def update_question(
    db: Session,
    post: Post,
    *,
    payload: QuestionMetadata,
    title: str,
    body: str,
) -> Post:
    """Question의 title/body/tags를 수정. edited_at 갱신.

    - type, author, region, created_at, published_at은 불변.
    - metadata는 type_tag(__post_type__) 제외 후 dict화.
    """
    if post.type != PostType.QUESTION:
        raise ValueError(f"Cannot update_question on type={post.type.value}")
    post.title = title
    post.body = body
    meta = payload.model_dump(by_alias=True, exclude_none=True)
    meta.pop("__post_type__", None)
    post.metadata_ = {"__post_type__": "question", **meta}
    post.edited_at = datetime.now(UTC)
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
    db.execute(
        update(Post).where(Post.id == post.id).values(view_count=Post.view_count + 1)
    )
    db.flush()


def get_post_for_detail(db: Session, post_id: int) -> Post | None:
    """published, non-Journey-episode/Answer 1건 + author/region eager. None if 미존재/숨김."""
    post = db.scalars(
        select(Post)
        .options(selectinload(Post.author), selectinload(Post.region))
        .where(Post.id == post_id)
    ).first()
    if (
        post is None
        or post.deleted_at is not None
        or post.status != PostStatus.PUBLISHED
        or post.type in (PostType.JOURNEY_EPISODE, PostType.ANSWER)
    ):
        return None
    return post


def get_question_for_detail(db: Session, post_id: int) -> Post | None:
    """published QUESTION 1건 + author/region eager. None if 미존재/숨김/타입미스."""
    post = db.scalars(
        select(Post)
        .options(selectinload(Post.author), selectinload(Post.region))
        .where(Post.id == post_id)
    ).first()
    if (
        post is None
        or post.deleted_at is not None
        or post.type != PostType.QUESTION
        or post.status != PostStatus.PUBLISHED
    ):
        return None
    return post


def list_published_answers(db: Session, question_id: int) -> list[Post]:
    """답변(ANSWER) 목록 — author eager, published_at asc."""
    return list(
        db.scalars(
            select(Post)
            .options(selectinload(Post.author))
            .where(
                Post.parent_post_id == question_id,
                Post.type == PostType.ANSWER,
                Post.deleted_at.is_(None),
            )
            .order_by(Post.published_at.asc())
        ).all()
    )


def list_journey_episodes(db: Session, journey_id: int) -> list[Post]:
    """journey 전체 published 에피소드 — author eager, episode_no asc."""
    return list(
        db.scalars(
            select(Post)
            .options(selectinload(Post.author))
            .where(
                Post.journey_id == journey_id,
                Post.type == PostType.JOURNEY_EPISODE,
                Post.deleted_at.is_(None),
                Post.status == PostStatus.PUBLISHED,
            )
            .order_by(Post.episode_no.asc())
        ).all()
    )


def count_journey_episodes(db: Session, journey_id: int) -> int:
    """journey의 published 에피소드 총 개수 — ep detail navigation progress용."""
    return db.scalar(
        select(func.count(Post.id)).where(
            Post.journey_id == journey_id,
            Post.type == PostType.JOURNEY_EPISODE,
            Post.deleted_at.is_(None),
            Post.status == PostStatus.PUBLISHED,
        )
    ) or 0


def get_journey_episode(db: Session, journey_id: int, ep_no: int) -> Post | None:
    """journey + episode_no로 단일 published 에피소드 — author/region eager."""
    return db.scalars(
        select(Post)
        .options(selectinload(Post.author), selectinload(Post.region))
        .where(
            Post.journey_id == journey_id,
            Post.episode_no == ep_no,
            Post.type == PostType.JOURNEY_EPISODE,
            Post.deleted_at.is_(None),
            Post.status == PostStatus.PUBLISHED,
        )
    ).first()


def prev_journey_episode(db: Session, journey_id: int, ep_no: int) -> Post | None:
    """현재 ep_no 이전의 가장 가까운 에피소드. 없으면 None."""
    return db.scalars(
        select(Post)
        .where(
            Post.journey_id == journey_id,
            Post.episode_no < ep_no,
            Post.type == PostType.JOURNEY_EPISODE,
            Post.deleted_at.is_(None),
        )
        .order_by(Post.episode_no.desc())
    ).first()


def next_journey_episode(db: Session, journey_id: int, ep_no: int) -> Post | None:
    """현재 ep_no 이후의 가장 가까운 에피소드. 없으면 None."""
    return db.scalars(
        select(Post)
        .where(
            Post.journey_id == journey_id,
            Post.episode_no > ep_no,
            Post.type == PostType.JOURNEY_EPISODE,
            Post.deleted_at.is_(None),
        )
        .order_by(Post.episode_no.asc())
    ).first()


__all__ = [
    "BODY_MAX_LENGTH",
    "create_answer",
    "create_journey",
    "create_journey_episode",
    "create_plan",
    "create_question",
    "create_review",
    "get_journey_episode",
    "get_post_for_detail",
    "get_question_for_detail",
    "increment_view_count",
    "list_journey_episodes",
    "count_journey_episodes",
    "list_published_answers",
    "next_journey_episode",
    "prev_journey_episode",
    "update_question",
    "validate_body_length",
]
