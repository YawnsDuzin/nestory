import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Journey
from app.models.interaction import journey_follows, post_likes, post_scraps, user_follows
from app.tests.factories import RegionFactory, ReviewPostFactory, UserFactory


def test_post_like_unique_per_user(db: Session) -> None:
    p = ReviewPostFactory()
    u = UserFactory()
    db.execute(post_likes.insert().values(post_id=p.id, user_id=u.id))
    db.flush()
    with pytest.raises(IntegrityError):
        db.execute(post_likes.insert().values(post_id=p.id, user_id=u.id))
        db.flush()
    db.rollback()


def test_post_scrap_separate_table(db: Session) -> None:
    p = ReviewPostFactory()
    u = UserFactory()
    db.execute(post_scraps.insert().values(post_id=p.id, user_id=u.id))
    db.flush()
    rows = db.execute(post_scraps.select().where(post_scraps.c.user_id == u.id)).all()
    assert len(rows) == 1


def test_user_follow_self_allowed_or_not_app_layer(db: Session) -> None:
    """DB 레벨엔 self-follow 제약 없음 — app 계층에서 막을 것 (P1.5)."""
    u = UserFactory()
    db.execute(user_follows.insert().values(follower_id=u.id, following_id=u.id))
    db.flush()
    rows = db.execute(user_follows.select().where(user_follows.c.follower_id == u.id)).all()
    assert len(rows) == 1


def test_journey_follow(db: Session) -> None:
    u = UserFactory()
    r = RegionFactory()
    j = Journey(author_id=u.id, region_id=r.id, title="J")
    db.add(j)
    db.flush()
    db.execute(journey_follows.insert().values(journey_id=j.id, user_id=u.id))
    db.flush()
    rows = db.execute(journey_follows.select()).all()
    assert len(rows) == 1
