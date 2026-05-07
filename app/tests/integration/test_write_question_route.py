"""Tests for GET·POST /write/question."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Post
from app.models._enums import PostType
from app.tests.factories import RegionFactory, UserFactory


def test_get_form_renders(client: TestClient, db: Session, login) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.get("/write/question")
    assert r.status_code == 200


def test_post_creates_question(client: TestClient, db: Session, login) -> None:
    user = UserFactory()
    region = RegionFactory()
    db.commit()
    login(user.id)
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
