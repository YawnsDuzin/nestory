# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**Nestory** — 은퇴자·전원주택 예비 입주자를 위한 커뮤니티 웹앱. Python 3.12 + FastAPI + Jinja2 SSR + HTMX + PostgreSQL 16. uv 패키지 매니저, PowerShell 환경 (Windows 11). **로컬 PostgreSQL 16 native 설치 필요** — Docker / docker compose 사용하지 않음 (2026-05-16 결정).

PRD는 `docs/superpowers/specs/2026-04-17-nestory-design.md` (v1.1.1, OI-14 PostHog 확정). 변경 시 반드시 인라인 `[v1.1]` / `[v1.1.1]` 라벨로 추적. 차별화 4축(T·C·R·V — Time-lag·Regret Cost·Region Match·Peer Validation)이 PRD §1.5에 정의되어 있고 모든 데이터 모델·UX 결정은 이 축을 강화해야 함.

진행 중 phase: Phase 1.1·1.2 완료 (데이터 모델 + 작업 큐 인프라 + 배지·권한 가드 + factory-boy 테스트 인프라). 다음 sub-plan은 `docs/superpowers/plans/` 에 작성. 사용자 화면 라우트는 P1.3부터 본격 추가 — 현재 구현된 페이지는 home·login·signup·me/badge·admin/badge-queue 등.

## Commands

모든 명령은 프로젝트 루트에서 실행. PowerShell. **전제: native PostgreSQL 16이 `localhost:5432`에서 기동 중** (`nestory` DB·user·password, 그리고 pytest용 `nestory_test` DB). Docker / docker compose는 이 프로젝트에서 사용하지 않음.

```powershell
# 의존성 설치 / 갱신
uv sync

# 마이그레이션
uv run alembic upgrade head            # 적용
uv run alembic current                 # 현재 head
uv run alembic history --verbose       # 체인 확인 (linear여야 함)
uv run alembic revision --autogenerate -m "<설명>"

# 개발 서버 (uvicorn — --reload 자동 갱신)
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 워커 (PG 기반 작업 큐 — 별도 터미널)
uv run python -m app.workers.runner

# 데모 데이터 시드 (alembic upgrade head 선행 필요)
uv run python -m scripts.seed_regions                  # 지역 마스터 (양평군 slug=yangpyeong 포함)
uv run python -m scripts.seed_yangpyeong_demo          # 양평군 허브 4탭(후기·Journey·질문·이웃) + 샘플 이미지 + 5 데모 계정. idempotent

# 테스트 — native Postgres 가 기동돼 있어야 함 (TEST_DATABASE_URL 별도 DB)
uv run pytest app/tests/ -q
uv run pytest app/tests/integration/test_post_model.py -v   # 단일 파일
uv run pytest app/tests/integration/test_post_model.py::test_create_review_post_with_metadata -v  # 단일 테스트

# Lint (마이그레이션 디렉토리 포함 전체 — 새 파일만 검사하지 말 것)
uv run ruff check app/
uv run ruff check --fix app/db/migrations/versions/   # autogenerate 후 UP007 자동 변환

# DB 직접 접근 (native psql)
psql -h localhost -p 5432 -U nestory -d nestory -c "\dt"
```

DB 접속 정보 (DBeaver 등): host `localhost`, port **`5432`** (native), db/user/password 모두 `nestory`. pytest 전용 DB는 같은 인스턴스의 `nestory_test`.

**데모 계정** (시드 후 사용, 모두 비밀번호 `demo1234`):

| Email | 페르소나 | Badge |
|---|---|---|
| `alice.yp@example.com` | 5년차 거주자 | RESIDENT |
| `bob.yp@example.com` | 직접 건축 | RESIDENT |
| `carol.yp@example.com` | 1년차 | RESIDENT |
| `evan.yp@example.com` | 원격근무 | RESIDENT |
| `dave.yp@example.com` | 예비 입주자 | REGION_VERIFIED (질문 작성 권한 테스트용) |

## 운영 갱신 (Linux 서버)

`deploy/systemd/` 의 service 유닛으로 nestory-app·nestory-worker 분리 기동. 코드 갱신:

