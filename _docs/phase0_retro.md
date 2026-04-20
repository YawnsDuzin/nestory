# Phase 0 리트로 (YYYY-MM-DD)

## 소요 시간

- 계획: 3주
- 실제: <N>주

## 완료된 산출물

- [ ] Task 1 — 프로젝트 스캐폴딩 (uv · pyproject · 디렉토리)
- [ ] Task 2 — Config 모듈 (pydantic-settings)
- [ ] Task 3 — 로컬 PostgreSQL (Docker Compose)
- [ ] Task 4 — 테스트 인프라 (pytest · TestClient)
- [ ] Task 5 — SQLAlchemy Base + 세션 + Alembic 초기화
- [ ] Task 6 — User 모델 + 마이그레이션
- [ ] Task 7 — Region 모델 + 테스트 격리 강화
- [ ] Task 8 — 시군 seed 스크립트
- [ ] Task 9 — 비밀번호 해싱 서비스 (argon2)
- [ ] Task 10 — 세션 미들웨어 + 사용자 서비스
- [ ] Task 11 — 회원가입 · 로그인 라우터
- [ ] Task 12 — Kakao OAuth 서비스
- [ ] Task 13 — Kakao OAuth 콜백 라우터 + upsert
- [ ] Task 14 — Admin 부트스트랩 스크립트
- [ ] Task 15 — Base Jinja2 레이아웃 + HTMX/Alpine
- [ ] Task 16 — 홈·로그인·회원가입 페이지
- [ ] Task 17 — structlog 구조화 로깅
- [ ] Task 18 — Sentry 통합
- [ ] Task 19 — GitHub Actions CI
- [ ] Task 20 — Nginx 설정
- [ ] Task 21 — systemd 유닛 + 백업 스크립트
- [ ] Task 22 — Cloudflare Tunnel + 배포 런북
- [ ] Task 23 — RPi 배포 & 스모크 테스트 **(이월 — 하드웨어 준비 후)**
- [ ] Task 24 — UptimeRobot 등록 (계정 필요) **(이월)**
- [ ] Task 25 — 최종 검증 체크리스트 실행

## 미완료·이월 항목

- Task 23 (RPi 실제 배포) — 하드웨어 준비 후 `deploy/README.md` 순서대로 실행
- Task 24 UptimeRobot 계정 등록 + 모니터 생성
- Phase 1 시작 전 다음 체크리스트 완료 필요

## 잘된 점

- 
- 
- 

## 개선점

- 
- 
- 

## Phase 1 시작 전 확정 필요

- OI-3 (실거주자 증빙 유형 최종 조합)
- OI-9 (브랜드·로고·톤앤매너)
- OI-10 (도메인) — 확정되었으면 "완료"로 표기
- Post metadata 템플릿 필드 사전 설계 (OI-11)

## 알려진 기술 부채 (Phase 1 후속 태스크)

- 테스트 TRUNCATE 목록 자동화 (information_schema 기반)
- Alembic `compare_server_default=True` 활성화
- `pg_enum()` 헬퍼 (values_callable 자동 적용)
- Form 에러 처리: Pydantic ValidationError → 400 + 필드 메시지 (Task 11 후속)
- 로그인 timing side-channel (더미 argon2 verify for enumeration 방어)
- CSRF 토큰 + 레이트 리밋 (slowapi)
- Tailwind 빌드 파이프라인 전환 (OI-4 재검토)
- Backup dump 암호화 (age 또는 GPG)
- Sentry `traces_sample_rate` 조정 (현재 0.0)
