"""add default admin from env

Revision ID: f493042da765
Revises: 8a4f9b3c2d51
Create Date: 2026-05-10 16:34:05.271919

관리자 기본 계정 시드 — 비-prod 환경은 ENV 없이도 자동 생성, prod는 ENV 명시 필수.

읽는 ENV:
- ADMIN_EMAIL              (override — 명시되면 환경 무관 그대로 사용)
- ADMIN_BOOTSTRAP_PASSWORD (override — promote-only는 빈 문자열로 명시)
- ADMIN_USERNAME           (선택, default="admin")
- ADMIN_DISPLAY_NAME       (선택, default="관리자")
- APP_ENV                  (default 적용 분기 — "production"이면 ENV 미설정 시 skip)

동작 (우선순위 위에서 아래):
1. ADMIN_EMAIL + ADMIN_BOOTSTRAP_PASSWORD 모두 명시: argon2 INSERT ON CONFLICT DO UPDATE role='admin'
2. ADMIN_EMAIL만 명시 (password 빈 문자열): 같은 email의 기존 user를 admin으로 승격
3. ADMIN_EMAIL 미설정 + APP_ENV != "production":
   default(admin@nestory.local / admin1234!)로 admin 자동 시드 — 즉시 로그인 가능
4. ADMIN_EMAIL 미설정 + APP_ENV == "production": skip (보안 — 명시 ENV 강제)

downgrade는 마이그레이션 시점의 spec과 동일한 email row 삭제.

prod에서는 반드시 .env에 ADMIN_EMAIL + ADMIN_BOOTSTRAP_PASSWORD를 명시할 것.
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

# 비-prod 환경에서 ADMIN_EMAIL 미설정 시 자동 적용되는 default. prod에서는 사용 안 됨.
_DEV_DEFAULT_EMAIL = "admin@nestory.local"
_DEV_DEFAULT_PASSWORD = "admin1234!"  # noqa: S105 — dev-only default, prod는 ENV 강제


def _read_admin_spec() -> tuple[str, str, str, str] | None:
    """관리자 스펙을 읽는다. prod + ENV 미설정이면 None (skip)."""
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "")
    username = (os.environ.get("ADMIN_USERNAME") or "admin").strip() or "admin"
    display_name = os.environ.get("ADMIN_DISPLAY_NAME") or "관리자"

    if email:
        # 명시 ENV 우선 — 환경 무관 그대로 사용
        return email, password, username, display_name

    app_env = os.environ.get("APP_ENV", "local").strip().lower()
    if app_env == "production":
        # prod + ENV 미설정 → 절대 default admin 만들지 않음 (보안)
        return None

    # 비-prod 환경: dev default로 자동 시드
    return _DEV_DEFAULT_EMAIL, _DEV_DEFAULT_PASSWORD, username, display_name


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
