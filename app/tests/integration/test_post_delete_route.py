"""POST /post/{id}/delete — 작성자 본인 soft delete."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import PostStatus, PostType
from app.tests.factories import PostFactory, UserFactory


def test_author_deletes_question_redirects_home(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
    )
    db.commit()
    login(author.id)
    r = client.post(f"/post/{post.id}/delete", follow_redirects=False)
    assert r.status_code == 303
    db.refresh(post)
    assert post.deleted_at is not None


def test_author_deletes_answer_redirects_to_question(
    client: TestClient, db: Session, login
) -> None:
    author = UserFactory()
    q = PostFactory(type=PostType.QUESTION, status=PostStatus.PUBLISHED)
    a = PostFactory(
        author=author, author_id=author.id,
        type=PostType.ANSWER, status=PostStatus.PUBLISHED,
        parent_post_id=q.id, title="",
        metadata_={"__post_type__": "answer"},
    )
    db.commit()
    login(author.id)
    r = client.post(f"/post/{a.id}/delete", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == f"/question/{q.id}"
    db.refresh(a)
    assert a.deleted_at is not None


def test_non_author_cannot_delete(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    other = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
    )
    db.commit()
    login(other.id)
    r = client.post(f"/post/{post.id}/delete", follow_redirects=False)
    assert r.status_code == 403


def test_deleted_post_returns_404_on_detail(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
    )
    db.commit()
    login(author.id)
    client.post(f"/post/{post.id}/delete", follow_redirects=False)
    r = client.get(f"/question/{post.id}")
    assert r.status_code == 404
