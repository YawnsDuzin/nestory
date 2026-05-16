import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.deps import (
    require_admin,
    require_badge,
    require_resident_in_region,
    require_user,
)
from app.models import User
from app.models.user import BadgeLevel
from app.tests.factories import (
    AdminUserFactory,
    RegionFactory,
    ResidentUserFactory,
    UserFactory,
)


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="t" * 32)

    @app.get("/protected")
    def protected(user: User = Depends(require_user)) -> dict:
        return {"id": user.id}

    @app.get("/admin")
    def admin(user: User = Depends(require_admin)) -> dict:
        return {"id": user.id}

    @app.get("/resident")
    def resident_only(user: User = Depends(require_badge(BadgeLevel.RESIDENT))) -> dict:
        return {"id": user.id}

    @app.get("/region/{region_id}")
    def region_only(
        region_id: int,
        user: User = Depends(require_resident_in_region("region_id")),
    ) -> dict:
        return {"id": user.id, "region_id": region_id}

    return app


def _session_cookie(user_id: int, *, auth_iat: float | None = None) -> str:
    import json
    from base64 import b64encode

    import itsdangerous

    signer = itsdangerous.TimestampSigner("t" * 32)
    payload: dict[str, int | float] = {"user_id": user_id}
    if auth_iat is not None:
        payload["auth_iat"] = auth_iat
    data = b64encode(json.dumps(payload).encode("utf-8"))
    return signer.sign(data).decode("utf-8")


def test_require_user_unauthenticated_rejects() -> None:
    test_app = _build_app()
    with TestClient(test_app) as c:
        r = c.get("/protected")
        assert r.status_code == 401


def test_require_user_authenticated_passes(db: Session) -> None:
    test_app = _build_app()
    user = UserFactory()
    db.commit()
    with TestClient(test_app) as c:
        c.cookies.set("session", _session_cookie(user.id))
        r = c.get("/protected")
        assert r.status_code == 200
        assert r.json() == {"id": user.id}


def test_require_admin_non_admin_rejects(db: Session) -> None:
    test_app = _build_app()
    user = UserFactory()
    db.commit()
    with TestClient(test_app) as c:
        c.cookies.set("session", _session_cookie(user.id))
        assert c.get("/admin").status_code == 403


def test_require_admin_admin_passes(db: Session) -> None:
    test_app = _build_app()
    user = AdminUserFactory()
    db.commit()
    with TestClient(test_app) as c:
        c.cookies.set("session", _session_cookie(user.id))
        assert c.get("/admin").status_code == 200


@pytest.mark.parametrize(
    "user_badge,expected",
    [
        (BadgeLevel.INTERESTED, 403),
        (BadgeLevel.REGION_VERIFIED, 403),
        (BadgeLevel.RESIDENT, 200),
        (BadgeLevel.EX_RESIDENT, 403),
    ],
)
def test_require_badge_resident(db: Session, user_badge: BadgeLevel, expected: int) -> None:
    test_app = _build_app()
    user = UserFactory(badge_level=user_badge)
    db.commit()
    with TestClient(test_app) as c:
        c.cookies.set("session", _session_cookie(user.id))
        assert c.get("/resident").status_code == expected


def test_require_resident_in_region_match(db: Session) -> None:
    test_app = _build_app()
    r = RegionFactory(sigungu="양평군", slug="yp-test-deps")
    user = ResidentUserFactory(primary_region=r)
    db.commit()
    with TestClient(test_app) as c:
        c.cookies.set("session", _session_cookie(user.id))
        assert c.get(f"/region/{r.id}").status_code == 200


def test_require_resident_in_region_mismatch(db: Session) -> None:
    test_app = _build_app()
    r1 = RegionFactory(sigungu="양평군", slug="yp-test-deps-2")
    r2 = RegionFactory(sigungu="가평군", slug="gp-test-deps-2")
    user = ResidentUserFactory(primary_region=r1)
    db.commit()
    with TestClient(test_app) as c:
        c.cookies.set("session", _session_cookie(user.id))
        assert c.get(f"/region/{r2.id}").status_code == 403


def test_get_current_user_ignores_authorization_header(db: Session) -> None:
    """P2 Bearer placeholder: Authorization 헤더가 와도 현재는 세션 기반 인증만 사용."""
    test_app = _build_app()
    user = UserFactory()
    db.commit()
    with TestClient(test_app) as c:
        c.cookies.set("session", _session_cookie(user.id))
        r = c.get("/protected", headers={"Authorization": "Bearer ignored-token"})
        assert r.status_code == 200
        assert r.json() == {"id": user.id}


def test_get_current_user_authorization_header_alone_does_not_authenticate(db: Session) -> None:
    """P2 placeholder 검증: Authorization 헤더만 있고 세션이 없으면 401."""
    test_app = _build_app()
    user = UserFactory()
    db.commit()
    with TestClient(test_app) as c:
        r = c.get("/protected", headers={"Authorization": f"Bearer user-{user.id}"})
        assert r.status_code == 401


def test_session_invalidated_when_auth_iat_predates_password_change(db: Session) -> None:
    """비번 변경 시점 이전 발급 세션은 거절 — 다른 디바이스 강제 로그아웃."""
    from datetime import UTC, datetime, timedelta

    test_app = _build_app()
    user = UserFactory()
    user.password_changed_at = datetime.now(UTC)
    db.commit()
    # 비번 변경 직전에 발급된 (오래된) 세션
    old_iat = (datetime.now(UTC) - timedelta(minutes=5)).timestamp()
    with TestClient(test_app) as c:
        c.cookies.set("session", _session_cookie(user.id, auth_iat=old_iat))
        assert c.get("/protected").status_code == 401


def test_session_invalidated_when_auth_iat_missing_and_password_changed(db: Session) -> None:
    """auth_iat 자체가 없는 구 세션 — password_changed_at이 설정된 사용자에겐 거절."""
    from datetime import UTC, datetime

    test_app = _build_app()
    user = UserFactory()
    user.password_changed_at = datetime.now(UTC)
    db.commit()
    with TestClient(test_app) as c:
        c.cookies.set("session", _session_cookie(user.id))  # no auth_iat
        assert c.get("/protected").status_code == 401


def test_session_accepted_when_auth_iat_after_password_change(db: Session) -> None:
    """비번 변경 후 새로 발급된 세션은 통과."""
    from datetime import UTC, datetime, timedelta

    test_app = _build_app()
    user = UserFactory()
    user.password_changed_at = datetime.now(UTC) - timedelta(hours=1)
    db.commit()
    fresh_iat = datetime.now(UTC).timestamp()
    with TestClient(test_app) as c:
        c.cookies.set("session", _session_cookie(user.id, auth_iat=fresh_iat))
        assert c.get("/protected").status_code == 200


def test_session_accepted_when_password_never_changed(db: Session) -> None:
    """가입 후 비번 미변경 사용자 — auth_iat 없어도 통과 (기존 동작 보존)."""
    test_app = _build_app()
    user = UserFactory()  # password_changed_at = None
    db.commit()
    with TestClient(test_app) as c:
        c.cookies.set("session", _session_cookie(user.id))
        assert c.get("/protected").status_code == 200
