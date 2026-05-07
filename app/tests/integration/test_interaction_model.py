import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.interaction import (
    journey_follows,
    post_scraps,
    user_follows,
)
from app.tests.factories import (
    JourneyFactory,
    PostFactory,
    UserFactory,
    add_journey_follow,
    add_post_like,
    add_post_scrap,
    add_user_follow,
)


def test_post_like_unique_per_user(db: Session) -> None:
    u = UserFactory()
    p = PostFactory()
    add_post_like(db, u, p)
    with pytest.raises(IntegrityError):
        add_post_like(db, u, p)
    db.rollback()


def test_post_scrap_separate_table(db: Session) -> None:
    u = UserFactory()
    p = PostFactory()
    add_post_scrap(db, u, p)
    rows = db.execute(post_scraps.select().where(post_scraps.c.user_id == u.id)).all()
    assert len(rows) == 1


def test_user_follow_self_allowed_or_not_app_layer(db: Session) -> None:
    """DB 레벨엔 self-follow 제약 없음 — app 계층에서 막을 것 (P1.5)."""
    u = UserFactory()
    add_user_follow(db, u, u)
    rows = db.execute(user_follows.select().where(user_follows.c.follower_id == u.id)).all()
    assert len(rows) == 1


def test_journey_follow(db: Session) -> None:
    u = UserFactory()
    j = JourneyFactory()
    add_journey_follow(db, u, j)
    rows = db.execute(journey_follows.select()).all()
    assert len(rows) == 1
