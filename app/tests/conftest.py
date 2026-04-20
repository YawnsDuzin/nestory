import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _ensure_db_ready() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


@pytest.fixture(autouse=True)
def _cleanup_db():
    """모든 테스트 후 테이블 TRUNCATE. TestClient 경유 데이터도 정리됨."""
    yield
    with SessionLocal() as session:
        session.execute(text("TRUNCATE TABLE users, regions RESTART IDENTITY CASCADE"))
        session.commit()


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
