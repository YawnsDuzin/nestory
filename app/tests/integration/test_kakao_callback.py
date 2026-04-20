from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.services.kakao import KakaoProfile


def test_kakao_start_redirects_to_authorize(client: TestClient) -> None:
    r = client.get("/auth/kakao/start", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"].startswith("https://kauth.kakao.com/oauth/authorize")


def test_kakao_callback_creates_user_and_logs_in(client: TestClient) -> None:
    fake_profile = KakaoProfile(kakao_id="99999", email="k@kakao.com", nickname="테스터")

    async def fake_exchange(*args, **kwargs):
        return fake_profile

    with patch("app.routers.auth.exchange_code_for_profile", side_effect=fake_exchange):
        start = client.get("/auth/kakao/start", follow_redirects=False)
        loc = start.headers["location"]
        qs = parse_qs(urlparse(loc).query)
        st = qs["state"][0]

        r = client.get(f"/auth/kakao/callback?code=C&state={st}", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"


def test_kakao_callback_rejects_bad_state(client: TestClient) -> None:
    r = client.get("/auth/kakao/callback?code=C&state=wrong", follow_redirects=False)
    assert r.status_code == 400
