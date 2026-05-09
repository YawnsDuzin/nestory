"""Unit tests for app.services.notifications.

Tests:
- test_create_notification_inserts_row
- test_create_notification_skips_self_trigger
- test_create_notification_with_no_source_user
- test_unread_count_excludes_read
- test_mark_read_owner_succeeds
- test_mark_read_other_user_returns_none
- test_mark_read_idempotent_for_already_read
- test_mark_all_read_only_targets_unread
- test_mark_all_read_isolates_users
- test_list_paginated_orders_desc_with_total
- test_recent_for_dropdown_caps_at_5
- test_format_label_per_type
- test_resolve_link_per_target

NOTE: Requires running Postgres (factory-boy + db fixture).
"""
from sqlalchemy.orm import Session

from app.models import Notification
from app.models._enums import NotificationType
from app.services import notifications as nsvc
from app.tests.factories import NotificationFactory, UserFactory


def test_create_notification_inserts_row(db: Session) -> None:
    recipient = UserFactory()
    source = UserFactory()
    notif = nsvc.create_notification(
        db,
        recipient=recipient,
        type=NotificationType.POST_COMMENT,
        source_user=source,
        target_type="post",
        target_id=42,
    )
    assert notif is not None
    assert notif.user_id == recipient.id
    assert notif.source_user_id == source.id
    assert notif.target_type == "post"
    assert notif.target_id == 42
    assert notif.is_read is False


def test_create_notification_skips_self_trigger(db: Session) -> None:
    user = UserFactory()
    notif = nsvc.create_notification(
        db,
        recipient=user,
        type=NotificationType.POST_COMMENT,
        source_user=user,  # same user
    )
    assert notif is None


def test_create_notification_with_no_source_user(db: Session) -> None:
    """System notifications have no source_user — must not skip."""
    user = UserFactory()
    notif = nsvc.create_notification(
        db, recipient=user, type=NotificationType.SYSTEM
    )
    assert notif is not None
    assert notif.source_user_id is None


def test_unread_count_excludes_read(db: Session) -> None:
    user = UserFactory()
    NotificationFactory(user=user, is_read=False)
    NotificationFactory(user=user, is_read=False)
    NotificationFactory(user=user, is_read=True)
    assert nsvc.unread_count(db, user) == 2


def test_mark_read_owner_succeeds(db: Session) -> None:
    user = UserFactory()
    notif = NotificationFactory(user=user, is_read=False)
    out = nsvc.mark_read(db, user, notif.id)
    assert out is not None
    assert out.is_read is True


def test_mark_read_other_user_returns_none(db: Session) -> None:
    owner = UserFactory()
    intruder = UserFactory()
    notif = NotificationFactory(user=owner, is_read=False)
    out = nsvc.mark_read(db, intruder, notif.id)
    assert out is None
    db.refresh(notif)
    assert notif.is_read is False  # untouched


def test_mark_read_idempotent_for_already_read(db: Session) -> None:
    user = UserFactory()
    notif = NotificationFactory(user=user, is_read=True)
    out = nsvc.mark_read(db, user, notif.id)
    assert out is not None
    assert out.is_read is True


def test_mark_all_read_only_targets_unread(db: Session) -> None:
    user = UserFactory()
    NotificationFactory(user=user, is_read=False)
    NotificationFactory(user=user, is_read=False)
    NotificationFactory(user=user, is_read=True)
    n = nsvc.mark_all_read(db, user)
    assert n == 2
    assert nsvc.unread_count(db, user) == 0


def test_mark_all_read_isolates_users(db: Session) -> None:
    a = UserFactory()
    b = UserFactory()
    NotificationFactory(user=a, is_read=False)
    NotificationFactory(user=b, is_read=False)
    nsvc.mark_all_read(db, a)
    assert nsvc.unread_count(db, b) == 1


def test_list_paginated_orders_desc_with_total(db: Session) -> None:
    user = UserFactory()
    older = NotificationFactory(user=user)
    newer = NotificationFactory(user=user)
    views, total = nsvc.list_paginated(db, user, page=1)
    assert total == 2
    assert [v.notification.id for v in views] == [newer.id, older.id]


def test_recent_for_dropdown_caps_at_5(db: Session) -> None:
    user = UserFactory()
    for _ in range(7):
        NotificationFactory(user=user)
    views = nsvc.recent_for_dropdown(db, user)
    assert len(views) == 5


def test_format_label_per_type() -> None:
    notif = Notification(
        user_id=1, type=NotificationType.BADGE_APPROVED, is_read=False
    )
    assert "승인" in nsvc._format_label(notif, None)

    notif = Notification(
        user_id=1, type=NotificationType.BADGE_REJECTED, is_read=False
    )
    assert "반려" in nsvc._format_label(notif, None)

    notif = Notification(
        user_id=1, type=NotificationType.POST_COMMENT, is_read=False
    )
    assert "@alice" in nsvc._format_label(notif, "alice")
    assert "댓글" in nsvc._format_label(notif, "alice")

    notif = Notification(
        user_id=1, type=NotificationType.JOURNEY_NEW_EPISODE, is_read=False
    )
    assert "에피소드" in nsvc._format_label(notif, "alice")

    notif = Notification(
        user_id=1, type=NotificationType.QUESTION_ANSWERED, is_read=False
    )
    assert "답변" in nsvc._format_label(notif, "alice")

    notif = Notification(
        user_id=1, type=NotificationType.SYSTEM, is_read=False
    )
    assert "공지" in nsvc._format_label(notif, None)


def test_resolve_link_per_target() -> None:
    n_badge = Notification(
        user_id=1,
        type=NotificationType.BADGE_APPROVED,
        target_type="badge_application",
        target_id=99,
        is_read=False,
    )
    assert nsvc.resolve_link(n_badge) == "/me/badge"

    n_post = Notification(
        user_id=1,
        type=NotificationType.POST_COMMENT,
        target_type="post",
        target_id=42,
        is_read=False,
    )
    assert nsvc.resolve_link(n_post) == "/post/42"

    n_unknown = Notification(
        user_id=1, type=NotificationType.SYSTEM, is_read=False
    )
    assert nsvc.resolve_link(n_unknown) == "/notifications"
