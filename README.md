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

# 3. 로컬 Postgres 기동 (host 포트 5433, 컨테이너 내부는 5432)
docker compose -f docker-compose.local.yml up -d

# 4. (Alembic 추가 후) 마이그레이션 적용
uv run alembic upgrade head

# 5. 개발 서버 기동
uv run uvicorn app.main:app --reload
```

서버가 `http://localhost:8000`에서 실행됩니다.

> **Note**: host 포트 5433은 Windows 네이티브 PostgreSQL(5432)과의 충돌을 피하기 위한 선택입니다.
> 네이티브 Postgres가 없다면 `docker-compose.local.yml`의 `"5433:5432"`를 `"5432:5432"`로 바꾸고 `.env`의 URL 포트도 5432로 맞추면 됩니다.
