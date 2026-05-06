from datetime import UTC, datetime

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
from app.models import Region, User
from app.models.user import BadgeLevel, UserRole


def _make_user(
    db: Session,
    *,
    badge: BadgeLevel = BadgeLevel.INTERESTED,
    role: UserRole = UserRole.USER,
    primary_region_id: int | None = None,
) -> User:
    ts = int(datetime.now(UTC).timestamp() * 1_000_000)
    u = User(
        email=f"t{ts}@example.com",
        username=f"u{ts}",
        display_name="테스터",
        password_hash="x",
        badge_level=badge,
        role=role,
        primary_region_id=primary_region_id,
    )
    db.add(u)
    db.flush()
    return u


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


def _session_cookie(user_id: int) -> str:
    import json
    from base64 import b64encode

    import itsdangerous

    signer = itsdangerous.TimestampSigner("t" * 32)
    data = b64encode(json.dumps({"user_id": user_id}).encode("utf-8"))
    return signer.sign(data).decode("utf-8")


def test_require_user_unauthenticated_rejects() -> None:
    test_app = _build_app()
    with TestClient(test_app) as c:
        r = c.get("/protected")
        assert r.status_code == 401


def test_require_user_authenticated_passes(db: Session) -> None:
    test_app = _build_app()
    user = _make_user(db)
    db.commit()
    with TestClient(test_app) as c:
        c.cookies.set("session", _session_cookie(user.id))
        r = c.get("/protected")
        assert r.status_code == 200
        assert r.json() == {"id": user.id}


def test_require_admin_non_admin_rejects(db: Session) -> None:
    test_app = _build_app()
    user = _make_user(db, role=UserRole.USER)
    db.commit()
    with TestClient(test_app) as c:
        c.cookies.set("session", _session_cookie(user.id))
        assert c.get("/admin").status_code == 403


def test_require_admin_admin_passes(db: Session) -> None:
    test_app = _build_app()
    user = _make_user(db, role=UserRole.ADMIN)
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
    user = _make_user(db, badge=user_badge)
    db.commit()
    with TestClient(test_app) as c:
        c.cookies.set("session", _session_cookie(user.id))
        assert c.get("/resident").status_code == expected


def test_require_resident_in_region_match(db: Session) -> None:
    test_app = _build_app()
    r = Region(sido="경기", sigungu="양평군", slug="yp-test-deps")
    db.add(r)
    db.flush()
    user = _make_user(db, badge=BadgeLevel.RESIDENT, primary_region_id=r.id)
    db.commit()
    with TestClient(test_app) as c:
        c.cookies.set("session", _session_cookie(user.id))
        assert c.get(f"/region/{r.id}").status_code == 200


def test_require_resident_in_region_mismatch(db: Session) -> None:
    test_app = _build_app()
    r1 = Region(sido="경기", sigungu="양평군", slug="yp-test-deps-2")
    r2 = Region(sido="경기", sigungu="가평군", slug="gp-test-deps-2")
    db.add_all([r1, r2])
    db.flush()
    user = _make_user(db, badge=BadgeLevel.RESIDENT, primary_region_id=r1.id)
    db.commit()
    with TestClient(test_app) as c:
        c.cookies.set("session", _session_cookie(user.id))
        assert c.get(f"/region/{r2.id}").status_code == 403
