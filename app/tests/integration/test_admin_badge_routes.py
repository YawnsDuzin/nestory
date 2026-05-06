import base64
import json
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BadgeApplication, BadgeEvidence, Job, Region, User
from app.models._enums import (
    BadgeApplicationStatus,
    BadgeRequestedLevel,
    EvidenceType,
    JobKind,
    JobStatus,
)
from app.models.user import BadgeLevel, UserRole


def _login_cookie(user_id: int) -> str:
    secret = get_settings().app_secret_key
    data = base64.b64encode(json.dumps({"user_id": user_id}).encode("utf-8"))
    signer = TimestampSigner(secret)
    return signer.sign(data).decode("utf-8")


def _make_user(db: Session, *, role: UserRole = UserRole.USER) -> User:
    ts = int(datetime.now(UTC).timestamp() * 1_000_000)
    u = User(
        email=f"t{ts}@example.com",
        username=f"u{ts}",
        display_name="테스터",
        password_hash="x",
        role=role,
    )
    db.add(u)
    db.flush()
    db.commit()
    return u


def test_queue_requires_admin(db: Session, client: TestClient) -> None:
    user = _make_user(db, role=UserRole.USER)
    client.cookies.set("nestory_session", _login_cookie(user.id))
    assert client.get("/admin/badge-queue").status_code == 403


def test_queue_lists_pending(db: Session, client: TestClient) -> None:
    admin = _make_user(db, role=UserRole.ADMIN)
    applicant = _make_user(db, role=UserRole.USER)
    region = Region(sido="경기", sigungu="양평군", slug="yp-q")
    db.add(region)
    db.commit()
    db.add(
        BadgeApplication(
            user_id=applicant.id,
            requested_level=BadgeRequestedLevel.RESIDENT,
            region_id=region.id,
        )
    )
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.get("/admin/badge-queue")
    assert r.status_code == 200
    assert "@" + applicant.username in r.text


def test_detail_shows_application(db: Session, client: TestClient) -> None:
    admin = _make_user(db, role=UserRole.ADMIN)
    applicant = _make_user(db, role=UserRole.USER)
    region = Region(sido="경기", sigungu="양평군", slug="yp-d")
    db.add(region)
    db.commit()
    app_obj = BadgeApplication(
        user_id=applicant.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
    )
    db.add(app_obj)
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.get(f"/admin/badge-queue/{app_obj.id}")
    assert r.status_code == 200
    assert "양평군" in r.text


def test_evidence_download_returns_file(db: Session, client: TestClient, tmp_path) -> None:
    admin = _make_user(db, role=UserRole.ADMIN)
    applicant = _make_user(db, role=UserRole.USER)
    region = Region(sido="경기", sigungu="양평군", slug="yp-e")
    db.add(region)
    db.commit()
    app_obj = BadgeApplication(
        user_id=applicant.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
    )
    db.add(app_obj)
    db.commit()

    # Create real file
    f = tmp_path / "ev.jpg"
    f.write_bytes(b"sample")
    e = BadgeEvidence(
        application_id=app_obj.id,
        evidence_type=EvidenceType.UTILITY_BILL,
        file_path=str(f),
    )
    db.add(e)
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.get(f"/admin/badge-queue/{app_obj.id}/evidence/{e.id}")
    assert r.status_code == 200
    assert r.content == b"sample"


def test_evidence_download_404_for_other_app(db: Session, client: TestClient) -> None:
    admin = _make_user(db, role=UserRole.ADMIN)
    applicant = _make_user(db, role=UserRole.USER)
    region = Region(sido="경기", sigungu="양평군", slug="yp-x")
    db.add(region)
    db.commit()
    app1 = BadgeApplication(
        user_id=applicant.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
    )
    app2 = BadgeApplication(
        user_id=applicant.id,
        requested_level=BadgeRequestedLevel.REGION_VERIFIED,
        region_id=region.id,
    )
    db.add_all([app1, app2])
    db.commit()
    e = BadgeEvidence(
        application_id=app1.id,
        evidence_type=EvidenceType.UTILITY_BILL,
        file_path="/nope",
    )
    db.add(e)
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(admin.id))
    # Try downloading via wrong app id
    r = client.get(f"/admin/badge-queue/{app2.id}/evidence/{e.id}")
    assert r.status_code == 404


def test_approve_promotes_user_and_schedules_cleanup(db: Session, client: TestClient) -> None:
    admin = _make_user(db, role=UserRole.ADMIN)
    applicant = _make_user(db, role=UserRole.USER)
    region = Region(sido="경기", sigungu="양평군", slug="yp-app")
    db.add(region)
    db.commit()
    app_obj = BadgeApplication(
        user_id=applicant.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
    )
    db.add(app_obj)
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
    admin = _make_user(db, role=UserRole.ADMIN)
    applicant = _make_user(db, role=UserRole.USER)
    region = Region(sido="경기", sigungu="양평군", slug="yp-rej")
    db.add(region)
    db.commit()
    app_obj = BadgeApplication(
        user_id=applicant.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
    )
    db.add(app_obj)
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
    admin = _make_user(db, role=UserRole.ADMIN)
    applicant = _make_user(db, role=UserRole.USER)
    region = Region(sido="경기", sigungu="양평군", slug="yp-twice")
    db.add(region)
    db.commit()
    app_obj = BadgeApplication(
        user_id=applicant.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
        status=BadgeApplicationStatus.APPROVED,
    )
    db.add(app_obj)
    db.commit()
    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.post(f"/admin/badge-queue/{app_obj.id}/approve")
    assert r.status_code == 400