```bash
cd /home/dzp/dzp-main/program/nestory
git pull
uv sync                                              # 의존성 변경 시
uv run alembic upgrade head                          # 새 마이그레이션 적용
sudo systemctl restart nestory-app nestory-worker
```

## Architecture

### 작업 흐름의 빅 픽처

1. **PRD가 모든 결정의 근거** — `[v1.1]` / `[v1.1.1]` 라벨로 변경 추적. 모든 새 기능은 PRD 섹션 어딘가와 일대일 매핑되어야 함.
2. **Sub-plan 단위 진행** — Phase 1은 P1.1(데이터+큐), P1.2(배지·가드), P1.3(콘텐츠·이미지), P1.4(허브·검색), P1.5(알림·관리자·PWA)로 분할. 각 sub-plan은 `docs/superpowers/plans/YYYY-MM-DD-...md`에 task 단위로 작성한 뒤 subagent-driven-development 스킬로 실행.
3. **데이터 모델은 단일 진실 원천** — `app/models/_enums.py`에 도메인 enum 모음. 모든 모델이 import. 새 enum은 여기에만 추가.

### 모델·마이그레이션 패턴 (반드시 준수)

Phase 0의 `app/models/user.py` 패턴을 그대로 복제 — 새 idiom 도입 금지:

- `Mapped[T]` + `mapped_column(...)` SQLAlchemy 2.x 스타일
- Enum: `Enum(E, name="<snake>", values_callable=lambda x: [e.value for e in x])` + `server_default=E.X.value`
- 타임스탬프: `server_default=func.now()`, `onupdate=func.now()` (updated_at에)
- Soft delete: `deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)` — User·Post·Journey·Comment에 적용
- 모든 신규 모델은 `app/models/__init__.py`에서 alphabetical re-export. **Table 객체** (post_tags, post_likes 등 M:N 정션)는 별도 모듈에서 정의 후 `__init__`에서 `# noqa: F401`로 import만 (metadata 등록용 — `__all__`에는 포함 X). **이 import를 빠뜨리면 `Base.metadata.tables`에 등록 안 됨 → conftest TRUNCATE가 누락하고 alembic autogenerate가 빈 마이그레이션 생성** (Phase 1.1 Task 12에서 발생, commit `1ef8fbe`로 fix).
- Alembic autogenerate 후 **즉시 검증**: ① `def upgrade()` 본문이 `pass`만 있지 않은지, ② `import sqlalchemy as sa` 있는지, ③ downgrade에 enum 생성 시 `op.execute("DROP TYPE <enum>")` 포함했는지. Autogenerate가 enum DROP을 종종 빠뜨림 — 수동 추가.
- 마이그레이션 파일은 `uv run ruff check --fix app/db/migrations/versions/`로 UP007 (Union → `X | Y`) 자동 정리. `pyproject.toml`의 per-file-ignores가 마이그레이션 디렉토리에 일부 룰만 무시.

### Forward FK gotcha (Phase 1.1에서 발견)

같은 plan 내 task 분할로 일시적 forward FK가 생길 때(예: Task 4 `images.post_id` → Task 6에서 추가될 `posts`):

- 모델·마이그레이션 **양쪽 모두에서 FK 보류** (모델은 plain `Integer`, 마이그레이션은 `ForeignKeyConstraint` 라인 제거)
- 참조 대상 task에서 모델 FK 복원 + alembic autogenerate가 schema diff로 `op.create_foreign_key` 자동 생성

이유: SQLAlchemy 2.0의 `Base.metadata.sorted_tables`가 `ForeignKey("future_table.id")`를 즉시 resolve 시도 → `NoReferencedTableError`. 자세한 패턴은 `~/.claude/projects/d---dzp-VIBE-CODING-nestory/memory/reference_sqlalchemy_forward_fk.md`. 같은 이유로 **conftest의 동적 TRUNCATE는 `Base.metadata.tables.values()`를 사용** (sorted_tables 아님 — 순환 FK 시 일부 테이블을 결과에서 누락시킴).

### Pydantic Discriminated Union for `Post.metadata`

