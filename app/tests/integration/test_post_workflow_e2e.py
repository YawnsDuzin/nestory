"""End-to-end: login → upload image → write review → detail page renders."""
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.factories import RegionFactory, ResidentUserFactory


def test_full_post_workflow_with_image(client: TestClient, db: Session, login) -> None:
    user = ResidentUserFactory()
    region = RegionFactory()
    db.commit()
    login(user.id)

    # 1. Upload image
    sample = Path("app/tests/fixtures/sample.jpg").read_bytes()
    upload_r = client.post(
        "/htmx/image/upload",
        files={"image": ("sample.jpg", BytesIO(sample), "image/jpeg")},
    )
    assert upload_r.status_code == 200
    img_data = upload_r.json()
    img_id = img_data["image_id"]
    img_url = img_data["url"]

    # 2. Write review with image embedded in body
    body = f"단열이 가장 후회됨\n\n![]({img_url})"
    write_r = client.post(
        "/write/review",
        data={
            "title": "1년차 회고",
            "body": body,
            "region_id": str(region.id),
            "house_type": "단독",
            "size_pyeong": "30",
            "satisfaction_overall": "4",
        },
        follow_redirects=False,
    )
    assert write_r.status_code == 303
    post_url = write_r.headers["location"]

    # 3. View detail page
    detail_r = client.get(post_url)
    assert detail_r.status_code == 200
    assert "1년차 회고" in detail_r.text
    # Markdown filter swapped /img/{id}/orig → /img/{id}/medium
    assert f"/img/{img_id}/medium" in detail_r.text
    assert f"/img/{img_id}/orig" not in detail_r.text


def test_journey_workflow_create_episode_view(client: TestClient, db: Session, login) -> None:
    user = ResidentUserFactory()
    region = RegionFactory()
    db.commit()
    login(user.id)

    # 1. Create journey
    j_r = client.post(
        "/write/journey",
        data={"title": "양평 정착기", "description": "터잡기부터", "region_id": str(region.id)},
        follow_redirects=False,
    )
    assert j_r.status_code == 303
    journey_url = j_r.headers["location"]
    journey_id = int(journey_url.split("/")[-1])

    # 2. Add episode
    ep_r = client.post(
        f"/write/journey/{journey_id}/ep",
        data={"title": "1화 터잡기", "body": "땅 매입", "phase": "터", "period_label": "2026-01"},
        follow_redirects=False,
    )
    assert ep_r.status_code == 303
    assert ep_r.headers["location"] == f"/journey/{journey_id}/ep/1"

    # 3. View journey listing
    list_r = client.get(journey_url)
    assert list_r.status_code == 200
    assert "1화 터잡기" in list_r.text


def test_question_answer_workflow(client: TestClient, db: Session, login) -> None:
    asker = ResidentUserFactory()
    answerer = ResidentUserFactory()
    region = RegionFactory()
    db.commit()

    # 1. Asker posts question
    login(asker.id)
    q_r = client.post(
        "/write/question",
        data={"title": "단열재?", "body": "추천 부탁", "region_id": str(region.id), "tags": "단열"},
        follow_redirects=False,
    )
    q_url = q_r.headers["location"]

    # 2. Answerer posts answer
    login(answerer.id)  # switches cookie
    a_r = client.post(
        f"{q_url}/answer",
        data={"body": "셀룰로오스 추천"},
        follow_redirects=False,
    )
    assert a_r.status_code == 303

    # 3. Anyone views thread with answer
    detail = client.get(q_url)
    assert detail.status_code == 200
    assert "셀룰로오스 추천" in detail.text
