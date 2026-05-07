from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.user import BadgeLevel, UserRole
from app.tests.factories import UserFactory


def test_create_user_with_defaults(db: Session) -> None:
    user = UserFactory(display_name="테스터", password_hash="x")

    assert user.id is not None
    assert user.role == UserRole.USER
    assert user.badge_level == BadgeLevel.INTERESTED
    assert user.created_at is not None
    assert user.deleted_at is None


def test_user_v1_1_columns_default_null(db: Session) -> None:
    user = UserFactory(display_name="테스터", password_hash="x")
    assert user.resident_revalidated_at is None
    assert user.ex_resident_at is None
    assert user.anonymized_at is None


def test_user_can_be_set_to_ex_resident(db: Session) -> None:
    user = UserFactory(
        display_name="테스터",
        password_hash="x",
        badge_level=BadgeLevel.EX_RESIDENT,
        ex_resident_at=datetime.now(UTC),
    )
    assert user.badge_level == BadgeLevel.EX_RESIDENT
