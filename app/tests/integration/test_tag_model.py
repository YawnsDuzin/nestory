import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Tag
from app.models.tag import post_tags
from app.tests.factories import ReviewPostFactory


def test_create_tag_unique_name(db: Session) -> None:
    db.add(Tag(name="단열", slug="insulation"))
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(Tag(name="단열", slug="insulation-2"))
        db.flush()
    db.rollback()


def test_attach_tag_to_post(db: Session) -> None:
    p = ReviewPostFactory()
    t = Tag(name="후회", slug="regret")
    db.add(t)
    db.flush()
    db.execute(post_tags.insert().values(post_id=p.id, tag_id=t.id))
    db.flush()

    rows = db.execute(post_tags.select().where(post_tags.c.post_id == p.id)).all()
    assert len(rows) == 1
