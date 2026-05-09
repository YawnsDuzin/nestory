"""GET /_offline returns 200 without auth."""
from fastapi.testclient import TestClient


def test_offline_route_renders_for_anonymous(client: TestClient) -> None:
    r = client.get("/_offline")
    assert r.status_code == 200
    assert "오프라인입니다" in r.text


def test_offline_route_includes_home_link(client: TestClient) -> None:
    r = client.get("/_offline")
    assert r.status_code == 200
    assert 'href="/"' in r.text
