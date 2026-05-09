"""Badge application & promotion business logic.

Reference: PRD §2.2 (권한 매트릭스), §5.4 (상태 머신), §5.4.1 (재검증·이사·탈거).

All functions accept Session and flush only — caller commits.
"""
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    BadgeApplication,
    BadgeEvidence,
    User,
)
from app.models._enums import (
    AuditAction,
    BadgeApplicationStatus,
    BadgeRequestedLevel,
    EvidenceType,
    NotificationType,
)
from app.models.user import BadgeLevel
from app.services.notifications import create_notification


def submit_application(
    db: Session,
    *,
    user: User,
    requested_level: BadgeRequestedLevel,
    region_id: int,
) -> BadgeApplication:
    """Create a new pending BadgeApplication. Caller must commit."""
    app_obj = BadgeApplication(
        user_id=user.id,
        requested_level=requested_level,
        region_id=region_id,
        status=BadgeApplicationStatus.PENDING,
    )
    db.add(app_obj)
    db.flush()
    return app_obj


def attach_evidence(
    db: Session,
    *,
    application: BadgeApplication,
    evidence_type: EvidenceType,
    file_path: str,
    scheduled_delete_at: datetime | None = None,
) -> BadgeEvidence:
    """Attach a stored evidence file's path to a BadgeApplication."""
    e = BadgeEvidence(
        application_id=application.id,
        evidence_type=evidence_type,
        file_path=file_path,
        scheduled_delete_at=scheduled_delete_at,
    )
    db.add(e)
    db.flush()
    return e


def list_pending(db: Session) -> Sequence[BadgeApplication]:
    """Return all pending applications, oldest first."""
    stmt = (
        select(BadgeApplication)
        .where(BadgeApplication.status == BadgeApplicationStatus.PENDING)
        .order_by(BadgeApplication.applied_at.asc())
    )
    return db.scalars(stmt).all()


def approve(
    db: Session,
    *,
    application: BadgeApplication,
    reviewer: User,
    note: str | None = None,
) -> None:
    """Approve a pending application — promotes user, writes audit + notification.

    Caller must commit. After commit, caller should enqueue an
    `evidence_cleanup` job (30 days delay) — see Task 7.
    """
    if application.status != BadgeApplicationStatus.PENDING:
        raise ValueError(f"Cannot approve application in status {application.status}")

    target_user = db.get(User, application.user_id)
    if target_user is None:
        raise ValueError(f"User {application.user_id} not found")

    # Update application
    application.status = BadgeApplicationStatus.APPROVED
    application.reviewer_id = reviewer.id
    application.review_note = note
    application.reviewed_at = datetime.now(UTC)

    # Promote user
    if application.requested_level == BadgeRequestedLevel.REGION_VERIFIED:
        target_user.badge_level = BadgeLevel.REGION_VERIFIED
        target_user.primary_region_id = application.region_id
    elif application.requested_level == BadgeRequestedLevel.RESIDENT:
        target_user.badge_level = BadgeLevel.RESIDENT
        target_user.primary_region_id = application.region_id
        target_user.resident_verified_at = datetime.now(UTC)
        target_user.resident_revalidated_at = datetime.now(UTC)

    # Audit log
    db.add(
        AuditLog(
            actor_id=reviewer.id,
            action=AuditAction.BADGE_APPROVED,
            target_type="badge_application",
            target_id=application.id,
            note=note,
        )
    )

    # Notify target user
    create_notification(
        db,
        recipient=target_user,
        type=NotificationType.BADGE_APPROVED,
        source_user=reviewer,
        target_type="badge_application",
        target_id=application.id,
    )

    db.flush()


def reject(
    db: Session,
    *,
    application: BadgeApplication,
    reviewer: User,
    note: str,
) -> None:
    """Reject a pending application — writes audit + notification.

    Note is required for rejection (user-facing reason).
    Caller must commit. Evidence files should be cleaned up immediately
    (caller enqueues evidence_cleanup with run_after=now).
    """
    if application.status != BadgeApplicationStatus.PENDING:
        raise ValueError(f"Cannot reject application in status {application.status}")

    target_user = db.get(User, application.user_id)
    if target_user is None:
        raise ValueError(f"User {application.user_id} not found")

    application.status = BadgeApplicationStatus.REJECTED
    application.reviewer_id = reviewer.id
    application.review_note = note
    application.reviewed_at = datetime.now(UTC)

    db.add(
        AuditLog(
            actor_id=reviewer.id,
            action=AuditAction.BADGE_REJECTED,
            target_type="badge_application",
            target_id=application.id,
            note=note,
        )
    )

    create_notification(
        db,
        recipient=target_user,
        type=NotificationType.BADGE_REJECTED,
        source_user=reviewer,
        target_type="badge_application",
        target_id=application.id,
    )

    db.flush()


def evidences_for(db: Session, application_id: int) -> Sequence[BadgeEvidence]:
    """Return all evidence rows for an application."""
    stmt = (
        select(BadgeEvidence)
        .where(BadgeEvidence.application_id == application_id)
        .order_by(BadgeEvidence.uploaded_at.asc())
    )
    return db.scalars(stmt).all()
