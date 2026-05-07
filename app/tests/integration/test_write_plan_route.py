"""Tests for GET·POST /write/plan."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Post
from app.models._enums import PostType
from app.tests.factories import RegionFactory, UserFactory


def test_post_creates_plan(client: TestClient, db: Session, login) -> None:
    region = RegionFactory()
    user = UserFactory(primary_region_id=region.id)
    db.commit()
    login(user.id)
    r = client.post(
        "/write/plan",
        data={
            "title": "2027 양평 입주",
            "body": "검토 중",
            "region_id": str(region.id),
            "target_move_year": "2027",
            "budget_total_manwon_band": "5000-10000",
            "construction_intent": "undecided",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    p = db.query(Post).filter(Post.type == PostType.PLAN).one()
    assert p.metadata_["target_move_year"] == 2027


def test_get_plan_form_without_primary_region(
    client: TestClient, db: Session, login,
) -> None:
    """User has no primary_region_id — form still renders (region select still available)."""
    user = UserFactory()
    RegionFactory()
    db.commit()
    login(user.id)
    r = client.get("/write/plan")
    assert r.status_code == 200