`Post.metadata` JSONB는 자유 입력이 아님. `app/schemas/post_metadata.py`의 5개 type별 모델 (`ReviewMetadata`, `JourneyEpisodeMetadata`, `QuestionMetadata`, `AnswerMetadata`, `PlanMetadata`) + `_Forbid` 베이스(`extra="forbid"`)로 검증. discriminator 필드는 `type_tag`(외부 alias `__post_type__`). 모든 쓰기 경로(P1.3+)는 `PostMetadata` 통과 후에만 DB 저장 — 클라이언트의 임의 필드 주입 차단 + Pillar C(Regret Cost) 통계 정합성 보장.

### 백그라운드 작업 큐 (PG 기반)

- `app/models/job.py` (jobs 테이블, JSONB payload, status enum)
- `app/workers/queue.py` — `enqueue` (NOTIFY 발송), `dequeue` (`SELECT ... FOR UPDATE SKIP LOCKED`), `mark_succeeded`/`mark_failed` (지수 백오프 `60 * 2^(attempts-1)` + max_attempts 초과 시 DEAD)
- `app/workers/handlers/` — `register(JobKind.X)` 데코레이터 + `dispatch`. Phase 1.1엔 `image_resize`·`notification` stub만. 실제 로직은 P1.3 (이미지 파이프라인) / P1.5 (알림톡·이메일)
- `app/workers/runner.py` — 메인 루프, `LISTEN/NOTIFY` 즉시 깨우기 + 1초 폴링 fallback, SIGTERM/SIGINT graceful shutdown
- 운영: systemd `deploy/systemd/nestory-worker.service` (uvicorn과 별개 프로세스); 테스트는 `app/tests/integration/test_worker_e2e.py`가 `process_one()`을 직접 호출하여 결정적 검증

### 권한 가드 (P1.2 도입 예정 — PRD §6.2 명시)

라우트 인증·인가는 FastAPI Depends 표준 가드로만 강제. 다른 인증 코드 작성 금지:

- `require_login()` — 🔒
- `require_badge(level: BadgeLevel)` — 🏡 등 (Depends 팩토리)
- `require_admin()` — 🛡
- `require_resident_in_region(region_id)` — Pillar V cross-validation 투표 권한

### 분석 트래킹 (OI-14 PostHog Cloud free, 미구현 — P1.5)

PostHog Cloud free 익명 모드. SHA-256 해시 distinct_id. 이벤트는 `app/services/analytics.py`의 `EventName` enum으로 강제 (자유 문자열 금지). 35개 이벤트 카탈로그는 PRD §14.5 참조. PII 절대 미포함 — 코드 리뷰 체크 항목.

### 테스트 데이터 (factory-boy)

`app/tests/factories/`에 14 도메인 모델별 factory + 4 M:N junction Table 헬퍼. **모든 통합·단위 테스트는 factory 우선**. 직접 `Model(...)` 생성자 호출은 다음 3 경우에만 허용:

1. **IntegrityError 검증** — `sqlalchemy_get_or_create` 또는 SubFactory 캐싱이 duplicate를 가려서 UNIQUE 위반을 잡을 수 없을 때 (예: `test_tag_model.py`, `test_interest_region_model.py`)
2. **모델 default 검증** — factory default가 model default와 의도적으로 다른 경우 모델 default 자체를 검증 (예: `test_image_model.py::test_image_status_defaults_to_processing` — `ImageFactory.status=READY`인데 model default는 `PROCESSING`)
3. **생성 service/queue API 자체가 SUT** — `create_user_with_password`·`queue.enqueue` 같은 row 생성 service 자체를 테스트 (예: `test_auth_service_db.py`, `test_job_queue.py`)

위 3 경우 외 직접 생성자 사용 시 **코드 리뷰 차단**.

**핵심 패턴 (반드시 준수 — 신규 factory 추가 시 기존 파일 복제)**:

