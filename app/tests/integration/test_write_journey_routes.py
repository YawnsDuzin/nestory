"""Tests for journey create + episode routes."""
import base64
import json

from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Journey, Post
from app.models._enums import PostType
from app.tests.factories import JourneyFactory, RegionFactory, ResidentUserFactory, UserFactory


def _login_cookie(user_id: int) -> str:
    signer = TimestampSigner(get_settings().app_secret_key)
    raw = base64.b64encode(json.dumps({"user_id": user_id}).encode()).decode()
    return signer.sign(raw.encode()).decode()


def _login(client: TestClient, user_id: int) -> None:
    client.cookies.set("nestory_session", _login_cookie(user_id))


def test_get_write_journey_renders(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    db.commit()
    _login(client, user.id)
    r = client.get("/write/journey")
    assert r.status_code == 200


def test_post_write_journey_creates_journey(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    region = RegionFactory()
    db.commit()
    _login(client, user.id)
    r = client.post(
        "/write/journey",
        data={
            "title": "양평 정착기",
            "description": "터잡기부터 입주까지",
            "region_id": str(region.id),
            "start_date": "2026-01-01",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    j = db.query(Journey).one()
    assert j.title == "양평 정착기"
    assert r.headers["location"] == f"/journey/{j.id}"


def test_post_write_journey_blocks_non_resident(client: TestClient, db: Session) -> None:
    user = UserFactory()
    region = RegionFactory()
    db.commit()
    _login(client, user.id)
    r = client.post(
        "/write/journey",
        data={"title": "x", "region_id": str(region.id)},
    )
    assert r.status_code == 403


def test_post_journey_episode_auto_increments(client: TestClient, db: Session) -> None:
    user = ResidentUserFactory()
    journey = JourneyFactory(author=user)
    db.commit()
    _login(client, user.id)
    for n in range(2):
        r = client.post(
            f"/write/journey/{journey.id}/ep",
            data={
                "title": f"{n+1}화", "body": "...",
                "phase": "입주", "period_label": "2026-04",
            },
            follow_redirects=False,
        )
        assert r.status_code == 303
    eps = (
        db.query(Post)
        .filter(Post.type == PostType.JOURNEY_EPISODE)
        .order_by(Post.episode_no)
        .all()
    )
    assert [e.episode_no for e in eps] == [1, 2]


def test_journey_episode_blocks_non_owner(client: TestClient, db: Session) -> None:
    owner = ResidentUserFactory()
    intruder = ResidentUserFactory()
    journey = JourneyFactory(author=owner)
    db.commit()
    _login(client, intruder.id)
    r = client.post(
        f"/write/journey/{journey.id}/ep",
        data={"title": "x", "body": "y", "phase": "입주", "period_label": "2026-04"},
    )
    assert r.status_code == 403
