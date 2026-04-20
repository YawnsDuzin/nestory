# Nestory Phase 0 (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nestory의 운영 가능한 최소 골격 — 로컬에서 `uv run uvicorn app.main:app`으로 기동되고, 이메일/카카오 로그인 후 빈 홈 페이지가 렌더되며, Raspberry Pi 배포 및 일 1회 `pg_dump` 백업이 자동 실행되는 상태를 3주 내 완성한다.

**Architecture:** Python 3.12 · FastAPI · PostgreSQL 16 · SQLAlchemy 2.x + Alembic · Jinja2 SSR + HTMX + Alpine.js · argon2id + itsdangerous 세션 쿠키 + Kakao OAuth 2.0. 호스팅은 Raspberry Pi 4B + Cloudflare Tunnel. 빌드 단계 없이 CDN으로 Tailwind/HTMX/Alpine 로드 (OI-4 결정 전 임시).

**Tech Stack:** Python 3.12, FastAPI, Uvicorn, SQLAlchemy 2.x, Alembic, PostgreSQL 16, Jinja2, HTMX 1.9+, Alpine.js 3+, Tailwind CSS (CDN), itsdangerous, argon2-cffi, httpx (for Kakao API), structlog, sentry-sdk, pytest, factory-boy, uv (패키지 매니저), Docker Compose (로컬 DB), Nginx, systemd, cloudflared.

---

## Phase 0 잠정 결정 (Phase 0 내 확정 필요)

이 계획은 아래 기본값을 **잠정 가정**으로 진행한다. Phase 0 종료 전 재확인하고, 최종 결정과 다르면 해당 태스크 결과물을 조정한다.

| OI | 잠정 가정 | 영향 범위 |
|---|---|---|
| OI-1 | 수도권 5개 시군: 양평 · 가평 · 남양주 · 춘천 · 홍천 | Task 8 (seed 스크립트) |
| OI-4 | Tailwind CSS CDN (`cdn.tailwindcss.com`) | Task 15 (base layout) |
| OI-5 | 첫 관리자는 본인 — `ADMIN_EMAIL` ENV로 지정 | Task 14 (admin bootstrap) |
| OI-7 | Phase 0 예산 0원 — Sentry/UptimeRobot 무료 티어, 도메인 미정 (Cloudflare 하위도메인 임시 사용) | Task 18, 26 |
| OI-9 | 로고 없음, 텍스트 "Nestory" + 기본 색상 (Tailwind slate/green) | Task 15 |
| OI-10 | 도메인 미정 → `NESTORY_DOMAIN` ENV 변수로 처리 | Task 22, 24 |

---

## 파일 구조 개요

Phase 0 종료 시 저장소는 다음과 같은 구조:

```
nestory/
├── app/
│   ├── __init__.py
│   ├── main.py                   # FastAPI 엔트리, 라우터 마운트
│   ├── config.py                 # pydantic-settings
│   ├── deps.py                   # DB 세션, current_user, admin_required
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py               # DeclarativeBase
│   │   ├── session.py            # engine, SessionLocal, get_db
│   │   └── migrations/           # Alembic (env.py, versions/)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py               # User (badge_level enum 포함)
│   │   └── region.py             # Region
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── auth.py               # SignupForm, LoginForm
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth.py               # 비밀번호 해싱·검증, 세션 생성
│   │   └── kakao.py              # OAuth start/callback 로직
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── pages.py              # GET /, /auth/login, /auth/signup
│   │   └── auth.py               # POST /auth/login, /auth/logout, kakao
│   ├── templates/
│   │   ├── base.html
│   │   ├── pages/
│   │   │   ├── home.html
│   │   │   ├── login.html
│   │   │   └── signup.html
│   │   └── components/
│   │       └── nav.html
│   ├── static/
│   │   └── js/
│   │       └── app.js
│   ├── templating.py             # Jinja2Templates 싱글톤
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py           # DB·client fixture
│       ├── unit/
│       │   ├── test_auth_service.py
│       │   └── test_kakao_service.py
│       └── integration/
│           ├── test_health.py
│           ├── test_signup_login.py
│           └── test_kakao_callback.py
├── alembic.ini
├── pyproject.toml                # uv
├── uv.lock
├── .env.example
├── .gitignore
├── docker-compose.local.yml      # 로컬 Postgres 전용
├── deploy/
│   ├── nginx.conf
│   ├── systemd/
│   │   ├── nestory.service
│   │   ├── nestory-backup.service
│   │   └── nestory-backup.timer
│   └── cloudflared-config.example.yml
├── scripts/
│   ├── seed_regions.py
│   ├── bootstrap_admin.py        # ADMIN_EMAIL 기반 role 승격
│   └── backup.sh
├── .github/
│   └── workflows/
│       └── ci.yml
└── README.md
```

---

## 주 단위 로드맵

- **Week 1 — 기반 (Tasks 1–9)**: 스캐폴딩 · config · FastAPI 엔트리 · 테스트 인프라 · DB 셋업 · User/Region 모델 · seed
- **Week 2 — 인증 & 템플릿 (Tasks 10–18)**: 이메일/비밀번호 회원가입·로그인 · 세션 · 카카오 OAuth · 관리자 부트스트랩 · Jinja2 베이스 · 홈/로그인 페이지
- **Week 3 — 관측·CI·배포 (Tasks 19–25)**: structlog · Sentry · GitHub Actions · Nginx · systemd · Cloudflare Tunnel · pg_dump 자동화 · 배포 런북

---

## Task 1: 프로젝트 스캐폴딩 (uv · pyproject · 디렉토리)

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Modify: `.gitignore`
- Create: `app/__init__.py`
- Create: `app/main.py` (최소 stub)
- Create: `app/tests/__init__.py`

- [ ] **Step 1: uv 설치 확인**

Run: `uv --version`
Expected: `uv 0.5.x` 이상. 없으면 `powershell -c "irm https://astral.sh/uv/install.ps1 | iex"` (Windows) 또는 `curl -LsSf https://astral.sh/uv/install.sh | sh`.

- [ ] **Step 2: `pyproject.toml` 작성**

```toml
[project]
name = "nestory"
version = "0.1.0"
description = "은퇴자 전원주택 커뮤니티 웹앱"
requires-python = ">=3.12,<3.13"
dependencies = [
  "fastapi>=0.115",
  "uvicorn[standard]>=0.32",
  "sqlalchemy>=2.0",
  "alembic>=1.13",
  "psycopg[binary]>=3.2",
  "pydantic-settings>=2.5",
  "jinja2>=3.1",
  "python-multipart>=0.0.12",
  "itsdangerous>=2.2",
  "argon2-cffi>=23.1",
  "httpx>=0.27",
  "structlog>=24.4",
  "sentry-sdk[fastapi]>=2.17",
  "pillow>=11.0",
]

[dependency-groups]
dev = [
  "pytest>=8.3",
  "pytest-asyncio>=0.24",
  "factory-boy>=3.3",
  "ruff>=0.7",
  "mypy>=1.13",
  "types-itsdangerous",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM"]

[tool.pytest.ini_options]
testpaths = ["app/tests"]
asyncio_mode = "auto"
```

- [ ] **Step 3: 의존성 설치 및 락파일 생성**

Run: `uv sync`
Expected: `uv.lock` 생성 + `.venv/` 디렉토리 생성. 설치 성공.

- [ ] **Step 4: `.gitignore` 보강**

기존 내용 확인 후 없는 항목만 추가:

```
.venv/
__pycache__/
*.pyc
.pytest_cache/
.ruff_cache/
.mypy_cache/
.env
.env.local
/media/
/data/
*.sqlite
*.db
.DS_Store
Thumbs.db
```

- [ ] **Step 5: `.env.example` 작성 (Phase 0에서 채울 모든 ENV)**

```
APP_ENV=local
APP_SECRET_KEY=change-me-with-openssl-rand-hex-32
DATABASE_URL=postgresql+psycopg://nestory:nestory@localhost:5432/nestory
KAKAO_CLIENT_ID=
KAKAO_CLIENT_SECRET=
KAKAO_REDIRECT_URI=http://localhost:8000/auth/kakao/callback
ADMIN_EMAIL=
SENTRY_DSN=
NESTORY_DOMAIN=localhost:8000
SESSION_COOKIE_SECURE=false
```

- [ ] **Step 6: 최소 stub 파일 작성**

`app/__init__.py`: 빈 파일
`app/tests/__init__.py`: 빈 파일
`app/main.py`:
```python
from fastapi import FastAPI

app = FastAPI(title="Nestory")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 7: 실행 확인**

Run: `uv run uvicorn app.main:app --reload`
Expected: `Uvicorn running on http://127.0.0.1:8000`.
브라우저에서 `http://localhost:8000/healthz` 접속 → `{"status":"ok"}` 확인.
Ctrl+C로 종료.

- [ ] **Step 8: 커밋**

```bash
git add pyproject.toml uv.lock .env.example .gitignore app/
git commit -m "feat: scaffold FastAPI project with uv, healthz endpoint"
```

---

## Task 2: Config 모듈 (pydantic-settings)

**Files:**
- Create: `app/config.py`
- Test: `app/tests/unit/test_config.py`

- [ ] **Step 1: 테스트 작성 (실패)**

`app/tests/unit/__init__.py`: 빈 파일
`app/tests/unit/test_config.py`:
```python
import os
from app.config import Settings


def test_settings_reads_env(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h/d")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    settings = Settings()
    assert settings.app_secret_key == "test-secret"
    assert settings.database_url == "postgresql+psycopg://u:p@h/d"
    assert settings.admin_email == "admin@example.com"
    assert settings.session_cookie_secure is False


def test_settings_derived_session_cookie_secure(monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "x")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h/d")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")
    settings = Settings()
    assert settings.session_cookie_secure is True
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest app/tests/unit/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 3: `app/config.py` 구현**

```python
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "local"
    app_secret_key: str
    database_url: str

    kakao_client_id: str = ""
    kakao_client_secret: str = ""
    kakao_redirect_uri: str = "http://localhost:8000/auth/kakao/callback"

    admin_email: str = ""
    sentry_dsn: str = ""
    nestory_domain: str = "localhost:8000"
    session_cookie_secure: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest app/tests/unit/test_config.py -v`
Expected: 2 passed.

- [ ] **Step 5: `app/main.py`에서 Settings 사용**

```python
from fastapi import FastAPI

