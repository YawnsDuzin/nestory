import base64
import json
import os

from dotenv import load_dotenv

# ⚠️ CRITICAL — dev DB 보호 가드. autouse `_cleanup_db`가 모든 도메인 테이블을
# TRUNCATE CASCADE 하므로 반드시 별도 test DB에서 실행해야 한다. dev/test 공용
# DB 사용 사고를 두 번 겪고 도입 (2026-05-13). 두 URL이 같으면 import 시점에 fail.
#
# .env 예:
#   DATABASE_URL=postgresql+psycopg://nestory:nestory@localhost:5432/nestory   # dev
#   TEST_DATABASE_URL=postgresql+psycopg://nestory:nestory@localhost:5433/nestory_test  # test
load_dotenv()
_TEST_DB_URL = (os.environ.get("TEST_DATABASE_URL") or "").strip()
_DEV_DB_URL = (os.environ.get("DATABASE_URL") or "").strip()
if not _TEST_DB_URL:
    raise RuntimeError(
        "TEST_DATABASE_URL not set. pytest TRUNCATEs all tables — refusing to run "
        "without a dedicated test DB. Set TEST_DATABASE_URL in .env to a non-dev DB "
        "(e.g. postgresql+psycopg://nestory:nestory@localhost:5433/nestory)."
    )
if _DEV_DB_URL and _TEST_DB_URL == _DEV_DB_URL:
    raise RuntimeError(
        f"TEST_DATABASE_URL must differ from DATABASE_URL. Both = {_TEST_DB_URL!r}. "
        "Use a separate test DB instance."
    )
# Override DATABASE_URL so app.config / app.db.session pick up the test DB before
# any app module touches the engine.
os.environ["DATABASE_URL"] = _TEST_DB_URL

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from itsdangerous import TimestampSigner  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.models  # noqa: F401, E402  # Base.metadata에 모든 모델 등록
from app.config import get_settings  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402


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
        # 미완료 transaction(SELECT FOR UPDATE 등) 명시 정리 — 다음 테스트의
        # autouse _cleanup_db TRUNCATE가 PG row lock 대기로 hang하는 상황 방지.
        session.rollback()
        session.close()


@pytest.fixture(autouse=True)
def _disable_rate_limit():
    """테스트에서는 rate limiter 비활성화 — flaky 회귀 방지."""
    from app.rate_limit import limiter

    limiter.enabled = False
    yield
    limiter.enabled = True


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def login(client: TestClient):
    """Test helper: log in as the given user_id. Returns a callable.

    Mirrors starlette SessionMiddleware: TimestampSigner(b64(json)).
    When session signing changes (CSRF in P1.5+), only this fixture needs an update.

    Usage:
        def test_x(client, db, login):
            user = UserFactory()
            login(user.id)
            r = client.get("/me/badge")
    """
    def _do_login(user_id: int) -> None:
        signer = TimestampSigner(get_settings().app_secret_key)
        raw = base64.b64encode(json.dumps({"user_id": user_id}).encode()).decode()
        cookie = signer.sign(raw.encode()).decode()
        client.cookies.set("nestory_session", cookie)
    return _do_login
