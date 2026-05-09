"""Integration tests for /admin/reports route."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import ReportStatus
from app.tests.factories import (
    AdminUserFactory,
    ReportFactory,
    UserFactory,
)


def test_reports_requires_admin(client: TestClient, db: Session, login) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.get("/admin/reports")
    assert r.status_code == 403


def test_reports_empty_queue_message(
    client: TestClient, db: Session, login
) -> None:
    admin = AdminUserFactory()
    db.commit()
    login(admin.id)
    r = client.get("/admin/reports")
    assert r.status_code == 200
    assert "현재 처리 대기 중인 신고가 없습니다" in r.text


def test_reports_pending_only(client: TestClient, db: Session, login) -> None:
    admin = AdminUserFactory()
    reporter = UserFactory()
    ReportFactory(reporter=reporter, status=ReportStatus.PENDING)
    ReportFactory(reporter=reporter, status=ReportStatus.RESOLVED)
    db.commit()
    login(admin.id)
    r = client.get("/admin/reports")
    assert r.status_code == 200
    assert "총 1건" in r.text
