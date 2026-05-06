from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Post, PostValidation, Region, User
from app.models._enums import PostType, ValidationVote


def _seed_post(db: Session) -> tuple[User, Post]:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    r = Region(sido="경기", sigungu="양평군", slug=f"yp-{u.username}")
    db.add_all([u, r])
    db.flush()
    p = Post(author_id=u.id, region_id=r.id, type=PostType.REVIEW, title="후기", body="...")
    db.add(p)
    db.flush()
    return u, p


def test_create_confirm_validation(db: Session) -> None:
    u, p = _seed_post(db)
    v = PostValidation(post_id=p.id, validator_user_id=u.id, vote=ValidationVote.CONFIRM)
    db.add(v)
    db.flush()
    assert v.id is not None
    assert v.vote == ValidationVote.CONFIRM


def test_duplicate_validator_per_post_rejected(db: Session) -> None:
    u, p = _seed_post(db)
    db.add(PostValidation(post_id=p.id, validator_user_id=u.id, vote=ValidationVote.CONFIRM))
    db.flush()
    db.add(PostValidation(post_id=p.id, validator_user_id=u.id, vote=ValidationVote.DISPUTE))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_dispute_with_note(db: Session) -> None:
    u, p = _seed_post(db)
    v = PostValidation(
        post_id=p.id,
        validator_user_id=u.id,
        vote=ValidationVote.DISPUTE,
        note="시공사명 일치하지 않음",
    )
    db.add(v)
    db.flush()
    assert v.note == "시공사명 일치하지 않음"
