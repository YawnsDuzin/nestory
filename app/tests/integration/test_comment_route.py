"""Integration tests for POST /post/{id}/comment.

Tests:
- test_comment_redirects_to_post_anchor
- test_comment_anonymous_returns_401
- test_comment_empty_body_returns_400
- test_comment_too_long_returns_400
- test_comment_journey_episode_redirects_correctly
- test_comment_question_redirects_correctly

NOTE: Requires a running Postgres instance.
      Cannot be executed on a no-Docker PC — run on docker-up PC.
"""
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import PostStatus
from app.tests.factories import (
    JourneyEpisodePostFactory,
    JourneyFactory,
    QuestionPostFactory,
    ResidentUserFactory,
    ReviewPostFactory,
    UserFactory,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _published_review(author=None, **kwargs):
    kw = dict(status=PostStatus.PUBLISHED, published_at=datetime.now(UTC))
    if author is not None:
        kw["author"] = author
    kw.update(kwargs)
    return ReviewPostFactory(**kw)


def _published_question(**kwargs):
    return QuestionPostFactory(
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        **kwargs,
    )


def _published_journey_ep(author, journey, **kwargs):
    return JourneyEpisodePostFactory(
        author=author,
        region_id=journey.region_id,
        journey_id=journey.id,
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Regular post (review / plan) comment
# ---------------------------------------------------------------------------


def test_comment_redirects_to_post_anchor(
    client: TestClient, db: Session, login
) -> None:
    """POST /post/{id}/comment redirects to /post/{id}#comments on success."""
    user = UserFactory()
    post = _published_review()
    db.commit()

    login(user.id)
    r = client.post(
        f"/post/{post.id}/comment",
        data={"body": "훌륭한 후기네요!"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/post/{post.id}#comments"


def test_comment_anonymous_returns_401(client: TestClient, db: Session) -> None:
    """POST /post/{id}/comment without login returns 401."""
    post = _published_review()
    db.commit()

    r = client.post(
        f"/post/{post.id}/comment",
        data={"body": "익명 댓글"},
        follow_redirects=False,
    )
    assert r.status_code == 401


def test_comment_empty_body_returns_400(
    client: TestClient, db: Session, login
) -> None:
    """POST with blank body returns 400."""
    user = UserFactory()
    post = _published_review()
    db.commit()

    login(user.id)
    r = client.post(
        f"/post/{post.id}/comment",
        data={"body": "   "},
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_comment_too_long_returns_400(
    client: TestClient, db: Session, login
) -> None:
    """POST with body > 2000 chars returns 400."""
    user = UserFactory()
    post = _published_review()
    db.commit()

    login(user.id)
    r = client.post(
        f"/post/{post.id}/comment",
        data={"body": "가" * 2001},
        follow_redirects=False,
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Journey episode comment — type-aware redirect
# ---------------------------------------------------------------------------


def test_comment_journey_episode_redirects_correctly(
    client: TestClient, db: Session, login
) -> None:
    """Comment on journey episode redirects to /journey/{jid}/ep/{n}#comments."""
    user = ResidentUserFactory()
    journey = JourneyFactory(author=user)
    ep = _published_journey_ep(user, journey, episode_no=1)
    db.commit()

    login(user.id)
    r = client.post(
        f"/post/{ep.id}/comment",
        data={"body": "멋진 에피소드입니다"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/journey/{journey.id}/ep/{ep.episode_no}#comments"


# ---------------------------------------------------------------------------
# Question comment — type-aware redirect
# ---------------------------------------------------------------------------


def test_comment_question_redirects_correctly(
    client: TestClient, db: Session, login
) -> None:
    """Comment on question redirects to /question/{id}#comments."""
    user = UserFactory()
    question = _published_question()
    db.commit()

    login(user.id)
    r = client.post(
        f"/post/{question.id}/comment",
        data={"body": "좋은 질문입니다"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/question/{question.id}#comments"
