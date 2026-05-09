"""In-app notifications service — single source of truth for notification lifecycle.

PRD §9.3 P1 종료 기준 알림. 카카오 알림톡 / 이메일 / Web Push는 P2.
"""
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import Notification, User
from app.models._enums import NotificationType

PAGE_SIZE = 30
DROPDOWN_LIMIT = 5


@dataclass(frozen=True)
class NotificationView:
    notification: Notification
    label: str
    link: str
    source_username: str | None


def create_notification(
    db: Session,
    *,
    recipient: User,
    type: NotificationType,
    source_user: User | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
) -> Notification | None:
    """Create a notification. Self-trigger (source==recipient) is skipped."""
    if source_user is not None and source_user.id == recipient.id:
        return None
    notif = Notification(
        user_id=recipient.id,
        type=type,
        source_user_id=source_user.id if source_user else None,
        target_type=target_type,
        target_id=target_id,
    )
    db.add(notif)
    db.flush()
    return notif


def unread_count(db: Session, user: User) -> int:
    return db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        )
    ) or 0


def recent_for_dropdown(
    db: Session, user: User, limit: int = DROPDOWN_LIMIT
) -> list[NotificationView]:
    rows = list(
        db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        ).all()
    )
    return [_to_view(db, n) for n in rows]


def list_paginated(
    db: Session, user: User, *, page: int = 1
) -> tuple[list[NotificationView], int]:
    base = select(Notification).where(Notification.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(
            base.order_by(Notification.created_at.desc())
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        ).all()
    )
    return [_to_view(db, n) for n in rows], total


def mark_read(db: Session, user: User, notif_id: int) -> Notification | None:
    """Soup-test ownership before marking. Returns None if not found or not owner."""
    notif = db.get(Notification, notif_id)
    if notif is None or notif.user_id != user.id:
        return None
    if not notif.is_read:
        notif.is_read = True
        db.flush()
    return notif


def mark_all_read(db: Session, user: User) -> int:
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    return result.rowcount or 0


def _to_view(db: Session, notif: Notification) -> NotificationView:
    source_username: str | None = None
    if notif.source_user_id:
        src = db.get(User, notif.source_user_id)
        source_username = src.username if src else None
    return NotificationView(
        notification=notif,
        label=_format_label(notif, source_username),
        link=_resolve_link(notif),
        source_username=source_username,
    )


def _format_label(notif: Notification, source_username: str | None) -> str:
    src = f"@{source_username}" if source_username else "운영진"
    if notif.type == NotificationType.BADGE_APPROVED:
        return "🎉 실거주자 배지가 승인되었습니다."
    if notif.type == NotificationType.BADGE_REJECTED:
        return "❌ 배지 신청이 반려되었습니다. 사유를 확인해주세요."
    if notif.type == NotificationType.POST_COMMENT:
        return f"{src}님이 회원님 글에 댓글을 달았습니다."
    if notif.type == NotificationType.JOURNEY_NEW_EPISODE:
        return f"{src}님이 새 에피소드를 게시했습니다."
    if notif.type == NotificationType.QUESTION_ANSWERED:
        return f"{src}님이 회원님 질문에 답변했습니다."
    if notif.type == NotificationType.SYSTEM:
        return "운영진 공지가 도착했습니다."
    return "새 알림이 있습니다."


def _resolve_link(notif: Notification) -> str:
    if notif.target_type == "badge_application":
        return "/me/badge"
    if notif.target_type == "post" and notif.target_id is not None:
        return f"/post/{notif.target_id}"
    return "/notifications"


__all__ = [
    "DROPDOWN_LIMIT",
    "NotificationView",
    "PAGE_SIZE",
    "create_notification",
    "list_paginated",
    "mark_all_read",
    "mark_read",
    "recent_for_dropdown",
    "unread_count",
]
