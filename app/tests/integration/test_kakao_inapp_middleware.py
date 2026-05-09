"""Middleware sets request.state.kakao_inapp + banner conditional render."""
from fastapi.testclient import TestClient


def test_kakao_ua_shows_banner(client: TestClient) -> None:
    r = client.get("/", headers={"user-agent": "Mozilla/5.0 KAKAOTALK 9.0.0"})
    assert r.status_code == 200
    assert "외부 브라우저에서 열어보세요" in r.text


def test_chrome_ua_no_banner(client: TestClient) -> None:
    r = client.get(
        "/", headers={"user-agent": "Mozilla/5.0 Chrome/120"}
    )
    assert r.status_code == 200
    assert "외부 브라우저에서 열어보세요" not in r.text


def test_no_ua_no_banner(client: TestClient) -> None:
    r = client.get("/", headers={"user-agent": ""})
    assert r.status_code == 200
    assert "외부 브라우저에서 열어보세요" not in r.text
