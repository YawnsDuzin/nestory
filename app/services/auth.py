import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy.orm import Session

from app.models.user import User

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    if not password or not password.strip():
        raise ValueError("password must be non-blank")
    return _hasher.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        _hasher.verify(hashed, password)
        return True
    except VerifyMismatchError:
        return False


def create_user_with_password(
    db: Session,
    *,
    email: str,
    username: str,
    display_name: str,
    password: str,
) -> User:
    user = User(
        email=email.lower().strip(),
        username=username.strip(),
        display_name=display_name.strip(),
        password_hash=hash_password(password),
    )
    db.add(user)
    db.flush()
    return user


def find_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.lower().strip()).one_or_none()


def upsert_user_by_kakao_id(
    db: Session,
    *,
    kakao_id: str,
    email: str | None,
    nickname: str | None,
) -> User:
    user = db.query(User).filter(User.kakao_id == kakao_id).one_or_none()
    if user is None:
        placeholder_email = email or f"kakao_{kakao_id}@nestory.local"
        username = f"k_{kakao_id[:6]}_{secrets.token_hex(3)}"
        user = User(
            email=placeholder_email.lower(),
            kakao_id=kakao_id,
            username=username,
            display_name=(nickname or "카카오 사용자")[:64],
        )
        db.add(user)
        db.flush()
        return user

    if email:
        user.email = email.lower()
    if nickname:
        user.display_name = nickname[:64]
    db.flush()
    return user
