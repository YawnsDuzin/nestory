import httpx
import pytest

from app.services.kakao import KakaoProfile, exchange_code_for_profile, build_authorize_url


def test_build_authorize_url_includes_state_and_params() -> None:
    url = build_authorize_url(client_id="abc", redirect_uri="https://x/cb", state="s1")
    assert "client_id=abc" in url
    assert "redirect_uri=https%3A%2F%2Fx%2Fcb" in url
    assert "state=s1" in url
    assert "response_type=code" in url
    assert url.startswith("https://kauth.kakao.com/oauth/authorize")


@pytest.mark.asyncio
async def test_exchange_code_returns_profile() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "TOK", "token_type": "bearer"})
        if request.url.path == "/v2/user/me":
            return httpx.Response(200, json={
                "id": 123456,
                "kakao_account": {"email": "kuser@kakao.com", "profile": {"nickname": "닉"}},
            })
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        profile = await exchange_code_for_profile(
            http,
            code="CODE",
            client_id="cid",
            client_secret="csec",
            redirect_uri="https://x/cb",
        )

    assert isinstance(profile, KakaoProfile)
    assert profile.kakao_id == "123456"
    assert profile.email == "kuser@kakao.com"
    assert profile.nickname == "닉"
