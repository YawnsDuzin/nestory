# Nestory

은퇴자와 전원주택 예비 입주자를 위한 커뮤니티 웹앱.

## 개발 환경 셋업

### 요구사항

- Python 3.12
- uv (https://docs.astral.sh/uv/)
- PostgreSQL 16 (native — `localhost:5432`에 기동, Docker / docker compose 사용하지 않음)

### Postgres 준비 (최초 1회)

`localhost:5432`의 native Postgres에 `nestory` user(password `nestory`)와 두 개의 DB(`nestory` 개발용, `nestory_test` pytest 전용)를 만든다.

```sql
-- psql로 superuser 접속 후
CREATE USER nestory WITH PASSWORD 'nestory';
CREATE DATABASE nestory OWNER nestory;
CREATE DATABASE nestory_test OWNER nestory;
```

### 시작

```bash
# 1. 의존성 설치
uv sync

# 2. 환경 변수 설정
cp .env.example .env
# APP_SECRET_KEY 생성: python -c "import secrets; print(secrets.token_hex(32))"

# 3. 마이그레이션 적용
uv run alembic upgrade head

# 4. 개발 서버 기동
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. (별도 터미널) 워커 기동 — PG 기반 작업 큐
uv run python -m app.workers.runner
```

서버가 `http://localhost:8000`에서 실행됩니다.

### 테스트 실행

native Postgres 가 기동돼 있어야 합니다. `TEST_DATABASE_URL` 이 `DATABASE_URL` 과 다른 DB(예: `nestory_test`)를 가리키는지 확인.

```bash
uv run pytest app/tests/ -q
```
