import base64
import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BadgeApplication, Region, User


def _login_cookie(user_id: int) -> str:
    """Mirror starlette SessionMiddleware: TimestampSigner(b64(json))."""
    secret = get_settings().app_secret_key
    data = base64.b64encode(json.dumps({"user_id": user_id}).encode("utf-8"))
    signer = TimestampSigner(secret)
    return signer.sign(data).decode("utf-8")


def _make_user(db: Session) -> User:
    ts = int(datetime.now(UTC).timestamp() * 1_000_000)
    u = User(
        email=f"t{ts}@example.com",
        username=f"u{ts}",
        display_name="테스터",
        password_hash="x",
    )
    db.add(u)
    db.flush()
    db.commit()
    return u


def test_badge_page_requires_login(client: TestClient) -> None:
    r = client.get("/me/badge")
    assert r.status_code == 401


def test_badge_page_renders_for_logged_in_user(db: Session, client: TestClient) -> None:
    user = _make_user(db)
    client.cookies.set("nestory_session", _login_cookie(user.id))
    r = client.get("/me/badge")
    assert r.status_code == 200
    assert "내 배지" in r.text
    assert "관심자" in r.text  # 기본 배지 표시


def test_apply_region_creates_pending_application(db: Session, client: TestClient) -> None:
    user = _make_user(db)
    region = Region(sido="경기", sigungu="양평군", slug="yp-me-test")
    db.add(region)
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(user.id))
    r = client.post("/me/badge/region", data={"region_id": region.id}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/me/badge"

    apps = db.query(BadgeApplication).filter_by(user_id=user.id).all()
    assert len(apps) == 1
    assert apps[0].region_id == region.id


def test_apply_region_blocks_duplicate_pending(db: Session, client: TestClient) -> None:
    user = _make_user(db)
    region = Region(sido="경기", sigungu="양평군", slug="yp-dup")
    db.add(region)
    db.commit()
    client.cookies.set("nestory_session", _login_cookie(user.id))
    client.post("/me/badge/region", data={"region_id": region.id})
    r = client.post("/me/badge/region", data={"region_id": region.id})
    assert r.status_code == 409


def test_apply_region_invalid_id(db: Session, client: TestClient) -> None:
    user = _make_user(db)
    client.cookies.set("nestory_session", _login_cookie(user.id))
    r = client.post("/me/badge/region", data={"region_id": 99999})
    assert r.status_code == 400
