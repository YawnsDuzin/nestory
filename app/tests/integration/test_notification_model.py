from sqlalchemy.orm import Session

from app.models._enums import NotificationType
from app.tests.factories import NotificationFactory


def test_create_unread_notification(db: Session) -> None:
    n = NotificationFactory(
        type=NotificationType.BADGE_APPROVED,
        target_type="badge_application",
        target_id=42,
    )
    assert n.is_read is False
    assert n.target_type == "badge_application"


def test_mark_as_read(db: Session) -> None:
    n = NotificationFactory(type=NotificationType.SYSTEM)
    n.is_read = True
    db.flush()
    assert n.is_read is True
