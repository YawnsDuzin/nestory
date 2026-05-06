from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Notification, User
from app.models._enums import NotificationType


def _make_user(db: Session) -> User:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    db.add(u)
    db.flush()
    return u


def test_create_unread_notification(db: Session) -> None:
    u = _make_user(db)
    n = Notification(
        user_id=u.id,
        type=NotificationType.BADGE_APPROVED,
        target_type="badge_application",
        target_id=42,
    )
    db.add(n)
    db.flush()
    assert n.is_read is False
    assert n.target_type == "badge_application"


def test_mark_as_read(db: Session) -> None:
    u = _make_user(db)
    n = Notification(user_id=u.id, type=NotificationType.SYSTEM)
    db.add(n)
    db.flush()
    n.is_read = True
    db.flush()
    assert n.is_read is True
