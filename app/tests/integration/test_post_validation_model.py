import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import PostValidation
from app.models._enums import ValidationVote
from app.tests.factories import ReviewPostFactory, UserFactory


def test_create_confirm_validation(db: Session) -> None:
    p = ReviewPostFactory()
    u = UserFactory()
    v = PostValidation(post_id=p.id, validator_user_id=u.id, vote=ValidationVote.CONFIRM)
    db.add(v)
    db.flush()
    assert v.id is not None
    assert v.vote == ValidationVote.CONFIRM


def test_duplicate_validator_per_post_rejected(db: Session) -> None:
    p = ReviewPostFactory()
    u = UserFactory()
    db.add(PostValidation(post_id=p.id, validator_user_id=u.id, vote=ValidationVote.CONFIRM))
    db.flush()
    db.add(PostValidation(post_id=p.id, validator_user_id=u.id, vote=ValidationVote.DISPUTE))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_dispute_with_note(db: Session) -> None:
    p = ReviewPostFactory()
    u = UserFactory()
    v = PostValidation(
        post_id=p.id,
        validator_user_id=u.id,
        vote=ValidationVote.DISPUTE,
        note="시공사명 일치하지 않음",
    )
    db.add(v)
    db.flush()
    assert v.note == "시공사명 일치하지 않음"
