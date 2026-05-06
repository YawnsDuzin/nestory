from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import BadgeApplication, BadgeEvidence, Region, User
from app.models._enums import (
    BadgeApplicationStatus,
    BadgeRequestedLevel,
    EvidenceType,
)


def _seed(db: Session) -> tuple[User, Region]:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    r = Region(sido="경기", sigungu="양평군", slug=f"yp-{u.username}")
    db.add_all([u, r])
    db.flush()
    return u, r


def test_create_resident_application_pending(db: Session) -> None:
    u, r = _seed(db)
    app = BadgeApplication(
        user_id=u.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=r.id,
    )
    db.add(app)
    db.flush()
    assert app.status == BadgeApplicationStatus.PENDING
    assert app.applied_at is not None
    assert app.reviewed_at is None


def test_attach_evidence_with_scheduled_delete(db: Session) -> None:
    u, r = _seed(db)
    app = BadgeApplication(
        user_id=u.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=r.id,
    )
    db.add(app)
    db.flush()
    delete_at = datetime.now(UTC) + timedelta(days=30)
    e = BadgeEvidence(
        application_id=app.id,
        evidence_type=EvidenceType.UTILITY_BILL,
        file_path="/private/evidence/2026/05/abc.jpg",
        scheduled_delete_at=delete_at,
    )
    db.add(e)
    db.flush()
    assert e.evidence_type == EvidenceType.UTILITY_BILL
    assert e.scheduled_delete_at is not None
