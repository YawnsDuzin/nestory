"""Tests for migration f493042da765 (default admin from env)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.models import User
from app.models.user import UserRole
from app.tests.factories import UserFactory

_MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "db" / "migrations" / "versions" / "f493042da765_add_default_admin_from_env.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("_mig_default_admin", _MIGRATION_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mig():
    return _load_migration_module()


def test_read_admin_spec_returns_none_when_email_missing(mig, monkeypatch) -> None:
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    assert mig._read_admin_spec() is None


def test_read_admin_spec_normalizes_email_and_defaults(mig, monkeypatch) -> None:
    monkeypatch.setenv("ADMIN_EMAIL", "  Owner@Example.COM ")
    monkeypatch.delenv("ADMIN_BOOTSTRAP_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_DISPLAY_NAME", raising=False)

    spec = mig._read_admin_spec()
    assert spec == ("owner@example.com", "", "admin", "관리자")


def test_apply_admin_creates_new_user_with_password(mig, db: Session) -> None:
    spec = ("first-admin@example.com", "S3cretPass!", "first_admin", "최고관리자")
    mig._apply_admin(db.connection(), spec)
    db.commit()

    user = db.query(User).filter_by(email="first-admin@example.com").one()
    assert user.role == UserRole.ADMIN
    assert user.username == "first_admin"
    assert user.display_name == "최고관리자"
    assert user.password_hash and user.password_hash.startswith("$argon2")


def test_apply_admin_promotes_existing_user_when_password_present(
    mig, db: Session,
) -> None:
    existing = UserFactory(email="ops@example.com", username="ops", display_name="Ops")
    db.commit()
    assert existing.role == UserRole.USER
    original_hash = existing.password_hash

    spec = ("ops@example.com", "newpass-but-ignored", "different_username", "다른이름")
    mig._apply_admin(db.connection(), spec)
    db.commit()
    db.refresh(existing)

    assert existing.role == UserRole.ADMIN
    # ON CONFLICT DO UPDATE SET role='admin' — 비밀번호·username·display_name은 보존
    assert existing.password_hash == original_hash
    assert existing.username == "ops"
    assert existing.display_name == "Ops"


def test_apply_admin_promote_only_when_password_blank(mig, db: Session) -> None:
    existing = UserFactory(email="ops2@example.com")
    db.commit()
    assert existing.role == UserRole.USER

    spec = ("ops2@example.com", "", "ignored", "ignored")
    mig._apply_admin(db.connection(), spec)
    db.commit()
    db.refresh(existing)

    assert existing.role == UserRole.ADMIN


def test_apply_admin_promote_only_no_user_is_noop(mig, db: Session) -> None:
    """password 미제공 + email로 매칭되는 user 없음 → 조용히 no-op."""
    spec = ("nobody@example.com", "", "x", "x")
    mig._apply_admin(db.connection(), spec)
    db.commit()

    assert db.query(User).filter_by(email="nobody@example.com").one_or_none() is None


def test_apply_admin_already_admin_unchanged(mig, db: Session) -> None:
    from app.tests.factories import AdminUserFactory

    admin = AdminUserFactory(email="root@example.com")
    db.commit()
    original_hash = admin.password_hash

    spec = ("root@example.com", "", "ignored", "ignored")
    mig._apply_admin(db.connection(), spec)
    db.commit()
    db.refresh(admin)

    assert admin.role == UserRole.ADMIN
    assert admin.password_hash == original_hash
