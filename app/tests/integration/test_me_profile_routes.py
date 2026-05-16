"""Integration tests for /me/profile* routes — TestClient + factory-boy."""
from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.services import auth as auth_service
from app.tests.factories import RegionFactory, UserFactory


def _png_bytes(size: tuple[int, int] = (80, 80)) -> bytes:
    """Generate a small valid PNG for upload tests."""
    buf = io.BytesIO()
    PILImage.new("RGB", size, color=(120, 200, 130)).save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. Anonymous access — every /me/profile* should redirect or 401
# ---------------------------------------------------------------------------


def test_anonymous_get_profile_redirects_or_401(client: TestClient) -> None:
    r = client.get("/me/profile", follow_redirects=False)
    assert r.status_code in (302, 303, 307, 401)


# ---------------------------------------------------------------------------
# 2. GET /me/profile — logged-in user sees form prefilled
# ---------------------------------------------------------------------------


def test_logged_in_get_profile_renders_form(client: TestClient, db: Session, login) -> None:
    user = UserFactory(display_name="홍길동", bio="자기소개")
    db.commit()
    login(user.id)

    r = client.get("/me/profile")
    assert r.status_code == 200
    assert "프로필 편집" in r.text
    assert "홍길동" in r.text
    assert "자기소개" in r.text


# ---------------------------------------------------------------------------
# 3. POST /me/profile happy + invalid region
# ---------------------------------------------------------------------------


