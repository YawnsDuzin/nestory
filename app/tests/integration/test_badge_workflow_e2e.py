"""Full badge workflow e2e test.

Scenario: signup → resident 신청(증빙 업로드) → 관리자 승인
          → User.badge_level=RESIDENT → cleanup 잡 dispatch → 파일·행 삭제.
"""
import io
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BadgeApplication, BadgeEvidence, User
from app.models._enums import BadgeApplicationStatus, JobKind
from app.models.user import BadgeLevel
from app.tests.factories import AdminUserFactory, RegionFactory
from app.workers.handlers import dispatch, import_handlers


@pytest.fixture(autouse=True)
def _isolate_evidence_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDENCE_BASE_PATH", str(tmp_path / "evidence"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_full_badge_workflow(db: Session, client: TestClient, login) -> None:
    # Seed admin + region
    ts = int(datetime.now(UTC).timestamp() * 1_000_000)
    admin = AdminUserFactory(display_name="관리자")
    region = RegionFactory(sigungu="양평군", slug=f"yp-e2e-{ts}")
    db.commit()

    # User signup via auth route
    resp = client.post(
        "/auth/signup",
        data={
            "email": f"u{ts}@x.com",
            "username": f"u{ts}",
            "display_name": "신청자",
            "password": "Password!123",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    user = db.query(User).filter_by(email=f"u{ts}@x.com").one()
    assert user.badge_level == BadgeLevel.INTERESTED

    # Step 1: user applies for resident with evidence
    login(user.id)
    r = client.post(
        "/me/badge/resident",
        data={"region_id": region.id},
        files={"utility_bill": ("bill.jpg", io.BytesIO(b"fake-evidence"), "image/jpeg")},
        follow_redirects=False,
    )
    assert r.status_code == 303
    app_obj = db.query(BadgeApplication).filter_by(user_id=user.id).one()
    assert app_obj.status == BadgeApplicationStatus.PENDING
    evidences = db.query(BadgeEvidence).filter_by(application_id=app_obj.id).all()
    assert len(evidences) == 1

    # Step 2: admin approves
    login(admin.id)
    r = client.post(
        f"/admin/badge-queue/{app_obj.id}/approve",
        data={"note": "OK"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    db.refresh(user)
    db.refresh(app_obj)
    assert user.badge_level == BadgeLevel.RESIDENT
    assert user.primary_region_id == region.id
    assert app_obj.status == BadgeApplicationStatus.APPROVED

    # Step 3: simulate worker dispatching the cleanup job
    import_handlers()
    dispatch(JobKind.EVIDENCE_CLEANUP, {"application_id": app_obj.id})
    db.expire_all()

    assert db.query(BadgeEvidence).filter_by(application_id=app_obj.id).count() == 0
