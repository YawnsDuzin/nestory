# Phase 0 리트로 (2026-04-20)

## 소요 시간

- 계획: 3주
- 실제: 하루 (Subagent-Driven Development로 집중 실행)

## 완료된 산출물

- [x] Task 1 — 프로젝트 스캐폴딩 (uv · pyproject · 디렉토리)
- [x] Task 2 — Config 모듈 (pydantic-settings)
- [x] Task 3 — 로컬 PostgreSQL (Docker Compose, 포트 5433 이탈)
- [x] Task 4 — 테스트 인프라 (pytest · TestClient)
- [x] Task 5 — SQLAlchemy Base + 세션 + Alembic 초기화
- [x] Task 6 — User 모델 + 마이그레이션 (`values_callable` 필수)
- [x] Task 7 — Region 모델 + 테스트 격리 강화 (TRUNCATE autouse)
- [x] Task 8 — 시군 seed 스크립트
- [x] Task 9 — 비밀번호 해싱 서비스 (argon2id)
- [x] Task 10 — 세션 미들웨어 + 사용자 저수준 서비스
- [x] Task 11 — 회원가입 · 로그인 · 로그아웃 라우터
- [x] Task 12 — Kakao OAuth 서비스
- [x] Task 13 — Kakao OAuth 콜백 라우터 + upsert
- [x] Task 14 — Admin 부트스트랩 스크립트
- [x] Task 15 — Base Jinja2 레이아웃 + HTMX/Alpine CDN
- [x] Task 16 — 홈 · 로그인 · 회원가입 페이지
- [x] Task 17 — structlog 구조화 로깅
- [x] Task 18 — Sentry 조건부 통합
- [x] Task 19 — GitHub Actions CI (Postgres service + ruff + alembic + pytest)
- [x] Task 20 — Nginx 설정 (RPi 프로덕션용)
- [x] Task 21 — systemd 유닛 + pg_dump 백업 스크립트
- [x] Task 22 — Cloudflare Tunnel 예시 + RPi 12-단계 런북
- [x] Task 23 — **테스트 환경 배포로 대체**: `docker-compose.test.yml` (app + nginx + postgres) · 스모크 테스트 통과 · 실제 RPi 배포는 향후
- [ ] Task 24 — 모니터링 문서 추가 완료. UptimeRobot 모니터 등록은 이월 (계정 필요)
- [x] Task 25 — 이 리트로 작성

추가 커밋:
- [x] Ruff 일괄 클린업 (CI lint 게이트 준비)
- [x] 전체 스택 테스트 환경 (`docker-compose.test.yml` + `Dockerfile` + `deploy/entrypoint.sh` + `deploy/nginx.test.conf`)
- [x] 테스트 환경 세부 개선 (compose 프로젝트 이름 격리 + venv 바이너리 직접 실행)

## 미완료·이월 항목

- **Task 23 실제 RPi 배포** — 하드웨어 준비 후 `deploy/README.md` 12단계 순서대로 실행
- **Task 24 UptimeRobot 모니터 등록** — 계정 생성 + `https://<DOMAIN>/healthz` 모니터 등록
- **main 브랜치 병합 + 푸시** — 현재 `phase0-foundation` 브랜치에 커밋만 쌓임

## 잘된 점

- Subagent-Driven Development 적용으로 태스크당 spec + quality 두 단계 리뷰가 일관적으로 돌아감. 리뷰어가 찾은 이슈는 다음 태스크 전에 처리되어 누적 부채 없음.
- 모든 DB 관련 테스트가 실제 Postgres 인스턴스(도커) 대상으로 실행되어 모킹이 숨길 수 있는 버그 회피. 카카오 OAuth만 제3자 API라 `httpx.MockTransport`로 격리.
- 테스트 환경이 프로덕션 스택(Nginx + app + Postgres)을 거의 그대로 재현 — RPi 배포 전에 수정 필요한 실수를 미리 잡을 확률 높음.
- 계획 파일이 구현 중 발견된 이탈(포트 5433, `values_callable` 패턴, uv 버전 핀)을 반영해 살아 있는 문서로 유지됨.

## 개선점

