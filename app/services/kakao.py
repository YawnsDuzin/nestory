from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

import httpx

AUTHORIZE_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
PROFILE_URL = "https://kapi.kakao.com/v2/user/me"


@dataclass
class KakaoProfile:
    kakao_id: str
    email: str | None
    nickname: str | None


def build_authorize_url(*, client_id: str, redirect_uri: str, state: str) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": "profile_nickname account_email",
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code_for_profile(
    http: httpx.AsyncClient,
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> KakaoProfile:
    token_resp = await http.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token_resp.raise_for_status()
    access_token = token_resp.json()["access_token"]

    me_resp = await http.get(
        PROFILE_URL,
        headers={"Authorization": f"Bearer {access_token}"},
    )
    me_resp.raise_for_status()
    body = me_resp.json()

    account = body.get("kakao_account", {}) or {}
    profile_block = account.get("profile", {}) or {}
    return KakaoProfile(
        kakao_id=str(body["id"]),
        email=account.get("email"),
        nickname=profile_block.get("nickname"),
    )
