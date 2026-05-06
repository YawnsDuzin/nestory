import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.services.auth import (
    create_user_with_password,
    find_user_by_email,
    upsert_user_by_kakao_id,
)


def test_create_and_find_user(db: Session) -> None:
    user = create_user_with_password(
        db,
        email="alice@example.com",
        username="alice",
        display_name="앨리스",
        password="horse-staple-42",
    )
    db.commit()

    assert user.id is not None
    assert user.email == "alice@example.com"
    assert user.password_hash is not None and user.password_hash.startswith("$argon2id$")

    found = find_user_by_email(db, "alice@example.com")
    assert found is not None
    assert found.id == user.id


def test_create_user_duplicate_email_raises(db: Session) -> None:
    create_user_with_password(
        db, email="dup@example.com", username="d1", display_name="d", password="x12345"
    )
    db.commit()

    with pytest.raises(IntegrityError):
        create_user_with_password(
            db, email="dup@example.com", username="d2", display_name="d", password="x12345"
        )
        db.commit()


def test_upsert_by_kakao_id_creates_then_updates(db: Session) -> None:
    u1 = upsert_user_by_kakao_id(db, kakao_id="K1", email=None, nickname="닉네임")
    db.commit()
    assert u1.id is not None
    assert u1.kakao_id == "K1"
    assert u1.display_name == "닉네임"
    assert u1.username.startswith("k_")

    u2 = upsert_user_by_kakao_id(db, kakao_id="K1", email="k@kakao.com", nickname="새닉")
    db.commit()
    assert u2.id == u1.id
    assert u2.email == "k@kakao.com"
    assert u2.display_name == "새닉"
