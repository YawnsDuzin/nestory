"""add default admin from env

Revision ID: f493042da765
Revises: 8a4f9b3c2d51
Create Date: 2026-05-10 16:34:05.271919

ENV 변수 기반 관리자 기본 계정 시드.

읽는 ENV:
- ADMIN_EMAIL              (필수, 미설정 시 마이그레이션 no-op)
- ADMIN_BOOTSTRAP_PASSWORD (선택, 미설정 시 promote-only — 기존 계정 role만 admin으로 승격)
- ADMIN_USERNAME           (선택, default="admin")
- ADMIN_DISPLAY_NAME       (선택, default="관리자")

동작:
- ADMIN_EMAIL 미설정: skip (테스트·CI·dev 환경 안전)
- ADMIN_BOOTSTRAP_PASSWORD 미설정: 같은 email의 기존 user를 admin으로 승격만
- 둘 다 설정: argon2 hash로 INSERT ... ON CONFLICT (email) DO UPDATE role='admin'

downgrade는 ADMIN_EMAIL 일치 row 삭제. ENV 미설정 시 no-op.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f493042da765"
down_revision: str | Sequence[str] | None = "8a4f9b3c2d51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _read_admin_spec() -> tuple[str, str, str, str] | None:
    """ENV에서 관리자 스펙을 읽는다. ADMIN_EMAIL 미설정 시 None."""
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    if not email:
        return None
    password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "")
    username = os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin"
    display_name = os.environ.get("ADMIN_DISPLAY_NAME", "관리자")
    return email, password, username, display_name


def _apply_admin(conn: sa.Connection, spec: tuple[str, str, str, str]) -> None:
    email, password, username, display_name = spec

    if not password:
        # password 미제공 → 기존 사용자 role만 승격 (없으면 no-op)
        conn.execute(
            sa.text(
                "UPDATE users SET role='admin' "
                "WHERE email = :email AND role <> 'admin' AND deleted_at IS NULL"
            ),
            {"email": email},
        )
        return

    from argon2 import PasswordHasher

    pwhash = PasswordHasher().hash(password)
    conn.execute(
        sa.text(
            """
            INSERT INTO users (email, username, display_name, password_hash, role, badge_level)
            VALUES (:email, :username, :display_name, :pwhash, 'admin', 'interested')
            ON CONFLICT (email) DO UPDATE SET role = 'admin'
            """
        ),
        {
            "email": email,
            "username": username,
            "display_name": display_name,
            "pwhash": pwhash,
        },
    )


def upgrade() -> None:
    spec = _read_admin_spec()
    if spec is None:
        return
    _apply_admin(op.get_bind(), spec)


def downgrade() -> None:
    spec = _read_admin_spec()
    if spec is None:
        return
    email = spec[0]
    op.get_bind().execute(
        sa.text("DELETE FROM users WHERE email = :email"),
        {"email": email},
    )
