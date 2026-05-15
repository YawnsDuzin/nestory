"""POST /write/question/{id} · /write/plan/{id} · /write/answer/{id} edit 라우트."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import PostStatus, PostType
from app.tests.factories import PostFactory, RegionFactory, UserFactory


def test_get_edit_question_renders_prefilled(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    region = RegionFactory(slug="edit-q-region")
    post = PostFactory(
        author=author, author_id=author.id,
        region=region, region_id=region.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
        title="원래 제목", body="원래 본문",
        metadata_={"__post_type__": "question", "tags": ["a", "b"]},
    )
    db.commit()
    login(author.id)
    r = client.get(f"/write/question/{post.id}")
    assert r.status_code == 200
    assert "원래 제목" in r.text
    assert "원래 본문" in r.text


def test_post_edit_question_updates_fields(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    region = RegionFactory(slug="edit-q-region-2")
    post = PostFactory(
        author=author, author_id=author.id,
        region=region, region_id=region.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
        title="A", body="B",
        metadata_={"__post_type__": "question", "tags": []},
    )
    db.commit()
    login(author.id)
    r = client.post(
        f"/write/question/{post.id}",
        data={
            "title": "수정된 제목",
            "body": "수정된 본문",
            "region_id": str(region.id),
            "tags": "k1,k2",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/question/{post.id}"
    db.refresh(post)
    assert post.title == "수정된 제목"
    assert post.body == "수정된 본문"
    assert post.metadata_["tags"] == ["k1", "k2"]
    assert post.edited_at is not None


def test_non_author_cannot_edit(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    other = UserFactory()
    region = RegionFactory(slug="edit-q-region-3")
    post = PostFactory(
        author=author, author_id=author.id,
        region=region, region_id=region.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
    )
    db.commit()
    login(other.id)
    r = client.get(f"/write/question/{post.id}")
    assert r.status_code == 403
