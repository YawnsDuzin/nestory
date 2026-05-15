"""E2E — Question 생성 → 수정 → 답변 작성 → 답변 수정 → 답변 삭제 → 질문 삭제."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Post
from app.models._enums import PostType
from app.tests.factories import RegionFactory, UserFactory


def test_full_edit_delete_flow(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    region = RegionFactory(slug="e2e-edit-region")
    db.commit()
    login(author.id)

    # 1. 질문 작성
    r = client.post("/write/question", data={
        "title": "양평 빌라 vs 단독주택 어떻게?",
        "body": "원본 본문",
        "region_id": str(region.id),
        "tags": "주택,선택",
    }, follow_redirects=False)
    assert r.status_code == 303
    qid = int(r.headers["location"].rsplit("/", 1)[1])

    # 2. 질문 수정
    r = client.post(f"/write/question/{qid}", data={
        "title": "양평 빌라 vs 단독주택 (재정리)",
        "body": "수정된 본문",
        "region_id": str(region.id),
        "tags": "주택,선택,재정리",
    }, follow_redirects=False)
    assert r.status_code == 303
    q = db.get(Post, qid)
    assert q.title.endswith("(재정리)")
    assert q.edited_at is not None

    # 3. 답변 작성
    r = client.post(f"/question/{qid}/answer", data={"body": "원본 답변"}, follow_redirects=False)
    assert r.status_code == 303
    aid = db.query(Post).filter(Post.type == PostType.ANSWER, Post.parent_post_id == qid).one().id

    # 4. 답변 수정
    r = client.post(f"/write/answer/{aid}", data={"body": "수정된 답변"}, follow_redirects=False)
    assert r.status_code == 303
    db.expire_all()
    a = db.get(Post, aid)
    assert a.body == "수정된 답변"
    assert a.edited_at is not None

    # 5. 답변 삭제
    r = client.post(f"/post/{aid}/delete", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == f"/question/{qid}"
    db.expire_all()
    a = db.get(Post, aid)
    assert a.deleted_at is not None

    # 6. 질문 삭제
    r = client.post(f"/post/{qid}/delete", follow_redirects=False)
    assert r.status_code == 303
    db.expire_all()
    q = db.get(Post, qid)
    assert q.deleted_at is not None

    # 7. 삭제된 질문 detail은 404
    r = client.get(f"/question/{qid}")
    assert r.status_code == 404
