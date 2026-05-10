"""/healthz 확장 검증 — DB ping 추가."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_healthz_returns_ok_when_db_reachable(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "ok"
    assert "env" in body


def test_healthz_returns_503_when_db_unreachable(client: TestClient) -> None:
    """SessionLocal에서 예외가 발생하면 status='degraded' + 503 반환."""

    def _broken():
        raise RuntimeError("db unreachable simulation")

    with patch("app.main.SessionLocal", side_effect=_broken):
        r = client.get("/healthz")

    assert r.status_code == 503
    body = r.json()
    assert body["status"] == "degraded"
    assert body["db"] == "error"
