import base64
import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Job
from app.models._enums import (
    BadgeApplicationStatus,
    BadgeRequestedLevel,
    EvidenceType,
    JobKind,
    JobStatus,
)
from app.models.user import BadgeLevel
from app.tests.factories import (
    AdminUserFactory,
    BadgeApplicationFactory,
    BadgeEvidenceFactory,
    RegionFactory,
    UserFactory,
)


def _login_cookie(user_id: int) -> str:
    secret = get_settings().app_secret_key
    data = base64.b64encode(json.dumps({"user_id": user_id}).encode("utf-8"))
    signer = TimestampSigner(secret)
    return signer.sign(data).decode("utf-8")


def test_queue_requires_admin(db: Session, client: TestClient) -> None:
    user = UserFactory()
    db.commit()
    client.cookies.set("nestory_session", _login_cookie(user.id))
    assert client.get("/admin/badge-queue").status_code == 403


def test_queue_lists_pending(db: Session, client: TestClient) -> None:
    admin = AdminUserFactory()
    applicant = UserFactory()
    region = RegionFactory(slug="yp-q")
    BadgeApplicationFactory(
        user=applicant,
        region=region,
        requested_level=BadgeRequestedLevel.RESIDENT,
    )
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.get("/admin/badge-queue")
    assert r.status_code == 200
    assert "@" + applicant.username in r.text


def test_detail_shows_application(db: Session, client: TestClient) -> None:
    admin = AdminUserFactory()
    applicant = UserFactory()
    region = RegionFactory(sigungu="양평군", slug="yp-d")
    app_obj = BadgeApplicationFactory(
        user=applicant,
        region=region,
        requested_level=BadgeRequestedLevel.RESIDENT,
    )
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.get(f"/admin/badge-queue/{app_obj.id}")
    assert r.status_code == 200
    assert "양평군" in r.text


def test_evidence_download_returns_file(db: Session, client: TestClient, tmp_path) -> None:
    admin = AdminUserFactory()
    applicant = UserFactory()
    region = RegionFactory(slug="yp-e")
    app_obj = BadgeApplicationFactory(
        user=applicant,
        region=region,
        requested_level=BadgeRequestedLevel.RESIDENT,
    )

    # Create real file
    f = tmp_path / "ev.jpg"
    f.write_bytes(b"sample")
    e = BadgeEvidenceFactory(
        application=app_obj,
        evidence_type=EvidenceType.UTILITY_BILL,
        file_path=str(f),
    )
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.get(f"/admin/badge-queue/{app_obj.id}/evidence/{e.id}")
    assert r.status_code == 200
    assert r.content == b"sample"


def test_evidence_download_404_for_other_app(db: Session, client: TestClient) -> None:
    admin = AdminUserFactory()
    applicant = UserFactory()
    region = RegionFactory(slug="yp-x")
    app1 = BadgeApplicationFactory(
        user=applicant,
        region=region,
        requested_level=BadgeRequestedLevel.RESIDENT,
    )
    app2 = BadgeApplicationFactory(
        user=applicant,
        region=region,
        requested_level=BadgeRequestedLevel.REGION_VERIFIED,
    )
    e = BadgeEvidenceFactory(
        application=app1,
        evidence_type=EvidenceType.UTILITY_BILL,
        file_path="/nope",
    )
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(admin.id))
    # Try downloading via wrong app id
    r = client.get(f"/admin/badge-queue/{app2.id}/evidence/{e.id}")
    assert r.status_code == 404


def test_approve_promotes_user_and_schedules_cleanup(db: Session, client: TestClient) -> None:
    admin = AdminUserFactory()
    applicant = UserFactory()
    region = RegionFactory(slug="yp-app")
    app_obj = BadgeApplicationFactory(
        user=applicant,
        region=region,
        requested_level=BadgeRequestedLevel.RESIDENT,
    )
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.post(
        f"/admin/badge-queue/{app_obj.id}/approve",
        data={"note": "확인 완료"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    db.refresh(applicant)
    assert applicant.badge_level == BadgeLevel.RESIDENT

    db.refresh(app_obj)
    assert app_obj.status == BadgeApplicationStatus.APPROVED

    job = db.query(Job).filter_by(kind=JobKind.EVIDENCE_CLEANUP).first()
    assert job is not None
    assert job.payload == {"application_id": app_obj.id}
    assert job.status == JobStatus.QUEUED
    # run_after ~30 days from now
    delta = job.run_after - datetime.now(UTC)
    assert timedelta(days=29) < delta < timedelta(days=31)


def test_reject_keeps_user_and_immediate_cleanup(db: Session, client: TestClient) -> None:
    admin = AdminUserFactory()
    applicant = UserFactory()
    region = RegionFactory(slug="yp-rej")
    app_obj = BadgeApplicationFactory(
        user=applicant,
        region=region,
        requested_level=BadgeRequestedLevel.RESIDENT,
    )
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.post(
        f"/admin/badge-queue/{app_obj.id}/reject",
        data={"note": "증빙 불충분"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    db.refresh(applicant)
    assert applicant.badge_level == BadgeLevel.INTERESTED  # unchanged
    db.refresh(app_obj)
    assert app_obj.status == BadgeApplicationStatus.REJECTED

    job = db.query(Job).filter_by(kind=JobKind.EVIDENCE_CLEANUP).first()
    assert job is not None
    # immediate (run_after in the past or near now)
    assert job.run_after <= datetime.now(UTC) + timedelta(seconds=2)


def test_approve_already_approved_returns_400(db: Session, client: TestClient) -> None:
    admin = AdminUserFactory()
    applicant = UserFactory()
    region = RegionFactory(slug="yp-twice")
    app_obj = BadgeApplicationFactory(
        user=applicant,
        region=region,
        requested_level=BadgeRequestedLevel.RESIDENT,
        status=BadgeApplicationStatus.APPROVED,
    )
    db.commit()
    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.post(f"/admin/badge-queue/{app_obj.id}/approve")
    assert r.status_code == 400
