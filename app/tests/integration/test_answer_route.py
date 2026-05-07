"""Tests for inline POST /question/{qid}/answer."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Post
from app.models._enums import PostType
from app.tests.factories import QuestionPostFactory, UserFactory


def test_answer_creates_post_with_parent_link(
    client: TestClient, db: Session, login,
) -> None:
    question = QuestionPostFactory()
    user = UserFactory()
    db.commit()
    login(user.id)
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


def test_answer_404_on_missing_question(client: TestClient, db: Session, login) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.post("/question/99999/answer", data={"body": "x"})
    assert r.status_code == 404
