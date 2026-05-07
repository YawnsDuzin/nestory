"""Tests for GET·POST /write/question."""
import base64
import json

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Post
from app.models._enums import PostType
from app.tests.factories import RegionFactory, UserFactory


def _login_cookie(user_id: int) -> str:
    signer = TimestampSigner(get_settings().app_secret_key)
    raw = base64.b64encode(json.dumps({"user_id": user_id}).encode()).decode()
    return signer.sign(raw.encode()).decode()


def _login(client: TestClient, user_id: int) -> None:
    client.cookies.set("nestory_session", _login_cookie(user_id))


def test_get_form_renders(client: TestClient, db: Session) -> None:
    user = UserFactory()
    db.commit()
    _login(client, user.id)
    r = client.get("/write/question")
    assert r.status_code == 200


def test_post_creates_question(client: TestClient, db: Session) -> None:
    user = UserFactory()
    region = RegionFactory()
    db.commit()
    _login(client, user.id)
    r = client.post(
        "/write/question",
        data={"title": "Q?", "body": "details", "region_id": str(region.id), "tags": "단열,지붕"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    q = db.query(Post).filter(Post.type == PostType.QUESTION).one()
    assert q.metadata_["tags"] == ["단열", "지붕"]


def test_anonymous_blocked(client: TestClient) -> None:
    r = client.get("/write/question")
    assert r.status_code == 401