from app.config import get_settings

settings = get_settings()

app = FastAPI(title="Nestory", debug=settings.app_env == "local")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
```

- [ ] **Step 6: 로컬 실행 검증**

로컬 `.env` 작성 (gitignore됨): `.env.example`을 복사해 `APP_SECRET_KEY`를 `$(openssl rand -hex 32)` 값으로, `DATABASE_URL`은 그대로.
Run: `uv run uvicorn app.main:app`
Expected: 기동 성공. `/healthz` 응답에 `"env":"local"`.

- [ ] **Step 7: 커밋**

```bash
git add app/config.py app/main.py app/tests/unit/
git commit -m "feat: add pydantic-settings config module with env loading"
```

---

## Task 3: 로컬 PostgreSQL (Docker Compose)

**Files:**
- Create: `docker-compose.local.yml`
- Modify: `README.md` (없으면 생성)

- [ ] **Step 1: `docker-compose.local.yml` 작성**

```yaml
services:
  postgres:
    image: postgres:16
    container_name: nestory-postgres-local
    environment:
      POSTGRES_USER: nestory
      POSTGRES_PASSWORD: nestory
      POSTGRES_DB: nestory
    ports:
      - "5432:5432"
    volumes:
      - nestory-pg-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U nestory -d nestory"]
      interval: 5s
      retries: 10

volumes:
  nestory-pg-data:
```

- [ ] **Step 2: 기동 및 연결 확인**

Run: `docker compose -f docker-compose.local.yml up -d`
Run: `docker exec nestory-postgres-local psql -U nestory -d nestory -c "SELECT 1;"`
Expected: 쿼리 결과 `1`. `docker compose ps` 에서 healthy 상태.

- [ ] **Step 3: `README.md` 기본 섹션 작성**

`README.md`:
```markdown
# Nestory

은퇴자와 전원주택 예비 입주자를 위한 커뮤니티 웹앱.

## 개발 환경 셋업

### 요구사항

