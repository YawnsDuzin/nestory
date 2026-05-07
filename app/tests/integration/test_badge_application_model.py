from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models._enums import (
    BadgeApplicationStatus,
    BadgeRequestedLevel,
    EvidenceType,
)
from app.tests.factories import BadgeApplicationFactory, BadgeEvidenceFactory


def test_create_resident_application_pending(db: Session) -> None:
    app = BadgeApplicationFactory(requested_level=BadgeRequestedLevel.RESIDENT)
    assert app.status == BadgeApplicationStatus.PENDING
    assert app.applied_at is not None
    assert app.reviewed_at is None


def test_attach_evidence_with_scheduled_delete(db: Session) -> None:
    app = BadgeApplicationFactory(requested_level=BadgeRequestedLevel.RESIDENT)
    delete_at = datetime.now(UTC) + timedelta(days=30)
    e = BadgeEvidenceFactory(
        application=app,
        evidence_type=EvidenceType.UTILITY_BILL,
        file_path="/private/evidence/2026/05/abc.jpg",
        scheduled_delete_at=delete_at,
    )
    assert e.evidence_type == EvidenceType.UTILITY_BILL
    assert e.scheduled_delete_at is not None
