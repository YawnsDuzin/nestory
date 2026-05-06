from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.models import Notification, Region, User
from app.models._enums import (
    BadgeApplicationStatus,
    BadgeRequestedLevel,
    EvidenceType,
    NotificationType,
)
from app.models.user import BadgeLevel, UserRole
from app.services.badges import (
    approve,
    attach_evidence,
    evidences_for,
    list_pending,
    reject,
    submit_application,
)


def _seed(db: Session) -> tuple[User, User, Region]:
    ts = int(datetime.now(UTC).timestamp() * 1_000_000)
    applicant = User(
        email=f"a{ts}@example.com",
        username=f"a{ts}",
        display_name="신청자",
        password_hash="x",
    )
    admin = User(
        email=f"adm{ts}@example.com",
        username=f"adm{ts}",
        display_name="관리자",
        password_hash="x",
        role=UserRole.ADMIN,
    )
    region = Region(sido="경기", sigungu="양평군", slug=f"yp-{ts}")
    db.add_all([applicant, admin, region])
    db.flush()
    return applicant, admin, region


def test_submit_application_pending(db: Session) -> None:
    user, _, region = _seed(db)
    app_obj = submit_application(
        db,
        user=user,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
    )
    db.commit()
    assert app_obj.status == BadgeApplicationStatus.PENDING
    assert app_obj.user_id == user.id


def test_attach_evidence(db: Session) -> None:
    user, _, region = _seed(db)
    app_obj = submit_application(
        db, user=user, requested_level=BadgeRequestedLevel.RESIDENT, region_id=region.id
    )
    e = attach_evidence(
        db,
        application=app_obj,
        evidence_type=EvidenceType.UTILITY_BILL,
        file_path="/private/evidence/2026/05/abc.jpg",
    )
    db.commit()
    assert e.id is not None
    assert e.evidence_type == EvidenceType.UTILITY_BILL


def test_list_pending_orders_oldest_first(db: Session) -> None:
    u1, _, region = _seed(db)
    submit_application(
        db, user=u1, requested_level=BadgeRequestedLevel.RESIDENT, region_id=region.id
    )
    submit_application(
        db, user=u1, requested_level=BadgeRequestedLevel.REGION_VERIFIED, region_id=region.id
    )
    db.commit()
    pending = list_pending(db)
    assert len(pending) == 2
    assert pending[0].requested_level == BadgeRequestedLevel.RESIDENT  # 먼저 신청


def test_approve_resident_promotes_user(db: Session) -> None:
    user, admin_user, region = _seed(db)
    app_obj = submit_application(
        db, user=user, requested_level=BadgeRequestedLevel.RESIDENT, region_id=region.id
    )
    approve(db, application=app_obj, reviewer=admin_user, note="확인 완료")
    db.commit()

    db.refresh(user)
    assert user.badge_level == BadgeLevel.RESIDENT
    assert user.primary_region_id == region.id
    assert user.resident_verified_at is not None
    assert user.resident_revalidated_at is not None
    assert app_obj.status == BadgeApplicationStatus.APPROVED
    assert app_obj.reviewer_id == admin_user.id
    assert app_obj.reviewed_at is not None


def test_approve_region_verified_only(db: Session) -> None:
    user, admin_user, region = _seed(db)
    app_obj = submit_application(
        db,
        user=user,
        requested_level=BadgeRequestedLevel.REGION_VERIFIED,
        region_id=region.id,
    )
    approve(db, application=app_obj, reviewer=admin_user)
    db.commit()
    db.refresh(user)
    assert user.badge_level == BadgeLevel.REGION_VERIFIED
    assert user.resident_verified_at is None  # resident 가 아니므로 미설정


def test_approve_creates_audit_and_notification(db: Session) -> None:
    user, admin_user, region = _seed(db)
    app_obj = submit_application(
        db, user=user, requested_level=BadgeRequestedLevel.RESIDENT, region_id=region.id
    )
    approve(db, application=app_obj, reviewer=admin_user)
    db.commit()

    notifs = db.query(Notification).filter_by(user_id=user.id).all()
    assert len(notifs) == 1
    assert notifs[0].type == NotificationType.BADGE_APPROVED


def test_reject_blocks_promotion(db: Session) -> None:
    user, admin_user, region = _seed(db)
    app_obj = submit_application(
        db, user=user, requested_level=BadgeRequestedLevel.RESIDENT, region_id=region.id
    )
    reject(db, application=app_obj, reviewer=admin_user, note="증빙 불충분")
    db.commit()

    db.refresh(user)
    assert user.badge_level == BadgeLevel.INTERESTED  # 미변경
    assert app_obj.status == BadgeApplicationStatus.REJECTED
    assert app_obj.review_note == "증빙 불충분"


def test_approve_rejects_non_pending(db: Session) -> None:
    user, admin_user, region = _seed(db)
    app_obj = submit_application(
        db, user=user, requested_level=BadgeRequestedLevel.RESIDENT, region_id=region.id
    )
    approve(db, application=app_obj, reviewer=admin_user)
    db.commit()
    with pytest.raises(ValueError, match="Cannot approve"):
        approve(db, application=app_obj, reviewer=admin_user)


def test_evidences_for_returns_attached(db: Session) -> None:
    user, _, region = _seed(db)
    app_obj = submit_application(
        db, user=user, requested_level=BadgeRequestedLevel.RESIDENT, region_id=region.id
    )
    attach_evidence(
        db, application=app_obj, evidence_type=EvidenceType.UTILITY_BILL, file_path="/p/1.jpg"
    )
    attach_evidence(
        db, application=app_obj, evidence_type=EvidenceType.CONTRACT, file_path="/p/2.jpg"
    )
    db.commit()
    es = evidences_for(db, app_obj.id)
    assert len(es) == 2
