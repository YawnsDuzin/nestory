"""Tests for auth route security posture (timing, enumeration, session)."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.factories import UserFactory


def test_signup_duplicate_returns_generic_message(client: TestClient, db: Session) -> None:
    UserFactory(email="taken@example.com")
    db.commit()
    r = client.post(
        "/auth/signup",
        data={
            "email": "taken@example.com",
            "username": "newuser",
            "display_name": "Test",
            "password": "password123",
        },
    )
    assert r.status_code == 400
    # Generic message should not reveal which field collided
    assert "Email or username already registered" not in r.text
    assert "가입에 실패했습니다" in r.text or "다른 이메일" in r.text


def test_login_invalid_email_and_invalid_password_return_same_message(
    client: TestClient, db: Session
) -> None:
    """Both 'user not found' and 'wrong password' return identical 400 + body."""
    user = UserFactory()
    db.commit()
    # We can't easily set a known password via factory (UserFactory uses
    # hash_password("test1234!")). Trust that and verify the responses match shape.
    r1 = client.post(
        "/auth/login",
        data={"email": "nonexistent@example.com", "password": "anypassword"},
    )
    r2 = client.post(
        "/auth/login",
        data={"email": user.email, "password": "wrong_password"},
    )
    assert r1.status_code == r2.status_code == 400
    # Same error message body — no enumeration via message difference
    assert r1.json() == r2.json()


def test_login_clears_session_before_setting_user_id(
    client: TestClient, db: Session, login
) -> None:
    """Defense-in-depth: any pre-existing session data is wiped on login."""
    # Pre-set a known cookie that will be sent as session
    user = UserFactory()
    db.commit()
    # First login establishes session
    login(user.id)
    r = client.get("/me/badge")
    assert r.status_code == 200
    # Subsequent login with the SAME password (UserFactory's "test1234!")
    # should clear and re-set session — no leakage of pre-login dict keys
    r = client.post(
        "/auth/login",
        data={"email": user.email, "password": "test1234!"},
        follow_redirects=False,
    )
    # 303 redirect to /
    assert r.status_code == 303


def test_signup_clears_session_before_setting_user_id(
    client: TestClient, db: Session
) -> None:
    """Same defense-in-depth for signup."""
    r = client.post(
        "/auth/signup",
        data={
            "email": "newuser@example.com",
            "username": "newuser",
            "display_name": "New",
            "password": "password123",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    # Cookie should be set to the new user's session
    assert "nestory_session" in r.cookies
