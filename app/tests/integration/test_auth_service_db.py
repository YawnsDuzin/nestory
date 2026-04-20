from sqlalchemy.orm import Session

from app.models.user import User
from app.services.auth import create_user_with_password, find_user_by_email


def test_create_and_find_user(db: Session) -> None:
    user = create_user_with_password(
        db,
        email="alice@example.com",
        username="alice",
        display_name="앨리스",
        password="horse-staple-42",
    )
    db.commit()

    assert user.id is not None
    assert user.email == "alice@example.com"
    assert user.password_hash is not None and user.password_hash.startswith("$argon2id$")

    found = find_user_by_email(db, "alice@example.com")
    assert found is not None
    assert found.id == user.id


def test_create_user_duplicate_email_raises(db: Session) -> None:
    create_user_with_password(db, email="dup@example.com", username="d1", display_name="d", password="x12345")
    db.commit()

    import pytest
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        create_user_with_password(db, email="dup@example.com", username="d2", display_name="d", password="x12345")
        db.commit()