- `class XFactory(BaseFactory)` + `Meta.model = X` + `Meta.exclude = ("relation",)` (관계 객체는 ORM 인스턴스로 받고 `_id` 컬럼만 모델에 전달)
- `relation = SubFactory(XFactory)` + `relation_id = SelfAttribute("relation.id")` 트리오 (모든 FK)
- 자연키 재사용은 `Meta.sqlalchemy_get_or_create=("slug",)` (Region·Tag만)
- PostFactory는 `@factory.lazy_attribute`로 `_default_metadata(self.type)` 반환 — JSONB 항상 `PostMetadata` Pydantic 검증 통과 보장 (P1.3+ 신규 type 추가 시 `app/tests/factories/post.py:_default_metadata`에 분기 추가 필수)
- 사용자 변형: `UserFactory` / `AdminUserFactory` / `RegionVerifiedUserFactory` / `ResidentUserFactory` — 권한 가드 테스트 시 그대로 사용 (직접 `User(role=ADMIN, ...)` 금지)

**M:N junction (Table 객체)**: ORM이 아니라 `app/tests/factories/interaction.py`의 helper 함수 (`add_post_like(db, user, post)` 등 4개) 사용. 신규 junction 추가 시 helper도 추가.

**신규 factory 추가 워크플로**:
1. `app/tests/factories/<snake_name>.py` 작성 (기존 패턴 복제)
2. `app/tests/factories/__init__.py` alphabetical re-export
3. `app/tests/unit/test_factories.py`에 sanity test 1개 추가 (row 생성 + 핵심 invariant 1-2개 assertion)
4. conftest 수정 불필요 (`_bind_factories`가 `BaseFactory.__subclasses__()` 동적 탐색)

**`persistence="flush"` 선택 이유**: factory가 commit하지 않음 → 기존 `_cleanup_db` autouse TRUNCATE CASCADE 패턴과 양립. session은 `db` fixture가 `_bind_factories`로 런타임 주입.

**자세한 설계 결정**: `docs/superpowers/specs/2026-05-07-nestory-test-factories-design.md`.

## 네이티브 확장 대비 (Backend reusability)

향후 Capacitor 하이브리드 또는 풀 네이티브(RN/Flutter) 전환 가능성을 염두에 두고 **백엔드 코드는 처음부터 양쪽에서 재사용 가능하게** 설계한다. 현재 SSR + HTMX는 그대로 진행하되, P1.2 이후 모든 신규 코드는 다음 4원칙을 준수.

1. **services 레이어 엄격 분리** — 라우트 함수는 ① 입력 검증 ② service 호출 ③ 응답 포맷팅(템플릿 렌더 또는 redirect)만. ORM 직접 쿼리·도메인 규칙·권한 분기는 모두 `app/services/<domain>.py`에. P1.1의 `app/workers/queue.py`가 기준.
2. **services는 `User` 객체를 인자로 받음** — `request.session` / `Cookie` / `Request`를 service 내부에서 직접 읽지 말 것. 라우트가 `Depends(require_user)`로 받은 User를 service에 그대로 전달. 네이티브 토큰 인증 도입 시 service 코드 수정 불필요.
3. **응답 표시 필드 셋 = Pydantic Read 스키마와 동일** — 템플릿이 ORM 객체를 받더라도, 실제 표시되는 필드는 `app/schemas/<domain>.py`의 `XxxRead`와 일치해야 함. 추후 같은 service 호출에 대해 JSON API 라우트가 `response_model=XxxRead`에 그대로 꽂힘.
4. **권한 판단은 service/guard, 템플릿은 표시만** — "이 사용자가 X 할 수 있나?"를 템플릿 `{% if user.role == ... %}`에서만 분기하지 말 것. service 또는 가드가 `HTTPException`을 던지고 템플릿은 결과만 렌더.

### 인증 가드 dual 시그니처 (P1.2 도입 시 1줄)

`app/deps.py:get_current_user`는 처음부터 Bearer 토큰 파라미터를 시그니처에만 선언 (P1.2엔 사용 안 함, P2 시점 분기 로직 추가):

```python
async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    authorization: str | None = Header(None),  # P2 Bearer용 — 현재는 미사용
) -> User | None:
    user_id = request.session.get("user_id")
    # P2: authorization 분기 추가 예정
    ...
```

