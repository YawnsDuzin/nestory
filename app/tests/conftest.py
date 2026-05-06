import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

import app.models  # noqa: F401  # Base.metadata에 모든 모델 등록
from app.db.session import SessionLocal, engine
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _ensure_db_ready() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


@pytest.fixture(autouse=True)
def _cleanup_db():
    """모든 테스트 후 모든 테이블 TRUNCATE. SQLAlchemy 메타데이터 기반 동적 수집."""
    yield
    from app.db.base import Base
    table_names = [t.name for t in Base.metadata.sorted_tables if t.name != "alembic_version"]
    if not table_names:
        return
    with SessionLocal() as session:
        joined = ", ".join(table_names)
        session.execute(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE"))
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
