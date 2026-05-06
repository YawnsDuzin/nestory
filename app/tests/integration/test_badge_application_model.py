from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import BadgeApplication, BadgeEvidence
from app.models._enums import (
    BadgeApplicationStatus,
    BadgeRequestedLevel,
    EvidenceType,
)
from app.tests.factories import RegionFactory, UserFactory


def test_create_resident_application_pending(db: Session) -> None:
    u = UserFactory()
    r = RegionFactory()
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
    u = UserFactory()
    r = RegionFactory()
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
