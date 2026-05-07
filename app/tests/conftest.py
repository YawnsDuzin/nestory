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


def _truncate_all_tables() -> None:
    """모든 도메인 테이블의 데이터를 비운다 (alembic_version 제외).

    `Base.metadata.tables.values()` 사용 — `sorted_tables` 는 순환 FK가 있을 때
    관련 테이블을 결과에서 제외하므로(SAWarning) 데이터 누수가 생긴다.
    TRUNCATE CASCADE 는 의존성 순서를 자체 처리하므로 정렬 불필요.
    """
    from app.db.base import Base
    table_names = [t.name for t in Base.metadata.tables.values() if t.name != "alembic_version"]
    if not table_names:
        return
    with SessionLocal() as session:
        joined = ", ".join(table_names)
        session.execute(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE"))
        session.commit()


@pytest.fixture(autouse=True)
def _cleanup_db():
    """각 테스트 전후로 모든 테이블 TRUNCATE — 이전 세션 잔존 데이터·테스트 간 누수 모두 차단."""
    _truncate_all_tables()
    yield
    _truncate_all_tables()


def _all_subclasses(cls):
    """Return every subclass of `cls` recursively, excluding `cls` itself."""
    seen = set()
    stack = [cls]
    while stack:
        c = stack.pop()
        for sub in c.__subclasses__():
            if sub not in seen:
                seen.add(sub)
                stack.append(sub)
                yield sub


def _bind_factories(session: Session) -> None:
    """Inject `session` into every BaseFactory subclass.

    Importing `app.tests.factories` triggers registration of every factory
    declared in submodules. We then walk the subclass tree and patch
    `_meta.sqlalchemy_session` so that `Factory.create()` uses the test session.
    """
    import app.tests.factories  # noqa: F401  # registers all factory classes
    from app.tests.factories._base import BaseFactory

    for cls in _all_subclasses(BaseFactory):
        cls._meta.sqlalchemy_session = session


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        _bind_factories(session)
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
