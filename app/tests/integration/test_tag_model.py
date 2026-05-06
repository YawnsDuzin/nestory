from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Post, Region, Tag, User
from app.models._enums import PostType
from app.models.tag import post_tags


def _seed_post(db: Session) -> Post:
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
    return p


def test_create_tag_unique_name(db: Session) -> None:
    db.add(Tag(name="단열", slug="insulation"))
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(Tag(name="단열", slug="insulation-2"))
        db.flush()
    db.rollback()


def test_attach_tag_to_post(db: Session) -> None:
    p = _seed_post(db)
    t = Tag(name="후회", slug="regret")
    db.add(t)
    db.flush()
    db.execute(post_tags.insert().values(post_id=p.id, tag_id=t.id))
    db.flush()

    rows = db.execute(post_tags.select().where(post_tags.c.post_id == p.id)).all()
    assert len(rows) == 1
