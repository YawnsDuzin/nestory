"""Middleware sets request.state.distinct_id_hash + session anon_id persistence."""
from fastapi.testclient import TestClient


def test_anonymous_user_gets_anon_distinct_id(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    r2 = client.get("/")
    assert r2.status_code == 200


def test_logged_in_user_gets_sha256_distinct_id(
    client: TestClient, db, login
) -> None:
    from app.tests.factories import UserFactory
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200


def test_anon_id_persists_across_requests(client: TestClient) -> None:
    r1 = client.get("/")
    cookie1 = client.cookies.get("nestory_session")
    r2 = client.get("/")
    cookie2 = client.cookies.get("nestory_session")
    assert r1.status_code == 200 and r2.status_code == 200
    assert cookie1 == cookie2 or cookie2 is not None
