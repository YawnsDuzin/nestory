"""Tests for POST /htmx/image/upload."""
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Image
from app.tests.factories import UserFactory


def _login_cookie(client: TestClient, user_id: int) -> dict[str, str]:
    """Reuse P1.2 pattern: signed session cookie via /auth/test-login (skip if absent).

    Falls back to direct session middleware manipulation."""
    from itsdangerous import TimestampSigner

    from app.config import get_settings
    signer = TimestampSigner(get_settings().app_secret_key)
    import base64
    import json
    payload = {"user_id": user_id}
    raw = base64.b64encode(json.dumps(payload).encode()).decode()
    cookie = signer.sign(raw.encode()).decode()
    return {"nestory_session": cookie}


def test_upload_returns_json_with_image_id_and_url(client: TestClient, db: Session) -> None:
    user = UserFactory()
    db.commit()
    cookies = _login_cookie(client, user.id)
    sample = Path("app/tests/fixtures/sample.jpg").read_bytes()
    r = client.post(
        "/htmx/image/upload",
        files={"image": ("sample.jpg", BytesIO(sample), "image/jpeg")},
        cookies=cookies,
    )
    assert r.status_code == 200
    body = r.json()
    assert "image_id" in body and isinstance(body["image_id"], int)
    assert body["url"] == f"/img/{body['image_id']}/orig"


def test_upload_requires_login(client: TestClient) -> None:
    sample = Path("app/tests/fixtures/sample.jpg").read_bytes()
    r = client.post(
        "/htmx/image/upload",
        files={"image": ("sample.jpg", BytesIO(sample), "image/jpeg")},
    )
    assert r.status_code == 401


def test_upload_rejects_non_image_mime(client: TestClient, db: Session) -> None:
    user = UserFactory()
    db.commit()
    cookies = _login_cookie(client, user.id)
    r = client.post(
        "/htmx/image/upload",
        files={
            "image": (
                "evil.exe",
                BytesIO(b"MZ\x90\x00not-an-image"),
                "application/octet-stream",
            ),
        },
        cookies=cookies,
    )
    assert r.status_code == 400


def test_upload_creates_image_row_and_enqueues_job(client: TestClient, db: Session) -> None:
    from app.models import Job
    from app.models._enums import JobKind
    user = UserFactory()
    db.commit()
    cookies = _login_cookie(client, user.id)
    sample = Path("app/tests/fixtures/sample.jpg").read_bytes()
    r = client.post(
        "/htmx/image/upload",
        files={"image": ("sample.jpg", BytesIO(sample), "image/jpeg")},
        cookies=cookies,
    )
    assert r.status_code == 200
    img_id = r.json()["image_id"]
    img = db.query(Image).filter_by(id=img_id).one()
    assert img.owner_id == user.id
    job = db.query(Job).filter(Job.kind == JobKind.IMAGE_RESIZE).one()
    assert job.payload == {"image_id": img_id}
