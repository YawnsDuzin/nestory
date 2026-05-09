"""Admin moderation service — content hide/unhide + listings.

PRD §9.3 P1 관리자 v1. 신고 resolve는 P2.
"""
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Post, Report, User
from app.models._enums import (
    AuditAction,
    PostStatus,
    ReportStatus,
)
from app.models.user import BadgeLevel

PAGE_SIZE = 30


@dataclass(frozen=True)
class PostListResult:
    posts: list[Post]
    total: int


@dataclass(frozen=True)
class UserListResult:
    users: list[User]
    total: int


@dataclass(frozen=True)
class ReportListResult:
    reports: list[Report]
    total: int


def hide_post(
    db: Session, admin: User, post: Post, reason: str | None = None
) -> Post:
    """Set post.status = HIDDEN + write AuditLog. Idempotent."""
    if post.status != PostStatus.HIDDEN:
        post.status = PostStatus.HIDDEN
    db.add(AuditLog(
        actor_id=admin.id,
        action=AuditAction.CONTENT_HIDDEN,
        target_type="post",
        target_id=post.id,
        note=reason,
    ))
    db.flush()
    return post


def unhide_post(
    db: Session, admin: User, post: Post, reason: str | None = None
) -> Post:
    """Restore post.status = PUBLISHED + write AuditLog."""
    post.status = PostStatus.PUBLISHED
    db.add(AuditLog(
        actor_id=admin.id,
        action=AuditAction.CONTENT_HIDDEN,
        target_type="post",
        target_id=post.id,
        note=f"unhide: {reason}" if reason else "unhide",
    ))
    db.flush()
    return post


def list_posts(
    db: Session,
    *,
    status_filter: Literal["all", "published", "hidden"] = "all",
    page: int = 1,
) -> PostListResult:
    base = select(Post).where(Post.deleted_at.is_(None))
    if status_filter == "published":
        base = base.where(Post.status == PostStatus.PUBLISHED)
    elif status_filter == "hidden":
        base = base.where(Post.status == PostStatus.HIDDEN)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(
            base.order_by(Post.created_at.desc())
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        ).all()
    )
    return PostListResult(posts=rows, total=total)


def list_users(
    db: Session,
    *,
    q: str | None = None,
    badge_level: BadgeLevel | None = None,
    page: int = 1,
) -> UserListResult:
    base = select(User).where(User.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        base = base.where(or_(User.username.ilike(like), User.email.ilike(like)))
    if badge_level is not None:
        base = base.where(User.badge_level == badge_level)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(
            base.order_by(User.created_at.desc())
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        ).all()
    )
    return UserListResult(users=rows, total=total)


def list_pending_reports(db: Session, *, page: int = 1) -> ReportListResult:
    base = select(Report).where(Report.status == ReportStatus.PENDING)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(
            base.order_by(Report.created_at.desc())
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        ).all()
    )
    return ReportListResult(reports=rows, total=total)


__all__ = [
    "PAGE_SIZE",
    "PostListResult",
    "ReportListResult",
    "UserListResult",
    "hide_post",
    "list_pending_reports",
    "list_posts",
    "list_users",
    "unhide_post",
]
