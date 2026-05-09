"""E2E flow: comment trigger → bell unread → click → redirect + mark read.

NOTE: Requires running Postgres.
"""
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notification
from app.models._enums import PostStatus
from app.tests.factories import ReviewPostFactory, UserFactory


def test_full_notification_lifecycle(
    client: TestClient, db: Session, login
) -> None:
    # 1. 두 사용자: 글 작성자(author) + 댓글 작성자(commenter)
    author = UserFactory()
    commenter = UserFactory()
    post = ReviewPostFactory(author=author, status=PostStatus.PUBLISHED)
    db.commit()

    # 2. commenter가 post에 댓글 작성 (POST 라우트)
    login(commenter.id)
    r = client.post(
        f"/post/{post.id}/comment",
        data={"body": "좋은 글입니다"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    # 3. author 측에 알림 row 1개
    notifs = list(
        db.scalars(
            select(Notification).where(Notification.user_id == author.id)
        ).all()
    )
    assert len(notifs) == 1
    notif = notifs[0]
    assert notif.is_read is False

    # 4. author 로그인 → bell partial GET → unread 표시
    client.cookies.clear()
    login(author.id)
    r = client.get("/notifications/_bell")
    assert r.status_code == 200
    assert "댓글" in r.text  # POST_COMMENT 메시지

    # 5. author가 알림 클릭 (POST read) → 303 to /post/{post.id}
    r = client.post(
        f"/notifications/{notif.id}/read", follow_redirects=False
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/post/{post.id}"

    # 6. 알림 read 처리됨
    db.refresh(notif)
    assert notif.is_read is True

    # 7. bell partial 재호출 → unread 0 (배지 사라짐)
    r = client.get("/notifications/_bell")
    assert r.status_code == 200
    assert "댓글" in r.text  # 여전히 dropdown에 표시 (read 상태)
