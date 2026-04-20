from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.user import BadgeLevel, User, UserRole


def test_create_user_with_defaults(db: Session) -> None:
    user = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    db.add(user)
    db.flush()

    assert user.id is not None
    assert user.role == UserRole.USER
    assert user.badge_level == BadgeLevel.INTERESTED
    assert user.created_at is not None
    assert user.deleted_at is None
