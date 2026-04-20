from fastapi.testclient import TestClient


def test_home_renders_html(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "Nestory" in r.text


def test_home_shows_login_cta_when_anonymous(client: TestClient) -> None:
    r = client.get("/")
    assert "시작하기" in r.text or "로그인" in r.text


def test_login_page_renders(client: TestClient) -> None:
    r = client.get("/auth/login")
    assert r.status_code == 200
    assert "이메일" in r.text
    assert "카카오" in r.text


def test_signup_page_renders(client: TestClient) -> None:
    r = client.get("/auth/signup")
    assert r.status_code == 200
    assert 'name="password"' in r.text


def test_home_shows_username_when_logged_in(client: TestClient) -> None:
    client.post(
        "/auth/signup",
        data={
            "email": "f@ex.com",
            "username": "frank",
            "display_name": "프랭크",
            "password": "password12",
        },
    )
    r = client.get("/")
    assert "@frank" in r.text
