from sqlalchemy.orm import Session

from app.models import Notification
from app.models._enums import NotificationType
from app.tests.factories import UserFactory


def test_create_unread_notification(db: Session) -> None:
    u = UserFactory()
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
    u = UserFactory()
    n = Notification(user_id=u.id, type=NotificationType.SYSTEM)
    db.add(n)
    db.flush()
    n.is_read = True
    db.flush()
    assert n.is_read is True
