"""Tests for GET·POST /write/review."""
import base64
import json

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Post
from app.models._enums import PostStatus, PostType
from app.tests.factories import RegionFactory, ResidentUserFactory, UserFactory


def _login_cookie(user_id: int) -> str:
    secret = get_settings().app_secret_key
    data = base64.b64encode(json.dumps({"user_id": user_id}).encode("utf-8"))
    signer = TimestampSigner(secret)
    return signer.sign(data).decode("utf-8")


def _login(client: TestClient, user_id: int) -> None:
    client.cookies.set("nestory_session", _login_cookie(user_id))


def test_get_write_review_renders_form(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    db.commit()
    _login(client, user.id)
    r = client.get("/write/review")
    assert r.status_code == 200
    assert "후기" in r.text or "review" in r.text.lower()
    # Form fields per ReviewMetadata
    assert 'name="house_type"' in r.text
    assert 'name="size_pyeong"' in r.text
    assert 'name="satisfaction_overall"' in r.text


def test_get_write_review_blocks_non_resident(client: TestClient, db: Session) -> None:
    user = UserFactory()  # badge_level=INTERESTED
    db.commit()
    _login(client, user.id)
    r = client.get("/write/review")
    assert r.status_code == 403


def test_get_write_review_blocks_anonymous(client: TestClient) -> None:
    r = client.get("/write/review")
    assert r.status_code == 401


def test_post_write_review_creates_post_and_redirects(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    region = RegionFactory()
    db.commit()
    _login(client, user.id)
    r = client.post(
        "/write/review",
        data={
            "title": "1년차 회고",
            "body": "단열이 가장 후회됨",
            "region_id": str(region.id),
            "house_type": "단독",
            "size_pyeong": "30",
            "satisfaction_overall": "4",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    post = db.query(Post).filter(Post.author_id == user.id, Post.type == PostType.REVIEW).one()
    assert r.headers["location"] == f"/post/{post.id}"
    assert post.status == PostStatus.PUBLISHED


def test_post_write_review_400_on_invalid_metadata(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    region = RegionFactory()
    db.commit()
    _login(client, user.id)
    r = client.post(
        "/write/review",
        data={
            "title": "x",
            "body": "y",
            "region_id": str(region.id),
            "house_type": "INVALID_TYPE",  # not in Literal
            "size_pyeong": "30",
            "satisfaction_overall": "4",
        },
    )
    assert r.status_code in (400, 422)
