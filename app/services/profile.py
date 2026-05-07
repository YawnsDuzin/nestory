"""Profile service — public profile data + author posts/scraps."""
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Post, User
from app.models._enums import PostStatus, PostType
from app.models.interaction import post_scraps

PAGE_SIZE = 20


@dataclass
class ProfileData:
    user: User
    review_count: int
    journey_episode_count: int
    question_count: int


def get_by_username(db: Session, username: str) -> User | None:
    return db.scalar(
        select(User).where(User.username == username, User.deleted_at.is_(None))
    )


def profile_data(db: Session, user: User) -> ProfileData:
    base = select(func.count(Post.id)).where(
        Post.author_id == user.id,
        Post.status == PostStatus.PUBLISHED,
        Post.deleted_at.is_(None),
    )
    return ProfileData(
        user=user,
        review_count=db.scalar(base.where(Post.type == PostType.REVIEW)) or 0,
        journey_episode_count=db.scalar(base.where(Post.type == PostType.JOURNEY_EPISODE)) or 0,
        question_count=db.scalar(base.where(Post.type == PostType.QUESTION)) or 0,
    )


def author_posts(db: Session, user: User, post_type: PostType, *, page: int = 1) -> list[Post]:
    return list(db.scalars(
        select(Post)
        .where(
            Post.author_id == user.id,
            Post.type == post_type,
            Post.status == PostStatus.PUBLISHED,
            Post.deleted_at.is_(None),
        )
        .options(selectinload(Post.region))
        .order_by(Post.published_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all())


def user_scraps(db: Session, user: User, *, page: int = 1) -> list[Post]:
    return list(db.scalars(
        select(Post)
        .join(post_scraps, post_scraps.c.post_id == Post.id)
        .where(
            post_scraps.c.user_id == user.id,
            Post.status == PostStatus.PUBLISHED,
            Post.deleted_at.is_(None),
        )
        .options(selectinload(Post.author), selectinload(Post.region))
        .order_by(post_scraps.c.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all())


__all__ = [
    "PAGE_SIZE",
    "ProfileData",
    "get_by_username",
    "profile_data",
    "author_posts",
    "user_scraps",
]
