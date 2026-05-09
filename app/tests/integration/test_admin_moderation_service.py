"""Tests for admin_moderation service.

NOTE: Requires running Postgres.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.models._enums import AuditAction, PostStatus, ReportStatus
from app.models.user import BadgeLevel
from app.services import admin_moderation as ams
from app.tests.factories import (
    AdminUserFactory,
    ReportFactory,
    ResidentUserFactory,
    ReviewPostFactory,
    UserFactory,
)


def test_hide_post_sets_status_and_audits(db: Session) -> None:
    admin = AdminUserFactory()
    author = ResidentUserFactory()
    post = ReviewPostFactory(author=author, status=PostStatus.PUBLISHED)
    db.flush()

    ams.hide_post(db, admin, post, reason="ad spam")
    assert post.status == PostStatus.HIDDEN
    audits = list(
        db.scalars(
            select(AuditLog).where(
                AuditLog.target_id == post.id,
                AuditLog.action == AuditAction.CONTENT_HIDDEN,
            )
        ).all()
    )
    assert len(audits) == 1
    assert audits[0].actor_id == admin.id
    assert audits[0].note == "ad spam"


def test_hide_post_idempotent(db: Session) -> None:
    admin = AdminUserFactory()
    author = ResidentUserFactory()
    post = ReviewPostFactory(author=author, status=PostStatus.HIDDEN)
    db.flush()
    ams.hide_post(db, admin, post)
    assert post.status == PostStatus.HIDDEN


def test_unhide_post_restores_status(db: Session) -> None:
    admin = AdminUserFactory()
    author = ResidentUserFactory()
    post = ReviewPostFactory(author=author, status=PostStatus.HIDDEN)
    db.flush()
    ams.unhide_post(db, admin, post, reason="false positive")
    assert post.status == PostStatus.PUBLISHED
    audits = list(
        db.scalars(
            select(AuditLog).where(
                AuditLog.target_id == post.id,
                AuditLog.action == AuditAction.CONTENT_HIDDEN,
            )
        ).all()
    )
    assert any("unhide" in (a.note or "") for a in audits)


def test_list_posts_filters_by_status(db: Session) -> None:
    author = ResidentUserFactory()
    p_pub = ReviewPostFactory(author=author, status=PostStatus.PUBLISHED)
    p_hidden = ReviewPostFactory(author=author, status=PostStatus.HIDDEN)
    db.flush()

    res_all = ams.list_posts(db, status_filter="all")
    assert res_all.total == 2
    res_pub = ams.list_posts(db, status_filter="published")
    assert res_pub.total == 1
    assert res_pub.posts[0].id == p_pub.id
    res_hidden = ams.list_posts(db, status_filter="hidden")
    assert res_hidden.total == 1
    assert res_hidden.posts[0].id == p_hidden.id


def test_list_users_searches_username(db: Session) -> None:
    UserFactory(username="alice123", email="a@x.com")
    UserFactory(username="bob456", email="b@x.com")
    db.flush()
    res = ams.list_users(db, q="alice")
    assert res.total == 1
    assert res.users[0].username == "alice123"


def test_list_users_filters_by_badge_level(db: Session) -> None:
    UserFactory(badge_level=BadgeLevel.INTERESTED)
    ResidentUserFactory()
    db.flush()
    res = ams.list_users(db, badge_level=BadgeLevel.RESIDENT)
    assert res.total == 1
    assert res.users[0].badge_level == BadgeLevel.RESIDENT


def test_list_pending_reports(db: Session) -> None:
    reporter = UserFactory()
    ReportFactory(reporter=reporter, status=ReportStatus.PENDING)
    ReportFactory(reporter=reporter, status=ReportStatus.RESOLVED)
    db.flush()
    res = ams.list_pending_reports(db)
    assert res.total == 1
    assert res.reports[0].status == ReportStatus.PENDING
