"""Tests for GET·POST /write/review."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Post
from app.models._enums import PostStatus, PostType
from app.tests.factories import RegionFactory, ResidentUserFactory, UserFactory


def test_get_write_review_renders_form(client: TestClient, db: Session, login) -> None:
    user = ResidentUserFactory()
    db.commit()
    login(user.id)
    r = client.get("/write/review")
    assert r.status_code == 200
    assert "후기" in r.text or "review" in r.text.lower()
    # Form fields per ReviewMetadata
    assert 'name="house_type"' in r.text
    assert 'name="size_pyeong"' in r.text
    assert 'name="satisfaction_overall"' in r.text


def test_get_write_review_blocks_non_resident(
    client: TestClient, db: Session, login,
) -> None:
    user = UserFactory()  # badge_level=INTERESTED
    db.commit()
    login(user.id)
    r = client.get("/write/review")
    assert r.status_code == 403


def test_get_write_review_blocks_anonymous(client: TestClient) -> None:
    r = client.get("/write/review")
    assert r.status_code == 401


def test_post_write_review_creates_post_and_redirects(
    client: TestClient, db: Session, login,
) -> None:
    user = ResidentUserFactory()
    region = RegionFactory()
    db.commit()
    login(user.id)
    r = client.post(
        "/write/review",
        data={
            "title": "1년차 회고",
            "body": "단열이 가장 후회됨",
            "region_id": str(region.id),
            "house_type": "단독",
            "size_pyeong": "30",
            "satisfaction_overall": "4",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    post = db.query(Post).filter(Post.author_id == user.id, Post.type == PostType.REVIEW).one()
    assert r.headers["location"] == f"/post/{post.id}"
    assert post.status == PostStatus.PUBLISHED


def test_post_write_review_400_on_invalid_metadata(
    client: TestClient, db: Session, login,
) -> None:
    user = ResidentUserFactory()
    region = RegionFactory()
    db.commit()
    login(user.id)
    r = client.post(
        "/write/review",
        data={
            "title": "x",
            "body": "y",
            "region_id": str(region.id),
            "house_type": "INVALID_TYPE",  # not in Literal
            "size_pyeong": "30",
            "satisfaction_overall": "4",
        },
    )
    assert r.status_code in (400, 422)


def test_post_write_review_400_on_pydantic_validation_error(
    client: TestClient, db: Session, login,
) -> None:
    """satisfaction_overall=6 passes FastAPI int validation but fails Pydantic le=5."""
    user = ResidentUserFactory()
    region = RegionFactory()
    db.commit()
    login(user.id)
    r = client.post(
        "/write/review",
        data={
            "title": "x",
            "body": "y",
            "region_id": str(region.id),
            "house_type": "단독",
            "size_pyeong": "30",
            "satisfaction_overall": "6",  # > Pydantic's le=5 cap
        },
    )
    assert r.status_code == 400
    text = r.text.lower()
    assert "satisfaction" in text or "less than" in text or "validation" in text


def test_post_write_review_400_on_body_too_long(
    client: TestClient, db: Session, login,
) -> None:
    """Body > 50KB UTF-8 must reject with 400 to prevent abuse."""
    user = ResidentUserFactory()
    region = RegionFactory()
    db.commit()
    login(user.id)
    huge_body = "가" * 30_000  # 30K Korean chars * 3 bytes/char = 90KB > 50KB cap
    r = client.post(
        "/write/review",
        data={
            "title": "x",
            "body": huge_body,
            "region_id": str(region.id),
            "house_type": "단독",
            "size_pyeong": "30",
            "satisfaction_overall": "4",
        },
    )
    assert r.status_code == 400
    assert "본문" in r.text or "최대" in r.text
