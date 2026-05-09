"""Integration tests for /admin/content routes.

NOTE: Requires running Postgres.
"""
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.models._enums import AuditAction, PostStatus
from app.tests.factories import (
    AdminUserFactory,
    ResidentUserFactory,
    ReviewPostFactory,
    UserFactory,
)


def test_content_list_requires_admin(client: TestClient, db: Session, login) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.get("/admin/content")
    assert r.status_code == 403


def test_content_list_admin_renders(client: TestClient, db: Session, login) -> None:
    admin = AdminUserFactory()
    author = ResidentUserFactory()
    ReviewPostFactory(author=author, status=PostStatus.PUBLISHED)
    db.commit()
    login(admin.id)
    r = client.get("/admin/content")
    assert r.status_code == 200
    assert "콘텐츠" in r.text


def test_content_filter_hidden(client: TestClient, db: Session, login) -> None:
    admin = AdminUserFactory()
    author = ResidentUserFactory()
    ReviewPostFactory(author=author, status=PostStatus.PUBLISHED, title="VISIBLE_POST")
    ReviewPostFactory(author=author, status=PostStatus.HIDDEN, title="HIDDEN_POST")
    db.commit()
    login(admin.id)
    r = client.get("/admin/content?status_filter=hidden")
    assert r.status_code == 200
    assert "HIDDEN_POST" in r.text
    assert "VISIBLE_POST" not in r.text


def test_hide_post_redirects_and_writes_audit(
    client: TestClient, db: Session, login
) -> None:
    admin = AdminUserFactory()
    author = ResidentUserFactory()
    post = ReviewPostFactory(author=author, status=PostStatus.PUBLISHED)
    db.commit()
    login(admin.id)
    r = client.post(
        f"/admin/content/{post.id}/hide",
        data={"reason": "test"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(post)
    assert post.status == PostStatus.HIDDEN
    audits = list(
        db.scalars(
            select(AuditLog).where(
                AuditLog.target_id == post.id,
                AuditLog.action == AuditAction.CONTENT_HIDDEN,
            )
        ).all()
    )
    assert len(audits) >= 1


def test_unhide_post_restores(client: TestClient, db: Session, login) -> None:
    admin = AdminUserFactory()
    author = ResidentUserFactory()
    post = ReviewPostFactory(author=author, status=PostStatus.HIDDEN)
    db.commit()
    login(admin.id)
    r = client.post(
        f"/admin/content/{post.id}/unhide", follow_redirects=False
    )
    assert r.status_code == 303
    db.refresh(post)
    assert post.status == PostStatus.PUBLISHED


def test_hide_unknown_post_returns_404(
    client: TestClient, db: Session, login
) -> None:
    admin = AdminUserFactory()
    db.commit()
    login(admin.id)
    r = client.post("/admin/content/99999/hide")
    assert r.status_code == 404