def test_post_profile_happy_saves_basic_fields(client: TestClient, db: Session, login) -> None:
    region = RegionFactory(slug="profile-route-region")
    user = UserFactory(display_name="원래", bio=None)
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile",
        data={
            "display_name": "새이름",
            "bio": "새 자기소개",
            "primary_region_id": str(region.id),
            "notify_email_enabled": "1",
            "notify_kakao_enabled": "1",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(user)
    assert user.display_name == "새이름"
    assert user.bio == "새 자기소개"
    assert user.primary_region_id == region.id
    assert user.notify_email_enabled is True
    assert user.notify_kakao_enabled is True


def test_post_profile_unchecked_notify_becomes_false(
    client: TestClient, db: Session, login
) -> None:
    """체크박스 미전송 시 False로 저장 (HTML form 표준)."""
    user = UserFactory(notify_email_enabled=True, notify_kakao_enabled=True)
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile",
        data={
            "display_name": user.display_name,
            "bio": "",
            "primary_region_id": "",
            # notify_* 필드 의도적 미전송
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(user)
    assert user.notify_email_enabled is False
    assert user.notify_kakao_enabled is False


def test_post_profile_invalid_region_flashes(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile",
        data={
            "display_name": user.display_name,
            "bio": "",
            "primary_region_id": "999999",
            "notify_email_enabled": "1",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    # flash 메시지가 다음 GET 페이지에 노출
    follow = client.get("/me/profile")
    assert "유효하지 않은 지역" in follow.text


# ---------------------------------------------------------------------------
# 4. POST /me/profile/avatar — multipart upload sets avatar_image_id
# ---------------------------------------------------------------------------


def test_post_avatar_upload_sets_avatar_image_id(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile/avatar",
        files={"image": ("avatar.png", _png_bytes(), "image/png")},
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(user)
    assert user.avatar_image_id is not None


# ---------------------------------------------------------------------------
# 5. POST /me/profile/avatar/delete — clears avatar_image_id
# ---------------------------------------------------------------------------


def test_post_avatar_delete_clears_avatar(client: TestClient, db: Session, login) -> None:
    from app.tests.factories import ImageFactory

    user = UserFactory()
    img = ImageFactory(owner=user)
    db.flush()
    user.avatar_image_id = img.id
    db.commit()
    login(user.id)

    r = client.post("/me/profile/avatar/delete", follow_redirects=False)
    assert r.status_code == 303
    db.refresh(user)
    assert user.avatar_image_id is None


# ---------------------------------------------------------------------------
# 6. GET /me/profile/username — throttle 안내 메시지
# ---------------------------------------------------------------------------


def test_get_username_page_shows_throttle_remaining(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory(
        username_changed_at=datetime.now(UTC) - timedelta(days=10)
    )
    db.commit()
    login(user.id)

    r = client.get("/me/profile/username")
    assert r.status_code == 200
    # 30 - 10 = 20 일 잔여 (test 실행 drift 허용)
    assert "일 후 변경 가능합니다" in r.text


# ---------------------------------------------------------------------------
# 7. POST /me/profile/username happy / duplicate / throttle
# ---------------------------------------------------------------------------


def test_post_username_happy_changes_and_redirects_to_profile(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory(username="oldname", username_changed_at=None)
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile/username",
        data={"new_username": "newname"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/me/profile"
    db.refresh(user)
    assert user.username == "newname"


def test_post_username_duplicate_flashes_and_stays_on_page(
    client: TestClient, db: Session, login
) -> None:
    UserFactory(username="taken")
    user = UserFactory(username="mine")
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile/username",
        data={"new_username": "taken"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/me/profile/username"
    follow = client.get("/me/profile/username")
    assert "이미 사용 중인 사용자명" in follow.text


def test_post_username_throttle_flashes_days_remaining(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory(
        username="oldname",
        username_changed_at=datetime.now(UTC) - timedelta(days=5),
    )
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile/username",
        data={"new_username": "newname"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/me/profile/username"
    follow = client.get("/me/profile/username")
    # 30 - 5 = 25 일 잔여
    assert "사용자명 변경은" in follow.text and "일 후 가능" in follow.text


# ---------------------------------------------------------------------------
# 8. GET /me/profile/password — 카카오 분기
# ---------------------------------------------------------------------------


def test_get_password_page_shows_form_for_email_user(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory(password_hash=auth_service.hash_password("pw1234567"))
    db.commit()
    login(user.id)

    r = client.get("/me/profile/password")
    assert r.status_code == 200
    assert 'name="current_password"' in r.text
    assert 'name="new_password"' in r.text


def test_get_password_page_shows_kakao_message_for_oauth_user(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory(password_hash=None, kakao_id="kakao_xyz")
    db.commit()
    login(user.id)

    r = client.get("/me/profile/password")
    assert r.status_code == 200
    assert "카카오 계정으로 가입하셨습니다" in r.text
    assert 'name="current_password"' not in r.text


# ---------------------------------------------------------------------------
# 9. POST /me/profile/password happy / wrong current / kakao 403
# ---------------------------------------------------------------------------


def test_post_password_happy_changes_hash(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory(password_hash=auth_service.hash_password("oldPassword"))
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile/password",
        data={"current_password": "oldPassword", "new_password": "newPassword"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    # 모든 디바이스 강제 로그아웃 — 로그인 페이지로 리디렉트하며 안내 메시지 표시.
    assert r.headers["location"] == "/auth/login?msg=password_changed"
    db.refresh(user)
    assert auth_service.verify_password("newPassword", user.password_hash) is True
    assert user.password_changed_at is not None
    # 후속 요청은 세션이 비어있어 보호 라우트 접근 불가.
    follow = client.get("/me/profile", follow_redirects=False)
    assert follow.status_code in (302, 303, 307, 401)


def test_post_password_invalidates_other_device_sessions(
    client: TestClient, db: Session, login
) -> None:
    """다른 디바이스의 기존 세션(=auth_iat 없음 또는 stale)도 다음 요청에서 무효화."""
    user = UserFactory(password_hash=auth_service.hash_password("oldPassword"))
    db.commit()
    login(user.id)
    # 비번 변경 — 본인 세션 clear됨.
    client.post(
        "/me/profile/password",
        data={"current_password": "oldPassword", "new_password": "newPassword"},
        follow_redirects=False,
    )
    # 다른 디바이스에서 비번 변경 이전에 발급된 세션(auth_iat 없음)으로 접근 시도.
    login(user.id)
    r = client.get("/me/profile", follow_redirects=False)
    assert r.status_code in (302, 303, 307, 401)


def test_post_password_wrong_current_flashes(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory(password_hash=auth_service.hash_password("realPass1234"))
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile/password",
        data={"current_password": "wrongPass", "new_password": "newPassword"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    follow = client.get("/me/profile/password")
    assert "현재 비밀번호" in follow.text  # flash message contains "현재 비밀번호..."


def test_post_password_kakao_user_returns_403(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory(password_hash=None, kakao_id="kakao_zzz")
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile/password",
        data={"current_password": "anything", "new_password": "newPass1234"},
    )
    assert r.status_code == 403
