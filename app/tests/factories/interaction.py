"""Helpers for M:N junction Tables (post_likes, post_scraps, etc).

These are not factory_boy `Factory` classes because the underlying objects
are SQLAlchemy `Table` instances, not ORM models. They take the active session
explicitly so callers can use them alongside ORM-backed factories.
"""
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.interaction import (
    journey_follows,
    post_likes,
    post_scraps,
    user_follows,
)


def add_post_like(session: Session, user, post) -> None:
    session.execute(
        post_likes.insert().values(
            user_id=user.id, post_id=post.id, created_at=datetime.now(UTC)
        )
    )
    session.flush()


def add_post_scrap(session: Session, user, post) -> None:
    session.execute(
        post_scraps.insert().values(
            user_id=user.id, post_id=post.id, created_at=datetime.now(UTC)
        )
    )
    session.flush()


def add_journey_follow(session: Session, user, journey) -> None:
    session.execute(
        journey_follows.insert().values(
            user_id=user.id, journey_id=journey.id, created_at=datetime.now(UTC)
        )
    )
    session.flush()


def add_user_follow(session: Session, follower, following) -> None:
    session.execute(
        user_follows.insert().values(
            follower_id=follower.id,
            following_id=following.id,
            created_at=datetime.now(UTC),
        )
    )
    session.flush()
