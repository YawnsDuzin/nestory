import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models._enums import ValidationVote
from app.tests.factories import PostValidationFactory, ReviewPostFactory


def test_create_confirm_validation(db: Session) -> None:
    p = ReviewPostFactory(title="후기", body="...")
    v = PostValidationFactory(post=p, vote=ValidationVote.CONFIRM)
    assert v.id is not None
    assert v.vote == ValidationVote.CONFIRM


def test_duplicate_validator_per_post_rejected(db: Session) -> None:
    p = ReviewPostFactory(title="후기", body="...")
    first = PostValidationFactory(post=p, vote=ValidationVote.CONFIRM)
    with pytest.raises(IntegrityError):
        PostValidationFactory(
            post=p,
            validator_user_id=first.validator_user_id,
            vote=ValidationVote.DISPUTE,
        )
    db.rollback()


def test_dispute_with_note(db: Session) -> None:
    p = ReviewPostFactory(title="후기", body="...")
    v = PostValidationFactory(
        post=p,
        vote=ValidationVote.DISPUTE,
        note="시공사명 일치하지 않음",
    )
    assert v.note == "시공사명 일치하지 않음"
