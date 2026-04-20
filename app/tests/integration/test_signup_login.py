from fastapi.testclient import TestClient


def test_signup_creates_user_and_logs_in(client: TestClient) -> None:
    response = client.post(
        "/auth/signup",
        data={
            "email": "bob@example.com",
            "username": "bob",
            "display_name": "밥",
            "password": "supersecret",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert "nestory_session" in response.headers.get("set-cookie", "")


def test_login_succeeds_with_valid_credentials(client: TestClient) -> None:
    client.post("/auth/signup", data={
        "email": "carol@example.com", "username": "carol",
        "display_name": "캐럴", "password": "rightpass1",
    })
    fresh = TestClient(client.app)
    r = fresh.post(
        "/auth/login",
        data={"email": "carol@example.com", "password": "rightpass1"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_login_fails_with_wrong_password(client: TestClient) -> None:
    client.post("/auth/signup", data={
        "email": "dave@example.com", "username": "dave",
        "display_name": "데이브", "password": "rightpass",
    })
    r = client.post(
        "/auth/login",
        data={"email": "dave@example.com", "password": "WRONG"},
        follow_redirects=False,
    )
    assert r.status_code == 400


def test_logout_clears_session(client: TestClient) -> None:
    client.post("/auth/signup", data={
        "email": "erin@example.com", "username": "erin",
        "display_name": "에린", "password": "rightpass",
    })
    r = client.post("/auth/logout", follow_redirects=False)
    assert r.status_code == 303
