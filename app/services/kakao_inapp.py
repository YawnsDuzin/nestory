"""카카오톡 인앱 브라우저 감지 — UA 기반.

PRD §9.3 P1 종료 기준 [v1.1·B2] 호환성 검증용.
"""
from fastapi import Request


def is_kakao_inapp(request: Request) -> bool:
    """User-Agent에 KAKAOTALK 토큰이 있으면 인앱 브라우저로 판정 (대소문자 무관)."""
    ua = request.headers.get("user-agent", "")
    return "KAKAOTALK" in ua.upper()


__all__ = ["is_kakao_inapp"]