이 1줄을 미리 잡아두면 추후 모든 가드를 다시 손질하는 비용을 막는다. **추가 비용 0 / 미적용 시 P2에서 모든 가드 재작성**.

### 안티패턴 (코드 리뷰 차단 사유)

- 라우트 함수에서 ORM 직접 쿼리 (`db.query(Post).filter(...).all()`)
- service 내부에서 `request.session` / `Cookie` / `Request` 접근
- 권한 분기를 템플릿 `{% if %}`에서만 처리 (service에 동일 가드 없음)
- 에러를 HTML flash 메시지로만 처리 (도메인 예외 클래스 미정의)
- 이미지 업로드 라우트가 `path` 문자열만 반환 (ID·URL 없음 → JSON API 추가 시 응답 재설계 필요)

### 두 경로 모두 백엔드 재사용 ≥ 90%

- **Capacitor 하이브리드** (WebView가 SSR HTML 그대로 렌더): 라우트·템플릿 100% 재사용. 추가는 `device_tokens` 테이블 + `JobKind.PUSH_SEND` 핸들러 + `POST /api/devices` 라우트 3개뿐.
- **풀 네이티브 (RN/Flutter)**: services·models·workers·schemas 100% 재사용. `app/api/v1/` 별도 prefix로 JSON 라우트만 추가 — 같은 service 호출.

전체 비교 분석은 `_docs/prompts/20260507_prompt.md` 참조.

## Working conventions

- **일관성 절대 우선** — Phase 0의 user.py 패턴, 파일 구조, 커밋 prefix(`feat(models):` / `feat(workers):` / `feat(deploy):` / `docs(prd):` / `fix:` / `style:` / `test:`)를 모든 신규 작업에서 그대로 유지. 새 패턴 도입은 정당한 이유 + 메모리 ref 동반.
- **단계적 변경** — testfile 다수 일괄 변경 시 회귀 진단이 어려워짐. 1-2개씩 변경 + 사이마다 풀 pytest 검증.
- **destructive 작업 명시 confirm** — `git reset --hard`, `git push --force`, `git branch -D`, `DROP SCHEMA` 등은 user 명시 요청에만. 단 본인이 만든 미커밋 변경 revert는 진행 가능.
- **테스트 격리** — `conftest.py`의 `_cleanup_db` autouse fixture가 each-test 전후로 모든 도메인 테이블 TRUNCATE CASCADE. 신규 모델 추가 시 conftest 수정 불필요 (메타데이터 기반 동적).
- **테스트 데이터** — factory-boy 우선. 직접 `Model(...)` 생성자 사용은 IntegrityError·모델 default·생성 SUT 3경우만 (자세히는 `## Architecture > 테스트 데이터 (factory-boy)` 참조).
- **메모리 시스템** — `~/.claude/projects/d---dzp-VIBE-CODING-nestory/memory/`에 user/feedback/project/reference 메모리. 세션 시작 시 `MEMORY.md` 자동 로드. 재개 시 `project_nestory_handoff.md`를 먼저 확인 — 다음 작업 진입점·잔여 OI·기술 부채가 기록됨.

## Branch state (참고 — git log로 항상 검증)

기본 작업 브랜치는 `dev` (origin/dev push됨). PR #2로 P1.2까지 main 머지됨. dev는 그 위에 factory-boy 13 commit + 사용자 미커밋 변경 누적. 일반적으로 dev에서 작업 후 P1 전체 완료 시점에 dev → main 일괄 머지 검토.

## Open Items (PRD §15 — 결정 필요한 항목)

- **OI-12** (Phase 1 말): 카카오 알림톡 도입 — 비즈채널 등록·심사·발신 비용. Pillar T 응답률 직결.
- **OI-13** (Phase 1 말): 한국어 검색 — Phase 2에 mecab-ko 도입 여부. 현재는 `pg_trgm` + `simple` FTS.
- OI-1·3·4·9·10·11: PRD 참조. P1.2 진입 전 일부 결정 필요.

OI-14 (Analytics) ✅ PostHog Cloud free / OI-15 PWA 정도 (manifest+오프라인) 잠정 결정됨.
