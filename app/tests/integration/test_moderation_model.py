from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Announcement, AuditLog, Report, User
from app.models._enums import AuditAction, ReportReason, ReportStatus


def _make_user(db: Session) -> User:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    db.add(u)
    db.flush()
    return u


def test_create_report_pending(db: Session) -> None:
    u = _make_user(db)
    r = Report(
        reporter_id=u.id,
        target_type="post",
        target_id=999,
        reason=ReportReason.AD,
        detail="홍보성 내용 의심",
    )
    db.add(r)
    db.flush()
    assert r.status == ReportStatus.PENDING


def test_audit_log_action(db: Session) -> None:
    u = _make_user(db)
    a = AuditLog(
        actor_id=u.id,
        action=AuditAction.BADGE_APPROVED,
        target_type="badge_application",
        target_id=1,
    )
    db.add(a)
    db.flush()
    assert a.action == AuditAction.BADGE_APPROVED
    assert a.created_at is not None


def test_pinned_announcement(db: Session) -> None:
    u = _make_user(db)
    a = Announcement(
        author_id=u.id,
        title="베타 오픈 안내",
        body="2026-06-01부터 양평 시범 시작",
        pinned=True,
    )
    db.add(a)
    db.flush()
    assert a.pinned is True