- Windows 환경에서 Docker Desktop 중지가 세션 중 2회 발생 → 자동 회복 또는 사전 체크 필요. `.gitattributes`로 LF 강제도 중반에야 추가됨.
- 태스크 1 시점에 `uv`가 시스템에 없어 설치부터 필요했음. 프로젝트 요구사항에 "uv 설치 여부" 확인 단계를 README에 앞세우면 좋음.
- 플랜 상 Enum `values_callable` 누락 · ruff 룰 누적 이슈(E402, B008, UP042)는 모두 사후에 고침. 플랜 작성 시 린트 프리셋을 먼저 돌려보고 알려진 false-positive을 ignore에 넣어두면 실행 단계 마찰이 줄어듦.
- 태스크당 단일 커밋 원칙에서 2건 이탈(17/18 분리, 20/21 통합). 대부분은 리뷰어가 허용했지만, 태스크 간 커밋 경계를 엄격히 지키면 bisect·롤백 용이.
- 로그인 timing side-channel, whitespace-only display_name 등 리뷰어가 지적한 "plan-level oversight" 는 Phase 1 시작 전 별도 세션에서 한 번에 처리 필요.

## Phase 1 시작 전 확정 필요

- **OI-1**: 파일럿 5개 시군 최종 결정 (현재 seed는 양평·가평·남양주·춘천·홍천 잠정)
- **OI-3**: 실거주자 증빙 허용 유형 조합
- **OI-4**: Tailwind CDN → Build 전환 시점 판단
- **OI-9**: 브랜드·로고·톤앤매너·컬러 팔레트
- **OI-10**: 도메인 확정 + Cloudflare Tunnel 연동 (RPi 배포와 동시 가능)
- **OI-11**: Post metadata 템플릿 필드 (파일럿 거주자 인터뷰 선행)

## 알려진 기술 부채 (Phase 1 백로그)

- 테스트 TRUNCATE 목록 자동화 (`information_schema.tables` 기반, 하드코딩 제거)
- Alembic `compare_server_default=True` 활성화로 autogenerate 드리프트 탐지
- `pg_enum()` 헬퍼 (`values_callable` 자동 적용) — `app/db/base.py` 또는 `app/db/types.py`
- Form 에러 처리: Pydantic `ValidationError` → 400 + 필드 메시지 (Task 11 후속)
- 로그인 timing side-channel — 없는 사용자도 더미 argon2 verify 수행으로 완화
- `display_name` 공백 전용 값 거부 (pydantic `constr(strip_whitespace=True, min_length=1)`)
- CSRF 토큰 + `slowapi` 레이트 리밋 (로그인 5/min, 업로드 10/h, 댓글 20/h)
- Tailwind 빌드 파이프라인 전환 (OI-4 재검토, npm/pnpm 또는 tailwindcss standalone CLI)
- Backup dump 암호화 (age 또는 GPG symmetric)
- Sentry `traces_sample_rate` 및 이벤트 샘플링 조정 (현재 0.0 → 운영 지표 기반 튜닝)
- Kakao 버튼 공식 가이드 준수 (`#FEE500` + 공식 로고 이미지) — 공개 출시 전
- `get_current_user` 전역 컨텍스트 프로세서화 (현재 각 페이지 수동 주입)

## 테스트 환경 스모크 결과 (2026-04-20)

- 스택: `nestory-app-test` + `nestory-nginx-test` + `nestory-postgres-test` (compose 프로젝트 `nestory-test`)
- 부팅: ~25초 (Alembic 3개 마이그레이션 + seed 5개 시군)
- `/healthz` → `{"status":"ok","env":"test"}`
- `/` → 200, "Nestory" × 4 렌더
- `/auth/login` → "카카오" 1회 (로그인 페이지)
- `/static/js/app.js` → Nginx 직접 서빙 (`Server: nginx/1.27.5`, `Cache-Control: immutable`)
- `POST /auth/signup` → 303 `Location: /` + `set-cookie: nestory_session=...` (SameSite=Lax, HttpOnly)

프로덕션 스택과 차이:
- Cloudflare Tunnel 없음 (Nginx 직접 노출)
- systemd 대신 Docker restart policy
- TLS 없음 (`X-Forwarded-Proto http`)
- `SESSION_COOKIE_SECURE=false`

이 차이들은 RPi 배포 시 런북이 채워주므로 테스트 환경의 검증 범위로 충분.
