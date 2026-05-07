"""Tests for inline POST /question/{qid}/answer."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Post
from app.models._enums import PostType
from app.tests.factories import QuestionPostFactory, UserFactory


def _login_cookie(user_id: int) -> str:
    import base64
    import json

    from itsdangerous import TimestampSigner

    from app.config import get_settings
    signer = TimestampSigner(get_settings().app_secret_key)
    raw = base64.b64encode(json.dumps({"user_id": user_id}).encode()).decode()
    return signer.sign(raw.encode()).decode()


def _login(client: TestClient, user_id: int) -> None:
    client.cookies.set("nestory_session", _login_cookie(user_id))


def test_answer_creates_post_with_parent_link(client: TestClient, db: Session) -> None:
    question = QuestionPostFactory()
    user = UserFactory()
    db.commit()
    _login(client, user.id)
    r = client.post(
        f"/question/{question.id}/answer",
        data={"body": "셀룰로오스가 가성비 좋습니다"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    answer = db.query(Post).filter(Post.type == PostType.ANSWER).one()
    assert answer.parent_post_id == question.id
    assert answer.region_id == question.region_id
    assert r.headers["location"] == f"/question/{question.id}"


def test_answer_blocks_anonymous(client: TestClient, db: Session) -> None:
    question = QuestionPostFactory()
    db.commit()
    r = client.post(f"/question/{question.id}/answer", data={"body": "x"})
    assert r.status_code == 401


def test_answer_404_on_missing_question(client: TestClient, db: Session) -> None:
    user = UserFactory()
    db.commit()
    _login(client, user.id)
    r = client.post("/question/99999/answer", data={"body": "x"})
    assert r.status_code == 404