- Python 3.12
- uv (https://docs.astral.sh/uv/)
- Docker Desktop (로컬 Postgres용)

### 시작

```bash
# 1. 의존성 설치
uv sync

# 2. 환경 변수 설정
cp .env.example .env
# APP_SECRET_KEY 생성: python -c "import secrets; print(secrets.token_hex(32))"

# 3. 로컬 Postgres 기동
docker compose -f docker-compose.local.yml up -d

# 4. (Alembic 추가 후) 마이그레이션 적용
uv run alembic upgrade head

# 5. 개발 서버 기동
uv run uvicorn app.main:app --reload
```

서버가 `http://localhost:8000`에서 실행됩니다.
```

- [ ] **Step 4: 커밋**

```bash
git add docker-compose.local.yml README.md
git commit -m "chore: add local Postgres via docker-compose and README bootstrap"
```

---

## Task 4: 테스트 인프라 (pytest · 통합 테스트 DB fixture)

**Files:**
- Create: `app/tests/conftest.py`
- Test: `app/tests/integration/__init__.py`
- Test: `app/tests/integration/test_health.py`

> **중요**: 테스트는 **실제 Postgres 인스턴스**에 연결한다 (mocks 금지). 로컬에서는 `docker-compose.local.yml`의 컨테이너를 재사용하되, 각 테스트 함수마다 트랜잭션을 롤백해 격리한다.

- [ ] **Step 1: 통합 테스트 디렉토리 생성**

`app/tests/integration/__init__.py`: 빈 파일.

- [ ] **Step 2: `conftest.py` 초안 (DB·클라이언트 fixture)**

SQLAlchemy 엔진·세션은 다음 태스크에서 만들 것이므로, 이 단계에서는 `TestClient` fixture만 작성.

`app/tests/conftest.py`:
```python
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
```

- [ ] **Step 3: healthz 통합 테스트 작성**

`app/tests/integration/test_health.py`:
```python
from fastapi.testclient import TestClient


def test_healthz_returns_ok(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "env" in body
```

- [ ] **Step 4: 테스트 실행**

Run: `uv run pytest -v`
Expected: test_health + test_config 포함해 3 passed.

- [ ] **Step 5: 커밋**

```bash
git add app/tests/
git commit -m "test: add pytest infra with TestClient fixture and healthz integration test"
```

---

## Task 5: SQLAlchemy Base + 세션 + Alembic 초기화

**Files:**
- Create: `app/db/__init__.py`
- Create: `app/db/base.py`
- Create: `app/db/session.py`
- Create: `app/deps.py`
- Create: `alembic.ini`
- Create: `app/db/migrations/env.py`
- Create: `app/db/migrations/script.py.mako`
- Create: `app/db/migrations/versions/.gitkeep`

- [ ] **Step 1: `app/db/__init__.py` 빈 파일**

- [ ] **Step 2: `app/db/base.py` 작성**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 3: `app/db/session.py` 작성**

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: `app/deps.py` 작성 (현재는 get_db만)**

```python
from app.db.session import get_db

__all__ = ["get_db"]
```

- [ ] **Step 5: Alembic 초기화**

Run: `uv run alembic init app/db/migrations`
Expected: `alembic.ini` + `app/db/migrations/env.py` + `script.py.mako` 생성.

- [ ] **Step 6: `alembic.ini` 수정**

`[alembic]` 섹션에서 `sqlalchemy.url` 주석 처리 (env.py에서 주입):
```
# sqlalchemy.url = driver://user:pass@localhost/dbname
```
`script_location = app/db/migrations` 확인.

- [ ] **Step 7: `app/db/migrations/env.py` 수정**

상단에 Settings 주입 + 모델 import를 위한 블록 추가:

```python
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from app.config import get_settings
from app.db.base import Base
# 모델은 추가되는 대로 import (autogenerate 용)
# from app.models import user, region  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", get_settings().database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 8: 빈 초기 리비전 생성**

Run: `uv run alembic revision -m "initial empty"`
Expected: `app/db/migrations/versions/xxxx_initial_empty.py` 생성.

- [ ] **Step 9: 적용 검증**

Run: `uv run alembic upgrade head`
Expected: `INFO [alembic.runtime.migration] Running upgrade -> xxxx, initial empty`.

DB 확인:
Run: `docker exec nestory-postgres-local psql -U nestory -d nestory -c "SELECT version_num FROM alembic_version;"`
Expected: 한 개 행 반환.

- [ ] **Step 10: 커밋**

```bash
git add alembic.ini app/db/ app/deps.py
git commit -m "feat: initialize SQLAlchemy base, session, and Alembic migrations"
```

---

## Task 6: User 모델 + 마이그레이션

**Files:**
- Create: `app/models/__init__.py`
- Create: `app/models/user.py`
- Create: `app/db/migrations/versions/<auto>_add_users_table.py` (autogenerate)
- Test: `app/tests/integration/test_user_model.py`

- [ ] **Step 1: 테스트 먼저 작성 (DB fixture 필요 — Task 5 이후 `conftest.py` 보강)**

`app/tests/conftest.py` 에 DB fixture 추가:

```python
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


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
```

> **참고**: 이 fixture는 커밋된 데이터를 유지한다. Task 7 직후 **truncate 기반 cleanup fixture**로 확장한다 (Task 7 Step 6).

- [ ] **Step 2: User 모델 테스트 작성**

`app/tests/integration/test_user_model.py`:
```python
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.user import BadgeLevel, User, UserRole


def test_create_user_with_defaults(db: Session) -> None:
    user = User(
        email=f"t{int(datetime.now(timezone.utc).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(timezone.utc).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    db.add(user)
    db.flush()

    assert user.id is not None
    assert user.role == UserRole.USER
    assert user.badge_level == BadgeLevel.INTERESTED
    assert user.created_at is not None
    assert user.deleted_at is None
```

- [ ] **Step 3: 테스트 실패 확인**

Run: `uv run pytest app/tests/integration/test_user_model.py -v`
Expected: FAIL — `ModuleNotFoundError: app.models.user`.

- [ ] **Step 4: `app/models/__init__.py`**

```python
from app.models.user import BadgeLevel, User, UserRole

__all__ = ["BadgeLevel", "User", "UserRole"]
```

- [ ] **Step 5: `app/models/user.py` 구현**

```python
import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class BadgeLevel(str, enum.Enum):
    INTERESTED = "interested"
    REGION_VERIFIED = "region_verified"
    RESIDENT = "resident"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    kakao_id: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(64))
    bio: Mapped[str | None] = mapped_column(String(500), nullable=True)

    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        default=UserRole.USER,
        server_default=UserRole.USER.value,
    )
    badge_level: Mapped[BadgeLevel] = mapped_column(
        Enum(BadgeLevel, name="badge_level"),
        default=BadgeLevel.INTERESTED,
        server_default=BadgeLevel.INTERESTED.value,
    )
    resident_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 6: Alembic env.py에서 모델 import 활성화**

`app/db/migrations/env.py` 에서 `# from app.models import user, region` 라인을 주석 해제하되 `region`은 제외:
```python
from app.models import user  # noqa: F401
```

- [ ] **Step 7: 마이그레이션 autogenerate**

Run: `uv run alembic revision --autogenerate -m "add users table"`
Expected: `versions/xxxx_add_users_table.py` 생성. 파일을 열어 `users` 테이블 + enum 타입 생성 코드를 확인.

- [ ] **Step 8: 마이그레이션 적용 & 테스트 통과 확인**

Run: `uv run alembic upgrade head`
Run: `uv run pytest app/tests/integration/test_user_model.py -v`
Expected: 1 passed.

- [ ] **Step 9: 커밋**

```bash
git add app/models/ app/db/migrations/ app/tests/conftest.py app/tests/integration/test_user_model.py
git commit -m "feat: add User model with role/badge_level enums and migration"
```

---

## Task 7: Region 모델 + 마이그레이션 + 테스트 격리 강화

**Files:**
- Create: `app/models/region.py`
- Modify: `app/models/__init__.py`
- Modify: `app/db/migrations/env.py`
- Create: `app/db/migrations/versions/<auto>_add_regions_table.py`
- Modify: `app/tests/conftest.py` (truncate fixture)
- Test: `app/tests/integration/test_region_model.py`

- [ ] **Step 1: 테스트 작성**

`app/tests/integration/test_region_model.py`:
```python
from sqlalchemy.orm import Session

from app.models.region import Region


def test_create_region(db: Session) -> None:
    region = Region(
        sido="경기도",
        sigungu="양평군",
        slug="yangpyeong",
        is_pilot=True,
    )
    db.add(region)
    db.flush()

    assert region.id is not None
    assert region.is_pilot is True
    assert region.created_at is not None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest app/tests/integration/test_region_model.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: `app/models/region.py` 구현**

```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Region(Base):
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(primary_key=True)
    sido: Mapped[str] = mapped_column(String(32))
    sigungu: Mapped[str] = mapped_column(String(64))
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_image: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_pilot: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 4: `app/models/__init__.py` 업데이트**

```python
from app.models.region import Region
from app.models.user import BadgeLevel, User, UserRole

__all__ = ["BadgeLevel", "Region", "User", "UserRole"]
```

- [ ] **Step 5: env.py에서 Region import 추가**

`app/db/migrations/env.py`:
```python
from app.models import region, user  # noqa: F401
```

- [ ] **Step 6: conftest.py에 autouse cleanup fixture 추가**

`app/tests/conftest.py` 전체를 다음으로 교체:

```python
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
```

> **주**: 현재 테이블이 users/regions 둘뿐이다. 이후 테이블이 추가되면 TRUNCATE 목록을 갱신하거나, `information_schema.tables` 기반 자동화로 개선 (Phase 1+).

- [ ] **Step 7: 마이그레이션 autogenerate**

Run: `uv run alembic revision --autogenerate -m "add regions table"`
파일에서 `regions` 테이블 생성 코드 확인.

- [ ] **Step 8: 적용 & 테스트 통과**

Run: `uv run alembic upgrade head`
Run: `uv run pytest -v`
Expected: 기존 테스트 포함 모두 passed.

- [ ] **Step 9: 커밋**

```bash
git add app/models/ app/db/migrations/versions/ app/db/migrations/env.py app/tests/
git commit -m "feat: add Region model with pilot flag and test truncate isolation"
```

---

## Task 8: 시군 seed 스크립트

**Files:**
- Create: `scripts/__init__.py`
- Create: `scripts/seed_regions.py`
- Test: `app/tests/integration/test_seed_regions.py`

- [ ] **Step 1: 테스트 작성**

`app/tests/integration/test_seed_regions.py`:
```python
from sqlalchemy.orm import Session

from app.models.region import Region
from scripts.seed_regions import PILOT_REGIONS, seed_regions


def test_seed_regions_inserts_pilot_set(db: Session) -> None:
    seed_regions(db)
    db.commit()

    rows = db.query(Region).all()
    assert len(rows) == len(PILOT_REGIONS)

    slugs = {r.slug for r in rows}
    assert {"yangpyeong", "gapyeong", "namyangju", "chuncheon", "hongcheon"} <= slugs
    assert all(r.is_pilot for r in rows)


def test_seed_regions_is_idempotent(db: Session) -> None:
    seed_regions(db)
    db.commit()
    seed_regions(db)
    db.commit()

    count = db.query(Region).count()
    assert count == len(PILOT_REGIONS)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest app/tests/integration/test_seed_regions.py -v`
Expected: FAIL — `ModuleNotFoundError: scripts.seed_regions`.

- [ ] **Step 3: `scripts/__init__.py` 빈 파일 생성**

- [ ] **Step 4: `scripts/seed_regions.py` 구현**

```python
"""파일럿 5개 시군을 regions 테이블에 주입 (idempotent).

OI-1 잠정 가정: 양평 · 가평 · 남양주 · 춘천 · 홍천.
Phase 0 중 최종 결정되면 이 목록을 갱신할 것.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.region import Region

PILOT_REGIONS: list[dict[str, str]] = [
    {"sido": "경기도", "sigungu": "양평군", "slug": "yangpyeong"},
    {"sido": "경기도", "sigungu": "가평군", "slug": "gapyeong"},
    {"sido": "경기도", "sigungu": "남양주시", "slug": "namyangju"},
    {"sido": "강원특별자치도", "sigungu": "춘천시", "slug": "chuncheon"},
    {"sido": "강원특별자치도", "sigungu": "홍천군", "slug": "hongcheon"},
]


def seed_regions(db: Session) -> None:
    existing_slugs = {slug for (slug,) in db.query(Region.slug).all()}
    for row in PILOT_REGIONS:
        if row["slug"] in existing_slugs:
            continue
        db.add(Region(
            sido=row["sido"],
            sigungu=row["sigungu"],
            slug=row["slug"],
            is_pilot=True,
        ))


def main() -> None:
    db = SessionLocal()
    try:
        seed_regions(db)
        db.commit()
        print(f"Seeded {len(PILOT_REGIONS)} pilot regions (idempotent).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run pytest app/tests/integration/test_seed_regions.py -v`
Expected: 2 passed.

- [ ] **Step 6: 실행 검증**

Run: `uv run python -m scripts.seed_regions`
Expected: `Seeded 5 pilot regions (idempotent).`
Run again: 같은 출력, 중복 insert 없음.

확인:
Run: `docker exec nestory-postgres-local psql -U nestory -d nestory -c "SELECT slug FROM regions;"`
Expected: 5개 행.

- [ ] **Step 7: 커밋**

```bash
git add scripts/ app/tests/integration/test_seed_regions.py
git commit -m "feat: add idempotent region seed script with 5 pilot sigungu"
```

---

## Task 9: 비밀번호 해싱 서비스 (argon2)

**Files:**
- Create: `app/services/__init__.py`
- Create: `app/services/auth.py`
- Test: `app/tests/unit/test_auth_service.py`

- [ ] **Step 1: 테스트 작성**

`app/tests/unit/test_auth_service.py`:
```python
import pytest

from app.services.auth import hash_password, verify_password


def test_hash_password_returns_argon2_string() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed.startswith("$argon2id$")
    assert len(hashed) > 50


def test_verify_password_correct() -> None:
    hashed = hash_password("secret")
    assert verify_password("secret", hashed) is True


def test_verify_password_incorrect() -> None:
    hashed = hash_password("secret")
    assert verify_password("wrong", hashed) is False


def test_verify_password_none_hash_returns_false() -> None:
    assert verify_password("any", None) is False


@pytest.mark.parametrize("pw", ["", "  ", "\n"])
def test_hash_password_rejects_blank(pw: str) -> None:
    with pytest.raises(ValueError):
        hash_password(pw)
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest app/tests/unit/test_auth_service.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: `app/services/__init__.py` 빈 파일 생성**

- [ ] **Step 4: `app/services/auth.py` 구현**

```python
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    if not password or not password.strip():
        raise ValueError("password must be non-blank")
    return _hasher.hash(password)


def verify_password(password: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        _hasher.verify(hashed, password)
        return True
    except VerifyMismatchError:
        return False
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run pytest app/tests/unit/test_auth_service.py -v`
Expected: 6 passed.

- [ ] **Step 6: 커밋**

```bash
git add app/services/
git commit -m "feat: add argon2id password hashing service"
```

---

## Task 10: 세션 미들웨어 + 사용자 생성 저수준 API

**Files:**
- Modify: `app/main.py`
- Modify: `app/services/auth.py`
- Modify: `app/deps.py`
- Test: `app/tests/unit/test_auth_service.py` (추가)

- [ ] **Step 1: 테스트 추가 (사용자 생성/조회)**

`app/tests/integration/test_auth_service_db.py`:
```python
from sqlalchemy.orm import Session

from app.models.user import User
from app.services.auth import create_user_with_password, find_user_by_email


def test_create_and_find_user(db: Session) -> None:
    user = create_user_with_password(
        db,
        email="alice@example.com",
        username="alice",
        display_name="앨리스",
        password="horse-staple-42",
    )
    db.commit()

    assert user.id is not None
    assert user.email == "alice@example.com"
    assert user.password_hash is not None and user.password_hash.startswith("$argon2id$")

    found = find_user_by_email(db, "alice@example.com")
    assert found is not None
    assert found.id == user.id


def test_create_user_duplicate_email_raises(db: Session) -> None:
    create_user_with_password(db, email="dup@example.com", username="d1", display_name="d", password="x12345")
    db.commit()

    import pytest
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        create_user_with_password(db, email="dup@example.com", username="d2", display_name="d", password="x12345")
        db.commit()
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest app/tests/integration/test_auth_service_db.py -v`
Expected: FAIL — `ImportError` for `create_user_with_password`.

- [ ] **Step 3: `app/services/auth.py` 확장**

파일 끝에 추가:
```python
from sqlalchemy.orm import Session

from app.models.user import User


def create_user_with_password(
    db: Session,
    *,
    email: str,
    username: str,
    display_name: str,
    password: str,
) -> User:
    user = User(
        email=email.lower().strip(),
        username=username.strip(),
        display_name=display_name.strip(),
        password_hash=hash_password(password),
    )
    db.add(user)
    db.flush()
    return user


def find_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.lower().strip()).one_or_none()
```

- [ ] **Step 4: 세션 미들웨어 추가 (main.py)**

`app/main.py`:
```python
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings

settings = get_settings()

app = FastAPI(title="Nestory", debug=settings.app_env == "local")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.app_secret_key,
    session_cookie="nestory_session",
    max_age=60 * 60 * 24 * 30,
    same_site="lax",
    https_only=settings.session_cookie_secure,
)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
```

- [ ] **Step 5: current_user dependency 추가**

`app/deps.py`:
```python
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User, UserRole


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


def require_user(user: User | None = Depends(get_current_user)) -> User:
    from fastapi import HTTPException, status
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login required")
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    from fastapi import HTTPException, status
    if user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user


__all__ = ["get_db", "get_current_user", "require_user", "require_admin"]
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `uv run pytest -v`
Expected: 모두 passed.

- [ ] **Step 7: 커밋**

```bash
git add app/main.py app/deps.py app/services/auth.py app/tests/integration/test_auth_service_db.py
git commit -m "feat: add session middleware and create_user/find_user DB services"
```

---

## Task 11: 회원가입 · 로그인 라우터 (HTML form)

**Files:**
- Create: `app/schemas/__init__.py`
- Create: `app/schemas/auth.py`
- Create: `app/routers/__init__.py`
- Create: `app/routers/auth.py`
- Modify: `app/main.py` (라우터 포함)
- Test: `app/tests/integration/test_signup_login.py`

- [ ] **Step 1: 통합 테스트 작성**

`app/tests/integration/test_signup_login.py`:
```python
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
    # session cookie set
    assert "nestory_session" in response.headers.get("set-cookie", "")


def test_login_succeeds_with_valid_credentials(client: TestClient) -> None:
    client.post("/auth/signup", data={
        "email": "carol@example.com", "username": "carol",
        "display_name": "캐럴", "password": "rightpass1",
    })
    # 새 세션으로 로그인 시도
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
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest app/tests/integration/test_signup_login.py -v`
Expected: FAIL — 404 또는 모듈 없음.

- [ ] **Step 3: 스키마 작성**

`app/schemas/__init__.py`: 빈 파일
`app/schemas/auth.py`:
```python
from pydantic import BaseModel, EmailStr, Field


class SignupForm(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=32, pattern=r"^[a-z0-9_]+$")
    display_name: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class LoginForm(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
```

`pyproject.toml`에 `email-validator>=2.2` 의존성 추가 → `uv sync` 재실행.

- [ ] **Step 4: 라우터 작성**

`app/routers/__init__.py`: 빈 파일
`app/routers/auth.py`:
```python
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.deps import get_db
from app.schemas.auth import LoginForm, SignupForm
from app.services.auth import (
    create_user_with_password,
    find_user_by_email,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup")
async def signup(
    request: Request,
    email: str = Form(...),
    username: str = Form(...),
    display_name: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    form = SignupForm(email=email, username=username, display_name=display_name, password=password)
    try:
        user = create_user_with_password(
            db,
            email=form.email,
            username=form.username,
            display_name=form.display_name,
            password=form.password,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email or username already registered")

    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    form = LoginForm(email=email, password=password)
    user = find_user_by_email(db, form.email)
    if user is None or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid credentials")

    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
```

- [ ] **Step 5: `app/main.py` 에 라우터 포함**

`app/main.py` 끝에 추가:
```python
from app.routers import auth as auth_router

app.include_router(auth_router.router)
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `uv run pytest app/tests/integration/test_signup_login.py -v`
Expected: 4 passed.

- [ ] **Step 7: 커밋**

```bash
git add app/schemas/ app/routers/ app/main.py pyproject.toml uv.lock
git commit -m "feat: add email/password signup, login, logout routes with session"
```

---

## Task 12: Kakao OAuth 서비스 (unit, httpx 목)

**Files:**
- Create: `app/services/kakao.py`
- Test: `app/tests/unit/test_kakao_service.py`

> **Note**: Kakao 외부 HTTP 호출 자체는 단위 테스트에서 `httpx.MockTransport`로 가로막는다 ("integration tests must hit a real database, not mocks" 원칙은 DB에 한정되며, 외부 제3자 API 호출은 명확히 mock 대상).

- [ ] **Step 1: 테스트 작성**

`app/tests/unit/test_kakao_service.py`:
```python
import httpx
import pytest

from app.services.kakao import KakaoProfile, exchange_code_for_profile, build_authorize_url


def test_build_authorize_url_includes_state_and_params() -> None:
    url = build_authorize_url(client_id="abc", redirect_uri="https://x/cb", state="s1")
    assert "client_id=abc" in url
    assert "redirect_uri=https%3A%2F%2Fx%2Fcb" in url
    assert "state=s1" in url
    assert "response_type=code" in url
    assert url.startswith("https://kauth.kakao.com/oauth/authorize")


@pytest.mark.asyncio
async def test_exchange_code_returns_profile() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/oauth/token":
            return httpx.Response(200, json={"access_token": "TOK", "token_type": "bearer"})
        if request.url.path == "/v2/user/me":
            return httpx.Response(200, json={
                "id": 123456,
                "kakao_account": {"email": "kuser@kakao.com", "profile": {"nickname": "닉"}},
            })
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http:
        profile = await exchange_code_for_profile(
            http,
            code="CODE",
            client_id="cid",
            client_secret="csec",
            redirect_uri="https://x/cb",
        )

    assert isinstance(profile, KakaoProfile)
    assert profile.kakao_id == "123456"
    assert profile.email == "kuser@kakao.com"
    assert profile.nickname == "닉"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest app/tests/unit/test_kakao_service.py -v`
Expected: FAIL.

- [ ] **Step 3: `app/services/kakao.py` 구현**

```python
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
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest app/tests/unit/test_kakao_service.py -v`
Expected: 2 passed.

- [ ] **Step 5: 커밋**

```bash
git add app/services/kakao.py app/tests/unit/test_kakao_service.py
git commit -m "feat: add Kakao OAuth service with token exchange and profile fetch"
```

---

## Task 13: Kakao OAuth 콜백 라우터 + users upsert

**Files:**
- Modify: `app/routers/auth.py`
- Modify: `app/services/auth.py` (upsert helper)
- Test: `app/tests/integration/test_kakao_callback.py`

- [ ] **Step 1: upsert 헬퍼 테스트**

`app/tests/integration/test_auth_service_db.py` 에 추가:
```python
from app.services.auth import upsert_user_by_kakao_id


def test_upsert_by_kakao_id_creates_then_updates(db) -> None:
    u1 = upsert_user_by_kakao_id(db, kakao_id="K1", email=None, nickname="닉네임")
    db.commit()
    assert u1.id is not None
    assert u1.kakao_id == "K1"
    assert u1.display_name == "닉네임"
    assert u1.username.startswith("k_")  # 자동 생성

    u2 = upsert_user_by_kakao_id(db, kakao_id="K1", email="k@kakao.com", nickname="새닉")
    db.commit()
    assert u2.id == u1.id
    assert u2.email == "k@kakao.com"
    assert u2.display_name == "새닉"
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest app/tests/integration/test_auth_service_db.py::test_upsert_by_kakao_id_creates_then_updates -v`
Expected: FAIL — import 에러.

- [ ] **Step 3: `app/services/auth.py` 에 upsert 추가**

```python
import secrets


def upsert_user_by_kakao_id(
    db: Session,
    *,
    kakao_id: str,
    email: str | None,
    nickname: str | None,
) -> User:
    user = db.query(User).filter(User.kakao_id == kakao_id).one_or_none()
    if user is None:
        placeholder_email = email or f"kakao_{kakao_id}@nestory.local"
        username = f"k_{kakao_id[:6]}_{secrets.token_hex(3)}"
        user = User(
            email=placeholder_email.lower(),
            kakao_id=kakao_id,
            username=username,
            display_name=(nickname or "카카오 사용자")[:64],
        )
        db.add(user)
        db.flush()
        return user

    if email:
        user.email = email.lower()
    if nickname:
        user.display_name = nickname[:64]
    db.flush()
    return user
```

- [ ] **Step 4: 콜백 테스트 작성**

`app/tests/integration/test_kakao_callback.py`:
```python
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient

from app.services.kakao import KakaoProfile


def test_kakao_start_redirects_to_authorize(client: TestClient) -> None:
    r = client.get("/auth/kakao/start", follow_redirects=False)
    assert r.status_code == 307
    assert r.headers["location"].startswith("https://kauth.kakao.com/oauth/authorize")


def test_kakao_callback_creates_user_and_logs_in(client: TestClient) -> None:
    # state를 미리 세션에 심으려면 /auth/kakao/start를 먼저 호출
    client.get("/auth/kakao/start", follow_redirects=False)
    state = next((c.value for c in client.cookies.jar if c.name == "nestory_session"), None)
    # Actually use a monkeypatched service to bypass external HTTP
    fake_profile = KakaoProfile(kakao_id="99999", email="k@kakao.com", nickname="테스터")

    async def fake_exchange(*args, **kwargs):
        return fake_profile

    with patch("app.routers.auth.exchange_code_for_profile", side_effect=fake_exchange):
        # state는 시작 시 세션에 저장된 값을 재사용해야 함 → 테스트에서는 start를 호출 후
        # session의 kakao_state 값을 같이 보내야 함. TestClient의 세션 persist를 활용:
        start = client.get("/auth/kakao/start", follow_redirects=False)
        loc = start.headers["location"]
        # state 쿼리 추출
        from urllib.parse import parse_qs, urlparse
        qs = parse_qs(urlparse(loc).query)
        st = qs["state"][0]

        r = client.get(f"/auth/kakao/callback?code=C&state={st}", follow_redirects=False)
        assert r.status_code == 303
        assert r.headers["location"] == "/"


def test_kakao_callback_rejects_bad_state(client: TestClient) -> None:
    r = client.get("/auth/kakao/callback?code=C&state=wrong", follow_redirects=False)
    assert r.status_code == 400
```

- [ ] **Step 5: 라우터에 Kakao 경로 추가**

`app/routers/auth.py` 끝에 추가:
```python
import secrets as _secrets

import httpx as _httpx

from app.config import get_settings as _get_settings
from app.services.auth import upsert_user_by_kakao_id as _upsert
from app.services.kakao import build_authorize_url, exchange_code_for_profile


@router.get("/kakao/start")
async def kakao_start(request: Request) -> RedirectResponse:
    settings = _get_settings()
    state = _secrets.token_urlsafe(24)
    request.session["kakao_state"] = state
    url = build_authorize_url(
        client_id=settings.kakao_client_id,
        redirect_uri=settings.kakao_redirect_uri,
        state=state,
    )
    return RedirectResponse(url)


@router.get("/kakao/callback")
async def kakao_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    settings = _get_settings()
    expected = request.session.pop("kakao_state", None)
    if not expected or expected != state:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid state")

    async with _httpx.AsyncClient(timeout=10.0) as http:
        profile = await exchange_code_for_profile(
            http,
            code=code,
            client_id=settings.kakao_client_id,
            client_secret=settings.kakao_client_secret,
            redirect_uri=settings.kakao_redirect_uri,
        )

    user = _upsert(db, kakao_id=profile.kakao_id, email=profile.email, nickname=profile.nickname)
    db.commit()
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
```

- [ ] **Step 6: 모든 테스트 통과 확인**

Run: `uv run pytest -v`
Expected: 전체 통과.

- [ ] **Step 7: 커밋**

```bash
git add app/services/auth.py app/routers/auth.py app/tests/integration/
git commit -m "feat: add Kakao OAuth start/callback routes with upsert_user_by_kakao_id"
```

---

## Task 14: Admin 부트스트랩 스크립트

**Files:**
- Create: `scripts/bootstrap_admin.py`
- Test: `app/tests/integration/test_bootstrap_admin.py`

- [ ] **Step 1: 테스트 작성**

`app/tests/integration/test_bootstrap_admin.py`:
```python
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.services.auth import create_user_with_password
from scripts.bootstrap_admin import promote_admin


def test_promote_existing_user_to_admin(db: Session) -> None:
    user = create_user_with_password(
        db, email="me@example.com", username="me",
        display_name="Me", password="secret12",
    )
    db.commit()

    promote_admin(db, email="me@example.com")
    db.commit()
    db.refresh(user)

    assert user.role == UserRole.ADMIN


def test_promote_missing_user_raises(db: Session) -> None:
    import pytest
    with pytest.raises(LookupError):
        promote_admin(db, email="nobody@example.com")


def test_promote_noop_when_already_admin(db: Session) -> None:
    user = create_user_with_password(
        db, email="a@a.com", username="a", display_name="A", password="secret12",
    )
    user.role = UserRole.ADMIN
    db.commit()

    # Should not raise, should remain admin
    promote_admin(db, email="a@a.com")
    db.commit()
    db.refresh(user)
    assert user.role == UserRole.ADMIN
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest app/tests/integration/test_bootstrap_admin.py -v`
Expected: FAIL.

- [ ] **Step 3: 스크립트 작성**

`scripts/bootstrap_admin.py`:
```python
"""ENV ADMIN_EMAIL로 지정된 계정을 admin 역할로 승격.

회원가입은 별도로 해야 하며, 이 스크립트는 기존 사용자의 role만 바꾼다.
OI-5 잠정: 초기 관리자는 본인 1명.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import SessionLocal
from app.models.user import User, UserRole


def promote_admin(db: Session, *, email: str) -> User:
    user = db.query(User).filter(User.email == email.lower().strip()).one_or_none()
    if user is None:
        raise LookupError(f"No user found with email {email!r}")
    user.role = UserRole.ADMIN
    db.flush()
    return user


def main() -> None:
    settings = get_settings()
    if not settings.admin_email:
        raise SystemExit("ADMIN_EMAIL env var is empty")

    db = SessionLocal()
    try:
        user = promote_admin(db, email=settings.admin_email)
        db.commit()
        print(f"Promoted {user.email} (id={user.id}) to admin.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `uv run pytest app/tests/integration/test_bootstrap_admin.py -v`
Expected: 3 passed.

- [ ] **Step 5: 커밋**

```bash
git add scripts/bootstrap_admin.py app/tests/integration/test_bootstrap_admin.py
git commit -m "feat: add admin bootstrap script promoting ADMIN_EMAIL user"
```

---

## Task 15: Base Jinja2 레이아웃 (HTMX · Alpine · Tailwind CDN)

**Files:**
- Create: `app/templating.py`
- Create: `app/templates/base.html`
- Create: `app/templates/components/nav.html`
- Create: `app/static/js/app.js`
- Modify: `app/main.py` (StaticFiles 마운트)

- [ ] **Step 1: `app/templating.py` 생성 (순환 import 방지용 싱글톤)**

```python
from pathlib import Path

from fastapi.templating import Jinja2Templates

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=BASE_DIR / "templates")
```

- [ ] **Step 2: `app/main.py`에서 StaticFiles 마운트 추가**

Task 10까지 작성된 `app/main.py`에 `StaticFiles` 마운트 한 줄을 추가. 전체 파일:

```python
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import get_settings
from app.routers import auth as auth_router

settings = get_settings()
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Nestory", debug=settings.app_env == "local")
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.app_secret_key,
    session_cookie="nestory_session",
    max_age=60 * 60 * 24 * 30,
    same_site="lax",
    https_only=settings.session_cookie_secure,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(auth_router.router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}
```

> **주**: `configure_logging`·`init_sentry` 는 Task 17·18에서 별도로 추가된다.

- [ ] **Step 3: `app/templates/base.html`**

```html
<!doctype html>
<html lang="ko" class="h-full">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Nestory{% endblock %}</title>
  <meta name="description" content="은퇴자 전원주택 커뮤니티 — 정착의 전 과정을 아카이브합니다.">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/htmx.org@1.9.12" defer></script>
  <script src="https://unpkg.com/alpinejs@3.14.1/dist/cdn.min.js" defer></script>
  <script src="{{ url_for('static', path='/js/app.js') }}" defer></script>
</head>
<body class="h-full bg-slate-50 text-slate-900 antialiased">
  {% include "components/nav.html" %}
  <main class="mx-auto max-w-3xl px-4 py-6">
    {% block content %}{% endblock %}
  </main>
  <footer class="mt-16 py-6 text-center text-xs text-slate-500">
    © Nestory · 전원주택 정착의 여정
  </footer>
</body>
</html>
```

- [ ] **Step 4: `app/templates/components/nav.html`**

```html
<nav class="sticky top-0 z-10 border-b border-slate-200 bg-white">
  <div class="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
    <a href="/" class="text-lg font-bold text-emerald-700">Nestory</a>
    <div class="flex items-center gap-3 text-sm">
      {% if current_user %}
        <span class="text-slate-600">@{{ current_user.username }}</span>
        <form method="post" action="/auth/logout" class="inline">
          <button type="submit" class="text-slate-500 hover:text-slate-900">로그아웃</button>
        </form>
      {% else %}
        <a href="/auth/login" class="text-slate-600 hover:text-slate-900">로그인</a>
        <a href="/auth/signup" class="rounded-md bg-emerald-600 px-3 py-1 text-white hover:bg-emerald-700">시작하기</a>
      {% endif %}
    </div>
  </div>
</nav>
```

- [ ] **Step 5: `app/static/js/app.js` 플레이스홀더**

```javascript
// Nestory client bootstrap.
// HTMX와 Alpine은 CDN으로 자동 부팅됨. 여기는 공유 헬퍼 전용.
document.addEventListener('htmx:responseError', (e) => {
  console.error('HTMX error', e.detail);
});
```

- [ ] **Step 6: 수동 렌더 확인**

Run: `uv run uvicorn app.main:app --reload`
접속: `http://localhost:8000/static/js/app.js` → 파일 내용 응답.
접속: `http://localhost:8000/healthz` → 여전히 JSON 응답.

- [ ] **Step 7: 커밋**

```bash
git add app/templating.py app/templates/ app/static/ app/main.py
git commit -m "feat: add Jinja2 base layout with Tailwind/HTMX/Alpine CDN and nav"
```

---

## Task 16: 홈 · 로그인 · 회원가입 페이지 (pages 라우터)

**Files:**
- Create: `app/routers/pages.py`
- Create: `app/templates/pages/home.html`
- Create: `app/templates/pages/login.html`
- Create: `app/templates/pages/signup.html`
- Modify: `app/main.py`
- Test: `app/tests/integration/test_pages.py`

- [ ] **Step 1: 통합 테스트 작성**

`app/tests/integration/test_pages.py`:
```python
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
    client.post("/auth/signup", data={
        "email": "f@ex.com", "username": "frank",
        "display_name": "프랭크", "password": "password12",
    })
    r = client.get("/")
    assert "@frank" in r.text
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest app/tests/integration/test_pages.py -v`
Expected: FAIL — 404.

- [ ] **Step 3: `app/routers/pages.py` 작성**

```python
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.deps import get_current_user
from app.models.user import User
from app.templating import templates

router = APIRouter(tags=["pages"])


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, current_user: User | None = Depends(get_current_user)) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/home.html", {"current_user": current_user}
    )


@router.get("/auth/login", response_class=HTMLResponse)
async def login_page(request: Request, current_user: User | None = Depends(get_current_user)) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/login.html", {"current_user": current_user}
    )


@router.get("/auth/signup", response_class=HTMLResponse)
async def signup_page(request: Request, current_user: User | None = Depends(get_current_user)) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/signup.html", {"current_user": current_user}
    )
```

- [ ] **Step 4: 템플릿 3개 작성**

`app/templates/pages/home.html`:
```html
{% extends "base.html" %}
{% block title %}홈 · Nestory{% endblock %}
{% block content %}
<section class="space-y-4">
  <h1 class="text-3xl font-bold text-slate-900">Nestory에 오신 것을 환영합니다</h1>
  <p class="text-slate-600">
    전원주택 정착의 전 과정을 실거주자의 여정으로 아카이빙하는 커뮤니티입니다.
  </p>
  {% if current_user %}
    <p class="rounded-md bg-emerald-50 p-4 text-emerald-800">
      반갑습니다, <strong>@{{ current_user.username }}</strong>. 콘텐츠 작성 기능은 곧 열립니다.
    </p>
  {% else %}
    <p class="rounded-md bg-slate-100 p-4 text-slate-700">
      <a href="/auth/signup" class="font-semibold text-emerald-700 hover:underline">계정을 만들어</a>
      관심 지역을 팔로우하세요.
    </p>
  {% endif %}
</section>
{% endblock %}
```

`app/templates/pages/login.html`:
```html
{% extends "base.html" %}
{% block title %}로그인 · Nestory{% endblock %}
{% block content %}
<section class="mx-auto max-w-md space-y-6">
  <h1 class="text-2xl font-bold">로그인</h1>

  <a href="/auth/kakao/start"
     class="flex w-full items-center justify-center gap-2 rounded-md bg-yellow-300 px-4 py-3 font-semibold text-slate-900 hover:bg-yellow-400">
    <span>카카오로 계속하기</span>
  </a>

  <div class="relative text-center text-xs text-slate-400">
    <span class="bg-slate-50 px-2">또는 이메일로 로그인</span>
    <hr class="absolute left-0 right-0 top-1/2 -z-10 border-slate-200">
  </div>

  <form method="post" action="/auth/login" class="space-y-3">
    <label class="block">
      <span class="text-sm text-slate-700">이메일</span>
      <input name="email" type="email" required autocomplete="email"
             class="mt-1 block w-full rounded-md border-slate-300 shadow-sm focus:border-emerald-500 focus:ring-emerald-500">
    </label>
    <label class="block">
      <span class="text-sm text-slate-700">비밀번호</span>
      <input name="password" type="password" required autocomplete="current-password"
             class="mt-1 block w-full rounded-md border-slate-300 shadow-sm">
    </label>
    <button type="submit" class="w-full rounded-md bg-emerald-600 py-2 font-semibold text-white hover:bg-emerald-700">
      로그인
    </button>
  </form>

  <p class="text-center text-sm text-slate-500">
    계정이 없으신가요?
    <a href="/auth/signup" class="font-medium text-emerald-700 hover:underline">가입하기</a>
  </p>
</section>
{% endblock %}
```

`app/templates/pages/signup.html`:
```html
{% extends "base.html" %}
{% block title %}가입 · Nestory{% endblock %}
{% block content %}
<section class="mx-auto max-w-md space-y-6">
  <h1 class="text-2xl font-bold">계정 만들기</h1>
  <form method="post" action="/auth/signup" class="space-y-3">
    <label class="block">
      <span class="text-sm text-slate-700">이메일</span>
      <input name="email" type="email" required autocomplete="email"
             class="mt-1 block w-full rounded-md border-slate-300">
    </label>
    <label class="block">
      <span class="text-sm text-slate-700">아이디 (3–32자, 소문자·숫자·_)</span>
      <input name="username" pattern="[a-z0-9_]{3,32}" required
             class="mt-1 block w-full rounded-md border-slate-300">
    </label>
    <label class="block">
      <span class="text-sm text-slate-700">닉네임</span>
      <input name="display_name" required maxlength="64"
             class="mt-1 block w-full rounded-md border-slate-300">
    </label>
    <label class="block">
      <span class="text-sm text-slate-700">비밀번호 (8자 이상)</span>
      <input name="password" type="password" minlength="8" required autocomplete="new-password"
             class="mt-1 block w-full rounded-md border-slate-300">
    </label>
    <button type="submit" class="w-full rounded-md bg-emerald-600 py-2 font-semibold text-white hover:bg-emerald-700">
      가입하기
    </button>
  </form>
</section>
{% endblock %}
```

- [ ] **Step 5: `app/main.py` 라우터 등록**

```python
from app.routers import auth as auth_router
from app.routers import pages as pages_router

app.include_router(pages_router.router)
app.include_router(auth_router.router)
```

- [ ] **Step 6: 모든 테스트 통과 확인**

Run: `uv run pytest -v`
Expected: 모두 passed.

- [ ] **Step 7: 브라우저 수동 확인**

Run: `uv run uvicorn app.main:app --reload`
1. `http://localhost:8000/` → 환영 섹션 렌더 · 상단 네비에 "로그인"/"시작하기"
2. `/auth/signup` → 폼 렌더 · 가입 → 홈으로 리다이렉트 · 네비에 `@username`
3. `/auth/login` → "카카오로 계속하기" + 이메일 폼
4. `/auth/logout` POST → 로그아웃

- [ ] **Step 8: 커밋**

```bash
git add app/routers/pages.py app/templates/pages/ app/main.py
git commit -m "feat: add home/login/signup Jinja pages with Tailwind styling"
```

---

## Task 17: structlog 구조화 로깅

**Files:**
- Create: `app/logging_setup.py`
- Modify: `app/main.py`
- Test: `app/tests/unit/test_logging_setup.py`

- [ ] **Step 1: 테스트 작성**

`app/tests/unit/test_logging_setup.py`:
```python
import json
import logging

import structlog

from app.logging_setup import configure_logging


def test_configure_logging_produces_json(capfd) -> None:
    configure_logging(env="production")
    log = structlog.get_logger("test")
    log.info("hello", user_id=42)

    captured = capfd.readouterr()
    line = captured.out.strip().splitlines()[-1]
    parsed = json.loads(line)
    assert parsed["event"] == "hello"
    assert parsed["user_id"] == 42
    assert parsed["level"] == "info"


def test_configure_logging_local_is_readable(capfd) -> None:
    configure_logging(env="local")
    log = structlog.get_logger("test")
    log.info("local-event")

    captured = capfd.readouterr()
    # Console renderer: not JSON, contains "local-event"
    assert "local-event" in captured.out
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run pytest app/tests/unit/test_logging_setup.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: `app/logging_setup.py` 구현**

```python
from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(*, env: str = "local") -> None:
    level = logging.INFO

    renderer: structlog.types.Processor
    if env == "local":
        renderer = structlog.dev.ConsoleRenderer(colors=False)
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.WriteLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
    logging.basicConfig(
        level=level,
        handlers=[logging.StreamHandler(sys.stdout)],
        format="%(message)s",
    )
```

- [ ] **Step 4: `app/main.py` 에서 호출**

import 섹션 뒤, app 생성 전에:
```python
from app.logging_setup import configure_logging

configure_logging(env=settings.app_env)
```

- [ ] **Step 5: 테스트 통과 확인**

Run: `uv run pytest app/tests/unit/test_logging_setup.py -v`
Expected: 2 passed.

- [ ] **Step 6: 커밋**

```bash
git add app/logging_setup.py app/main.py app/tests/unit/test_logging_setup.py
git commit -m "feat: configure structlog with JSON (prod) and console (local) renderers"
```

---

## Task 18: Sentry 통합 (production only)

**Files:**
- Modify: `app/main.py`
- Test: `app/tests/unit/test_sentry_setup.py`

- [ ] **Step 1: Sentry init 헬퍼 만들고 테스트**

`app/logging_setup.py` 에 추가:
```python
def init_sentry(dsn: str, env: str) -> None:
    if not dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    sentry_sdk.init(
        dsn=dsn,
        environment=env,
        integrations=[StarletteIntegration(), FastApiIntegration()],
        traces_sample_rate=0.0,
        send_default_pii=False,
    )
```

`app/tests/unit/test_sentry_setup.py`:
```python
from app.logging_setup import init_sentry


def test_init_sentry_noop_when_dsn_missing(monkeypatch) -> None:
    called = {"inited": False}
    import sentry_sdk

    def fake_init(**kwargs):
        called["inited"] = True

    monkeypatch.setattr(sentry_sdk, "init", fake_init)
    init_sentry("", "local")
    assert called["inited"] is False


def test_init_sentry_calls_init_when_dsn_present(monkeypatch) -> None:
    called = {}
    import sentry_sdk

    def fake_init(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(sentry_sdk, "init", fake_init)
    init_sentry("https://key@o0.ingest.sentry.io/0", "production")
    assert called["dsn"].startswith("https://")
    assert called["environment"] == "production"
    assert called["send_default_pii"] is False
```

- [ ] **Step 2: `app/main.py` 에서 호출**

`configure_logging` 호출 뒤에:
```python
from app.logging_setup import configure_logging, init_sentry

configure_logging(env=settings.app_env)
init_sentry(settings.sentry_dsn, settings.app_env)
```

- [ ] **Step 3: 테스트 통과 확인**

Run: `uv run pytest -v`
Expected: 전체 passed.

- [ ] **Step 4: 커밋**

```bash
git add app/logging_setup.py app/main.py app/tests/unit/test_sentry_setup.py
git commit -m "feat: add conditional Sentry init for production error reporting"
```

---

## Task 19: GitHub Actions CI (lint + test)

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: 워크플로 작성**

`.github/workflows/ci.yml`:
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: nestory
          POSTGRES_PASSWORD: nestory
          POSTGRES_DB: nestory
        ports: ["5432:5432"]
        options: >-
          --health-cmd="pg_isready -U nestory"
          --health-interval=5s
          --health-timeout=5s
          --health-retries=10

    env:
      APP_ENV: test
      APP_SECRET_KEY: ci-secret-ci-secret-ci-secret-ci
      DATABASE_URL: postgresql+psycopg://nestory:nestory@localhost:5432/nestory
      ADMIN_EMAIL: admin@example.com
      SESSION_COOKIE_SECURE: "false"
      KAKAO_CLIENT_ID: test-id
      KAKAO_CLIENT_SECRET: test-secret
      KAKAO_REDIRECT_URI: http://localhost:8000/auth/kakao/callback

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "0.5.x"

      - name: Set up Python
        run: uv python install 3.12

      - name: Install dependencies
        run: uv sync --frozen

      - name: Lint (ruff)
        run: uv run ruff check .

      - name: Format check (ruff format)
        run: uv run ruff format --check .

      - name: Apply migrations
        run: uv run alembic upgrade head

      - name: Run tests
        run: uv run pytest -v
```

- [ ] **Step 2: 로컬에서 lint 재현 & 통과**

Run: `uv run ruff check .`
Run: `uv run ruff format --check .`
위반이 있으면 수정: `uv run ruff check --fix .` 및 `uv run ruff format .`
다시 `pytest -v` 수행 후 통과 확인.

- [ ] **Step 3: 커밋 & 푸시**

```bash
git add .github/workflows/ci.yml
# (ruff 수정이 있었으면 그것도 포함)
git add -u
git commit -m "ci: add GitHub Actions workflow with Postgres service, ruff, alembic, pytest"
git push origin main
```

- [ ] **Step 4: CI 그린 확인**

`gh run watch` 또는 GitHub UI에서 최신 워크플로가 ✅ 인지 확인. 실패 시 로그 보고 수정 → 재커밋.

---

## Task 20: Nginx 설정

**Files:**
- Create: `deploy/nginx.conf`

- [ ] **Step 1: 구성 파일 작성**

`deploy/nginx.conf`:
```nginx
# /etc/nginx/sites-available/nestory
# cloudflared tunnel이 127.0.0.1로 요청을 보냄.
# 따라서 Nginx는 127.0.0.1:80 에서만 수신하고,
# Uvicorn을 127.0.0.1:8000으로 프록시한다.

server {
    listen 127.0.0.1:80 default_server;
    server_name _;

    client_max_body_size 12M;  # 이미지 업로드 여유 (Phase 1에서 본격 사용)

    # 정적 파일 — FastAPI에서 서빙하되 Nginx 캐시 추천
    location /static/ {
        alias /opt/nestory/app/static/;
        expires 7d;
        add_header Cache-Control "public, max-age=604800, immutable";
        access_log off;
    }

    # (Phase 1+) 미디어 디렉토리
    # location /media/ {
    #     alias /var/nestory/media/;
    #     expires 30d;
    #     access_log off;
    # }

    location /healthz {
        proxy_pass http://127.0.0.1:8000;
        access_log off;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_redirect off;
        proxy_buffering off;
        proxy_read_timeout 60s;
    }

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml image/svg+xml;
    gzip_min_length 1024;
}
```

- [ ] **Step 2: 유효성 사전 검증 (로컬에서 nginx 실행 불가할 수 있음)**

로컬 설치된 nginx가 있다면: `nginx -t -c deploy/nginx.conf`
없다면 skip (배포 단계 Task 23에서 RPi에서 검증).

- [ ] **Step 3: 커밋**

```bash
git add deploy/nginx.conf
git commit -m "chore: add Nginx reverse proxy config for Uvicorn and static assets"
```

---

## Task 21: systemd 유닛 (앱 · 백업 타이머)

**Files:**
- Create: `deploy/systemd/nestory.service`
- Create: `deploy/systemd/nestory-backup.service`
- Create: `deploy/systemd/nestory-backup.timer`
- Create: `scripts/backup.sh`

- [ ] **Step 1: `deploy/systemd/nestory.service`**

```ini
[Unit]
Description=Nestory FastAPI application
After=network-online.target postgresql.service
Wants=network-online.target

[Service]
Type=simple
User=nestory
Group=nestory
WorkingDirectory=/opt/nestory
EnvironmentFile=/etc/nestory/nestory.env
ExecStart=/opt/nestory/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=3
StandardOutput=journal
StandardError=journal

# 하드닝
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/nestory /opt/nestory/app/db/migrations
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: `scripts/backup.sh`**

```bash
#!/usr/bin/env bash
# pg_dump 일배치 백업. systemd가 매일 03:00 실행.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/mnt/backup/pg}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
DATABASE_URL="${DATABASE_URL:?DATABASE_URL must be set}"

mkdir -p "$BACKUP_DIR"
TS="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
FILE="$BACKUP_DIR/nestory-$TS.sql.gz"

pg_dump "$DATABASE_URL" --format=plain --no-owner --no-privileges \
  | gzip -9 > "$FILE"

# 권한 제한
chmod 600 "$FILE"

# 보관 기간 초과 파일 삭제
find "$BACKUP_DIR" -maxdepth 1 -name "nestory-*.sql.gz" -mtime "+$RETENTION_DAYS" -delete

echo "Backup written: $FILE"
```

Windows에서 작성 시 LF 줄바꿈 유지 필수:
Run: `uv run python -c "p=open('scripts/backup.sh','rb').read().replace(b'\r\n', b'\n'); open('scripts/backup.sh','wb').write(p)"`

권한 비트는 RPi 배포 시 `chmod +x`로 부여.

- [ ] **Step 3: `deploy/systemd/nestory-backup.service`**

```ini
[Unit]
Description=Nestory nightly pg_dump
After=postgresql.service

[Service]
Type=oneshot
User=nestory
Group=nestory
EnvironmentFile=/etc/nestory/nestory.env
Environment=BACKUP_DIR=/mnt/backup/pg
Environment=RETENTION_DAYS=14
ExecStart=/usr/bin/env bash /opt/nestory/scripts/backup.sh
```

- [ ] **Step 4: `deploy/systemd/nestory-backup.timer`**

```ini
[Unit]
Description=Run Nestory backup nightly at 03:00
Requires=nestory-backup.service

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

- [ ] **Step 5: 커밋**

```bash
git add deploy/systemd/ scripts/backup.sh
git commit -m "chore: add systemd units for app and nightly pg_dump backup"
```

---

## Task 22: Cloudflare Tunnel 설정 예시

**Files:**
- Create: `deploy/cloudflared-config.example.yml`
- Create: `deploy/README.md`

- [ ] **Step 1: `deploy/cloudflared-config.example.yml`**

```yaml
# /etc/cloudflared/config.yml (실제 배포 시 복사 후 값 채움)
tunnel: <TUNNEL_UUID>
credentials-file: /etc/cloudflared/<TUNNEL_UUID>.json

ingress:
  - hostname: ${NESTORY_DOMAIN}
    service: http://127.0.0.1:80
    originRequest:
      noTLSVerify: false
      connectTimeout: 30s
      keepAliveConnections: 100
  - service: http_status:404
```

- [ ] **Step 2: `deploy/README.md` — 런북**

```markdown
# Nestory 배포 런북 (Raspberry Pi)

**전제**: Raspberry Pi OS Bookworm (64-bit), nestory 유닉스 유저 생성됨.

## 1. 시스템 패키지

```bash
sudo apt update
sudo apt install -y postgresql-16 nginx git build-essential libpq-dev python3-venv \
    cloudflared   # Cloudflare에서 제공하는 arm64 .deb 설치
```

## 2. 애플리케이션 사용자·디렉토리

```bash
sudo useradd --system --home /opt/nestory --shell /usr/sbin/nologin nestory
sudo mkdir -p /opt/nestory /var/nestory/media /etc/nestory /mnt/backup/pg
sudo chown -R nestory:nestory /opt/nestory /var/nestory /mnt/backup
sudo chown root:nestory /etc/nestory && sudo chmod 750 /etc/nestory
```

## 3. 코드 + 의존성

```bash
sudo -u nestory git clone https://github.com/<OWNER>/nestory /opt/nestory
cd /opt/nestory
sudo -u nestory bash -lc 'curl -LsSf https://astral.sh/uv/install.sh | sh'
sudo -u nestory /opt/nestory/.local/bin/uv sync --frozen
```

## 4. 환경 파일

```bash
sudo tee /etc/nestory/nestory.env <<EOF
APP_ENV=production
APP_SECRET_KEY=<openssl rand -hex 32>
DATABASE_URL=postgresql+psycopg://nestory:<PW>@localhost:5432/nestory
KAKAO_CLIENT_ID=<...>
KAKAO_CLIENT_SECRET=<...>
KAKAO_REDIRECT_URI=https://<DOMAIN>/auth/kakao/callback
ADMIN_EMAIL=<your@email>
SENTRY_DSN=<optional>
NESTORY_DOMAIN=<DOMAIN>
SESSION_COOKIE_SECURE=true
EOF
sudo chmod 640 /etc/nestory/nestory.env
sudo chown root:nestory /etc/nestory/nestory.env
```

## 5. Postgres 초기화

```bash
sudo -u postgres createuser nestory -P
sudo -u postgres createdb nestory -O nestory
cd /opt/nestory && sudo -u nestory bash -lc 'source /etc/nestory/nestory.env && uv run alembic upgrade head'
```

## 6. 초기 시드 · 관리자 승격

```bash
sudo -u nestory bash -lc 'set -a; . /etc/nestory/nestory.env; set +a; uv run python -m scripts.seed_regions'
# 먼저 웹에서 /auth/signup으로 본인 계정 가입한 뒤:
sudo -u nestory bash -lc 'set -a; . /etc/nestory/nestory.env; set +a; uv run python -m scripts.bootstrap_admin'
```

## 7. Nginx

```bash
sudo cp /opt/nestory/deploy/nginx.conf /etc/nginx/sites-available/nestory
sudo ln -sf /etc/nginx/sites-available/nestory /etc/nginx/sites-enabled/nestory
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

## 8. systemd

```bash
sudo cp /opt/nestory/deploy/systemd/*.service /opt/nestory/deploy/systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nestory.service
sudo systemctl enable --now nestory-backup.timer
sudo systemctl status nestory
```

## 9. Cloudflare Tunnel

```bash
# 1) cloudflared 로그인 + 터널 생성
sudo cloudflared tunnel login
sudo cloudflared tunnel create nestory
# 2) DNS 레코드 연결
sudo cloudflared tunnel route dns nestory <DOMAIN>
# 3) 설정 파일 배치
sudo cp /opt/nestory/deploy/cloudflared-config.example.yml /etc/cloudflared/config.yml
sudo sed -i "s/\${NESTORY_DOMAIN}/<DOMAIN>/" /etc/cloudflared/config.yml
sudo sed -i "s/<TUNNEL_UUID>/$(sudo cloudflared tunnel list | awk '/nestory/{print $1}')/" /etc/cloudflared/config.yml
# 4) systemd 서비스로 등록
sudo cloudflared service install
sudo systemctl enable --now cloudflared
```

## 10. 스모크 테스트

```bash
curl -fsSL https://<DOMAIN>/healthz
# Expected: {"status":"ok","env":"production"}
```

브라우저에서:
- `/` 렌더
- `/auth/signup` → 계정 생성 → 리다이렉트 홈
- `/auth/kakao/start` → Kakao 로그인 → 콜백 → 홈

## 11. 백업 수동 검증

```bash
sudo systemctl start nestory-backup.service
ls -lh /mnt/backup/pg/
```

## 12. 롤백

```bash
cd /opt/nestory
sudo -u nestory git fetch origin
sudo -u nestory git checkout <PREV_TAG_OR_SHA>
sudo -u nestory bash -lc 'uv sync --frozen && set -a; . /etc/nestory/nestory.env; set +a; uv run alembic upgrade head'
sudo systemctl restart nestory
```
```

- [ ] **Step 3: 커밋**

```bash
git add deploy/cloudflared-config.example.yml deploy/README.md
git commit -m "docs: add Cloudflare Tunnel example config and Raspberry Pi deploy runbook"
```

---

## Task 23: RPi 실제 배포 & 스모크 테스트

> **참고**: 이 태스크는 **코드 변경 없음**. 런북 실행 + 발견된 문제를 이슈·수정 PR로 기록.

- [ ] **Step 1: RPi에 SSH 접속 및 런북 따라가기**

`deploy/README.md`를 순서대로 실행.
각 섹션 실행 후 `echo "OK: step N"` 형태로 터미널 확인.

- [ ] **Step 2: 스모크 테스트 체크리스트**

- [ ] `curl https://<DOMAIN>/healthz` → 200 + JSON
- [ ] 브라우저 `/` 렌더 + Tailwind 스타일 적용
- [ ] 이메일 회원가입 + 로그인 가능
- [ ] 카카오 OAuth 플로우 정상 (Kakao 콘솔에 redirect URI 등록 필수)
- [ ] `/auth/logout` 후 세션 제거
- [ ] `sudo systemctl status nestory` active (running)
- [ ] `sudo systemctl list-timers | grep nestory` 정상
- [ ] `/mnt/backup/pg/`에 백업 파일 생성 (수동 trigger 후)

- [ ] **Step 3: 발견된 차이점을 PR로 반영**

런북과 실제 명령이 다르면 `deploy/README.md` 갱신:
```bash
git add deploy/README.md
git commit -m "docs: fix deploy runbook after real RPi walkthrough"
git push
```

- [ ] **Step 4: 첫 배포 태그**

```bash
git tag -a phase0-deployed -m "Phase 0 Foundation deployed to Raspberry Pi"
git push origin phase0-deployed
```

---

## Task 24: UptimeRobot 모니터 + 운영 문서

**Files:**
- Modify: `deploy/README.md`

- [ ] **Step 1: UptimeRobot 계정에서 HTTP(s) 모니터 등록**

- URL: `https://<DOMAIN>/healthz`
- Monitoring Interval: 5분
- Keyword Monitoring: `"status":"ok"` 포함
- Alert Contacts: 본인 이메일

- [ ] **Step 2: 모니터링 시작 후 30분 관찰**

로그:
```bash
sudo journalctl -u nestory -n 50 -f
```
UptimeRobot 대시보드에서 Uptime 100% 확인.

- [ ] **Step 3: 운영 런북 섹션 추가**

`deploy/README.md` 끝에 추가:
```markdown
## 모니터링

- **업타임**: UptimeRobot `https://<DOMAIN>/healthz`, 5분 간격, 이메일 알림
- **에러 트래킹**: Sentry (SENTRY_DSN 설정 시)
- **로그**: `sudo journalctl -u nestory -f` 및 `-u cloudflared -f`
- **DB 상태**: `sudo -u nestory psql $DATABASE_URL -c "\l+"`

## 복구 시나리오

### RPi 전원 장애 후

```bash
sudo systemctl status nestory postgresql nginx cloudflared
# 필요 시 재기동: sudo systemctl restart nestory
```

### DB 복원

```bash
gunzip -c /mnt/backup/pg/nestory-<TS>.sql.gz | sudo -u postgres psql nestory_restore
# 검증 후 실제 DB 교체는 수동.
```
```

- [ ] **Step 4: 커밋**

```bash
git add deploy/README.md
git commit -m "docs: add UptimeRobot setup and recovery scenarios"
git push
```

---

## Task 25: Phase 0 종료 자체 검증 + 리트로

**Files:**
- Create: `_docs/phase0_retro.md`

- [ ] **Step 1: 완료 기준 체크리스트 실행**

다음을 모두 확인:
- [ ] 로컬 `uv run uvicorn app.main:app` 기동 OK
- [ ] `/healthz` JSON 응답
- [ ] 홈 페이지 Jinja2 렌더 (Tailwind 스타일 적용)
- [ ] 이메일/비밀번호 회원가입·로그인·로그아웃 동작
- [ ] 카카오 OAuth 플로우 동작 (staging 또는 prod URI 기준)
- [ ] `seed_regions` 실행 → DB에 5개 시군
- [ ] `bootstrap_admin` 실행 → ADMIN_EMAIL 계정이 `role='admin'`
- [ ] `alembic upgrade head` 재현 가능
- [ ] `uv run pytest` 전부 통과
- [ ] `uv run ruff check .` + `ruff format --check .` 통과
- [ ] CI 워크플로 그린
- [ ] RPi에 배포되어 도메인 접속 가능
- [ ] systemd 백업 타이머로 `/mnt/backup/pg/`에 파일 생성 확인
- [ ] UptimeRobot 24시간 100% Uptime

- [ ] **Step 2: OI 재확인**

- [ ] OI-1: 파일럿 5개 시군 — seed 목록과 실제 결정 일치하는가? 불일치 시 `scripts/seed_regions.py` 수정 + 재시드.
- [ ] OI-4: CSS 프레임워크 — Tailwind CDN으로 충분한가? 빌드 전환 필요성 평가 (Phase 1 초까지 미룰 수 있음).
- [ ] OI-5: 첫 관리자 — bootstrap_admin이 지정된 이메일을 승격했는가?
- [ ] OI-7: 예산 — Phase 1 시작 전 필요한 지출 목록 정리 (도메인 · Sentry 유료 · Kakao 비즈니스).
- [ ] OI-9: 브랜드 — 로고·컬러 팔레트 Phase 1 시작 전 확정 필요.
- [ ] OI-10: 도메인 — `NESTORY_DOMAIN` 확정. DNS·Cloudflare Tunnel에 반영됨.

- [ ] **Step 3: 리트로 문서 작성**

`_docs/phase0_retro.md`:
```markdown
# Phase 0 리트로 (YYYY-MM-DD)

## 소요 시간
- 계획: 3주
- 실제: <N>주

## 완료된 산출물
- [목록]

## 미완료·이월 항목
- [Phase 1로 넘긴 것]

## 잘된 점
- 

## 개선점
- 

## Phase 1 시작 전 확정 필요
- OI-3 (증빙 유형)
- OI-9 (브랜드)
- OI-10 (도메인) — 확정되었으면 "완료"로 표기
- Post metadata 템플릿 필드 사전 설계 (OI-11)
```

- [ ] **Step 4: 최종 커밋**

```bash
git add _docs/phase0_retro.md
git commit -m "docs: add Phase 0 retro skeleton for end-of-phase review"
git push
git tag -a phase0-complete -m "Phase 0 Foundation completed"
git push origin phase0-complete
```

---

## Phase 0 성공 기준 요약

Phase 0이 "완료"되려면 다음이 모두 참이어야 한다:

1. **로컬**: 새 개발자가 `README.md`를 따라 `uv sync` → `docker compose up` → `alembic upgrade head` → `uv run uvicorn` 만으로 기동 가능.
2. **기능**: 이메일·카카오 두 방식으로 로그인 가능하고, 로그인 상태가 홈에서 `@username`으로 표시됨.
3. **데이터**: `regions` 테이블에 파일럿 5개, `users` 테이블에 관리자 1명이 존재.
4. **프로덕션**: `https://<DOMAIN>/healthz` → 200, `/` → Nestory 랜딩 렌더.
5. **운영**: 일일 `pg_dump` 자동 실행되어 `/mnt/backup/pg/`에 파일 쌓임. UptimeRobot 알림 수신 검증.
6. **자동화**: CI 그린 (ruff + alembic + pytest).
7. **문서**: `deploy/README.md` 런북만으로 다른 사람이 배포 재현 가능.

이후 Phase 1 계획 작성을 시작한다 (별도 문서 `docs/superpowers/plans/YYYY-MM-DD-nestory-phase1.md`).
