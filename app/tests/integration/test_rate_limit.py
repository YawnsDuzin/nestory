"""Rate limiter 적용 검증.

conftest의 _disable_rate_limit fixture가 default로 limiter를 끄지만,
이 파일에서는 명시적으로 enabled=True로 켜서 실제 throttle 동작을 검증한다.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.rate_limit import limiter


@pytest.fixture
def limiter_on():
    """이 테스트만 rate limit 활성화."""
    limiter.reset()
    limiter.enabled = True
    yield
    limiter.enabled = False
    limiter.reset()


def test_login_rate_limit_returns_429_after_threshold(
    client: TestClient, limiter_on,
) -> None:
    """/auth/login은 분당 10회 — 11번째 요청부터 429."""
    payload = {"email": "nobody@example.com", "password": "x"}
    # 잘못된 자격 → 400. 그래도 429 throttle은 카운트됨.
    for _ in range(10):
        r = client.post("/auth/login", data=payload, follow_redirects=False)
        assert r.status_code == 400, f"unexpected {r.status_code}"
    r11 = client.post("/auth/login", data=payload, follow_redirects=False)
    assert r11.status_code == 429
    assert "요청이 너무 많습니다" in r11.json()["detail"]


def test_signup_rate_limit_returns_429_after_threshold(
    client: TestClient, limiter_on,
) -> None:
    """/auth/signup은 분당 5회 — 6번째 요청부터 429."""
    for i in range(5):
        r = client.post(
            "/auth/signup",
            data={
                "email": f"new{i}@example.com",
                "username": f"new{i}",
                "display_name": "Test",
                "password": "password123",
            },
            follow_redirects=False,
        )
        assert r.status_code in (303, 400), f"got {r.status_code}"
    r6 = client.post(
        "/auth/signup",
        data={
            "email": "new6@example.com",
            "username": "new6",
            "display_name": "Test",
            "password": "password123",
        },
        follow_redirects=False,
    )
    assert r6.status_code == 429


def test_default_no_rate_limit_in_test_env(client: TestClient) -> None:
    """default conftest fixture는 limiter 비활성화 — 11번째도 정상 처리."""
    payload = {"email": "nobody@example.com", "password": "x"}
    for _ in range(11):
        r = client.post("/auth/login", data=payload, follow_redirects=False)
        assert r.status_code == 400
