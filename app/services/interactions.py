"""Interactions service — idempotent like/scrap toggles."""
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Post, User
from app.models.interaction import post_likes, post_scraps


def is_liked_by(db: Session, post_id: int, user_id: int) -> bool:
    return (
        db.scalar(
            select(func.count())
            .select_from(post_likes)
            .where(post_likes.c.post_id == post_id, post_likes.c.user_id == user_id)
        )
        == 1
    )


def like_count(db: Session, post_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(post_likes)
            .where(post_likes.c.post_id == post_id)
        )
        or 0
    )


def toggle_like(db: Session, post: Post, user: User) -> bool:
    """Return True if now-liked, False if now-unliked."""
    if is_liked_by(db, post.id, user.id):
        db.execute(
            delete(post_likes).where(
                post_likes.c.post_id == post.id, post_likes.c.user_id == user.id
            )
        )
        db.commit()
        return False
    try:
        db.execute(insert(post_likes).values(post_id=post.id, user_id=user.id))
        db.commit()
    except IntegrityError:
        db.rollback()  # 동시 클릭 race — 결과적 멱등
    return True


def is_scrapped_by(db: Session, post_id: int, user_id: int) -> bool:
    return (
        db.scalar(
            select(func.count())
            .select_from(post_scraps)
            .where(post_scraps.c.post_id == post_id, post_scraps.c.user_id == user_id)
        )
        == 1
    )


def scrap_count(db: Session, post_id: int) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(post_scraps)
            .where(post_scraps.c.post_id == post_id)
        )
        or 0
    )


def toggle_scrap(db: Session, post: Post, user: User) -> bool:
    """Return True if now-scrapped, False if now-unscrapped."""
    if is_scrapped_by(db, post.id, user.id):
        db.execute(
            delete(post_scraps).where(
                post_scraps.c.post_id == post.id, post_scraps.c.user_id == user.id
            )
        )
        db.commit()
        return False
    try:
        db.execute(insert(post_scraps).values(post_id=post.id, user_id=user.id))
        db.commit()
    except IntegrityError:
        db.rollback()  # 동시 클릭 race — 결과적 멱등
    return True


__all__ = [
    "is_liked_by",
    "is_scrapped_by",
    "like_count",
    "scrap_count",
    "toggle_like",
    "toggle_scrap",
]
