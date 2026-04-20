import pytest
from sqlalchemy.orm import Session

from app.models.user import UserRole
from app.services.auth import create_user_with_password
from scripts.bootstrap_admin import promote_admin


def test_promote_existing_user_to_admin(db: Session) -> None:
    user = create_user_with_password(
        db,
        email="me@example.com",
        username="me",
        display_name="Me",
        password="secret12",
    )
    db.commit()

    promote_admin(db, email="me@example.com")
    db.commit()
    db.refresh(user)

    assert user.role == UserRole.ADMIN


def test_promote_missing_user_raises(db: Session) -> None:
    with pytest.raises(LookupError):
        promote_admin(db, email="nobody@example.com")


def test_promote_noop_when_already_admin(db: Session) -> None:
    user = create_user_with_password(
        db,
        email="a@a.com",
        username="a",
        display_name="A",
        password="secret12",
    )
    user.role = UserRole.ADMIN
    db.commit()

    promote_admin(db, email="a@a.com")
    db.commit()
    db.refresh(user)
    assert user.role == UserRole.ADMIN
