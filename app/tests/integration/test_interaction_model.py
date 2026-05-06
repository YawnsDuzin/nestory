from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Journey, Post, Region, User
from app.models._enums import PostType
from app.models.interaction import journey_follows, post_likes, post_scraps, user_follows


def _seed(db: Session) -> tuple[User, Region, Post]:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    r = Region(sido="경기", sigungu="양평군", slug=f"yp-{u.username}")
    db.add_all([u, r])
    db.flush()
    p = Post(author_id=u.id, region_id=r.id, type=PostType.REVIEW, title="t", body="b")
    db.add(p)
    db.flush()
    return u, r, p


def test_post_like_unique_per_user(db: Session) -> None:
    u, _, p = _seed(db)
    db.execute(post_likes.insert().values(post_id=p.id, user_id=u.id))
    db.flush()
    with pytest.raises(IntegrityError):
        db.execute(post_likes.insert().values(post_id=p.id, user_id=u.id))
        db.flush()
    db.rollback()


def test_post_scrap_separate_table(db: Session) -> None:
    u, _, p = _seed(db)
    db.execute(post_scraps.insert().values(post_id=p.id, user_id=u.id))
    db.flush()
    rows = db.execute(post_scraps.select().where(post_scraps.c.user_id == u.id)).all()
    assert len(rows) == 1


def test_user_follow_self_allowed_or_not_app_layer(db: Session) -> None:
    """DB 레벨엔 self-follow 제약 없음 — app 계층에서 막을 것 (P1.5)."""
    u, _, _ = _seed(db)
    db.execute(user_follows.insert().values(follower_id=u.id, following_id=u.id))
    db.flush()
    rows = db.execute(user_follows.select().where(user_follows.c.follower_id == u.id)).all()
    assert len(rows) == 1


def test_journey_follow(db: Session) -> None:
    u, r, _ = _seed(db)
    j = Journey(author_id=u.id, region_id=r.id, title="J")
    db.add(j)
    db.flush()
    db.execute(journey_follows.insert().values(journey_id=j.id, user_id=u.id))
    db.flush()
    rows = db.execute(journey_follows.select()).all()
    assert len(rows) == 1
