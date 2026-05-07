from sqlalchemy.orm import Session

from app.models._enums import AuditAction, ReportReason, ReportStatus
from app.tests.factories import AnnouncementFactory, AuditLogFactory, ReportFactory


def test_create_report_pending(db: Session) -> None:
    r = ReportFactory(
        target_type="post",
        target_id=999,
        reason=ReportReason.AD,
        detail="홍보성 내용 의심",
    )
    assert r.status == ReportStatus.PENDING


def test_audit_log_action(db: Session) -> None:
    a = AuditLogFactory(
        action=AuditAction.BADGE_APPROVED,
        target_type="badge_application",
        target_id=1,
    )
    assert a.action == AuditAction.BADGE_APPROVED
    assert a.created_at is not None


def test_pinned_announcement(db: Session) -> None:
    a = AnnouncementFactory(
        title="베타 오픈 안내",
        body="2026-06-01부터 양평 시범 시작",
        pinned=True,
    )
    assert a.pinned is True
