"""ENV ADMIN_EMAIL로 지정된 계정을 admin 역할로 승격.

회원가입은 별도로 해야 하며, 이 스크립트는 기존 사용자의 role만 바꾼다.
OI-5 잠정: 초기 관리자는 본인 1명.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def promote_admin(db: Session, *, email: str) -> User:
    user = db.query(User).filter(User.email == email.lower().strip()).one_or_none()
    if user is None:
        raise LookupError(f"No user found with email {email!r}")
    user.role = UserRole.ADMIN
    db.flush()
    return user


def main() -> None:
    settings = get_settings()
    if not settings.admin_email:
        raise SystemExit("ADMIN_EMAIL env var is empty")

    db = SessionLocal()
    try:
        user = promote_admin(db, email=settings.admin_email)
        db.commit()
        print(f"Promoted {user.email} (id={user.id}) to admin.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
