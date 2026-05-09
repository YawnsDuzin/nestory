"""Integration tests for /notifications routes.

Tests:
- test_notifications_page_requires_login
- test_notifications_page_renders_for_owner
- test_notifications_page_paginates
- test_bell_partial_returns_unread_count_zero_for_new_user
- test_bell_partial_returns_unread_with_recent
- test_read_marks_notification_and_redirects_to_link
- test_read_returns_404_for_other_user
- test_read_returns_404_for_unknown_id
- test_read_all_marks_all_owned_unread

NOTE: Requires running Postgres.
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import NotificationType
from app.services.notifications import unread_count
from app.tests.factories import NotificationFactory, UserFactory


def test_notifications_page_requires_login(client: TestClient) -> None:
    r = client.get("/notifications")
    assert r.status_code == 401


def test_notifications_page_renders_for_owner(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    NotificationFactory(user=user, type=NotificationType.SYSTEM)
    db.commit()
    login(user.id)
    r = client.get("/notifications")
    assert r.status_code == 200
    assert "알림" in r.text


def test_notifications_page_paginates(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    for _ in range(35):
        NotificationFactory(user=user)
    db.commit()
    login(user.id)
    r1 = client.get("/notifications?page=1")
    r2 = client.get("/notifications?page=2")
    assert r1.status_code == 200
    assert r2.status_code == 200


def test_bell_partial_returns_unread_count_zero_for_new_user(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.get("/notifications/_bell")
    assert r.status_code == 200
    assert "새 알림이 없습니다" in r.text


def test_bell_partial_returns_unread_with_recent(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    NotificationFactory(user=user, is_read=False, type=NotificationType.SYSTEM)
    NotificationFactory(user=user, is_read=False, type=NotificationType.SYSTEM)
    db.commit()
    login(user.id)
    r = client.get("/notifications/_bell")
    assert r.status_code == 200
    assert "공지" in r.text


def test_read_marks_notification_and_redirects_to_link(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    notif = NotificationFactory(
        user=user,
        is_read=False,
        type=NotificationType.POST_COMMENT,
        target_type="post",
        target_id=42,
    )
    db.commit()
    login(user.id)
    r = client.post(
        f"/notifications/{notif.id}/read", follow_redirects=False
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/post/42"
    db.refresh(notif)
    assert notif.is_read is True


def test_read_returns_404_for_other_user(
    client: TestClient, db: Session, login
) -> None:
    owner = UserFactory()
    intruder = UserFactory()
    notif = NotificationFactory(user=owner, is_read=False)
    db.commit()
    login(intruder.id)
    r = client.post(f"/notifications/{notif.id}/read")
    assert r.status_code == 404


def test_read_returns_404_for_unknown_id(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.post("/notifications/99999/read")
    assert r.status_code == 404


def test_read_all_marks_all_owned_unread(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    NotificationFactory(user=user, is_read=False)
    NotificationFactory(user=user, is_read=False)
    NotificationFactory(user=user, is_read=True)
    db.commit()
    login(user.id)
    r = client.post("/notifications/read-all", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/notifications"
    assert unread_count(db, user) == 0
