# Phase 1 Complete — dev → main PR

> **PR 생성 URL** (브라우저에서 클릭):
> https://github.com/YawnsDuzin/nestory/compare/main...dev?expand=1
>
> 아래 description을 PR 본문에 복붙하세요.

**제목 (권장)**: `Phase 1 — Core MVP (P1.3 콘텐츠 + P1.4 허브·검색 + P1.4b Region Match Wizard + P1.5 알림·PWA·PostHog·관리자 v1)`

**Squash 권장**: 148 commits → 단일 squash commit

---

## Summary

Phase 1 Core MVP (PRD §9.3) 코드 구현 완료. 5개 sub-plan이 dev에 누적되어 있으며 본 PR로 main에 일괄 머지합니다.

### 포함 범위

- **P1.3 콘텐츠·이미지** — Post CRUD (review/journey_episode/question/answer/plan), Pydantic discriminated union metadata 검증, EXIF 제거 + WebP 3단 리사이즈 이미지 파이프라인 (PG-기반 작업 큐).
- **P1.4 허브·검색·인터랙션** — `/discover` 시군 그리드, `/hub/{slug}` 4탭, `/search` (pg_trgm + simple FTS hybrid), `/feed`, `/u/{username}` 프로필, like/scrap/comment.
- **P1.4b Region Match Wizard** (Pillar R 차별화) — 5문항 → Top 3 시군 deterministic 채점 + claude-haiku-4-5 LLM 자연어 설명 (정적 fallback).
- **P1.5a 알림** — `Notification` row 단일 진실 원천 + `create_notification` self-skip helper + 4 trigger 통합 (badges/comments/journey episode/answer) + bell HTMX 30s polling + `/notifications` 페이지.
- **P1.5b PWA + 카카오 인앱 호환** — `manifest.webmanifest`, 최소 Service Worker (offline shell), UA 기반 카카오 인앱 배너, `/_offline` 라우트.
- **P1.5c PostHog 활성화** — `analytics.emit` no-op stub → 실제 `posthog>=3.0` SDK wiring. SHA-256 distinct_id, 익명 anon_id 세션 보존, `app_env != production` 시 no-op.
- **P1.5d 관리자 v1** — `/admin/content` (hide/unhide + AuditLog), `/admin/users` (검색 + 필터), `/admin/reports` (pending GET-only, resolve는 P2).

### 변경 규모

- **148 commits** (`0ceda2d..4cc749d`)
- **233 files changed, +29,545 / −775**
- **180+ 신규 통합 테스트** (factory-boy 기반)
- **마이그레이션 신규 (P1.3 이후)**: posts·images·journeys·comments·post_validations·moderation·notifications·jobs·user_interest_regions·badge_applications·tags·interactions·search indexes·region_scoring_weights·추가 pilot weights — 모두 linear chain

### 신규 라우트 (사용자 surface)

| 영역 | 경로 |
|---|---|
| 콘텐츠 | `/post/{id}` · `/write/{review,journey,question,plan,answer}` · `/journey/{id}/ep/{n}` · `/question/{id}` |
| 허브·탐색 | `/discover` · `/hub/{slug}` (home/reviews/journeys/questions/neighbors) · `/feed` · `/search` · `/u/{username}/{posts,journeys,scraps}` |
| 인터랙션 | `POST /post/{id}/{like,unlike,scrap,unscrap,comment}` |
| 시군 매칭 | `/match/wizard` · `/match/wizard/q/{n}` · `POST /match/wizard/submit` · `GET /match/result` |
| 알림 | `/notifications` · `/notifications/_bell` · `POST /notifications/{id}/read` · `POST /notifications/read-all` |
| PWA | `/_offline` · `/static/manifest.webmanifest` · `/static/sw.js` |
| 관리자 v1 | `/admin/content` · `POST /admin/content/{id}/hide,unhide` · `/admin/users` · `/admin/reports` (기존 `/admin/badge-queue` 유지) |

### 기술 스택 (Phase 0 이후 변경)

- **Python 3.12 / FastAPI / SQLAlchemy 2.x / Alembic**
- **Jinja2 SSR + HTMX + Alpine.js + Tailwind (CDN)**
- **PostgreSQL 16** (host 5433) — `pg_trgm` extension + GIN partial indexes (`status='published' AND deleted_at IS NULL`)
- **신규 dep**: `anthropic>=0.40` (LLM 설명, OAuth Bearer), `posthog>=3.0` (analytics)
- **PG-기반 작업 큐** (LISTEN/NOTIFY + SKIP LOCKED) — 별도 worker 프로세스

### 차별화 4축 (PRD §1.5) 구현 상태

- **T (Time-lag 시계열 회고)** — Phase 2: 1·3년차 알림 큐, 재작성률 메트릭
- **C (Regret Cost)** — Pydantic discriminated union으로 `regret_items` 정량화 데이터 모델 P1.3 완료. 통계 화면은 Phase 2.
- **R (Region Match)** ✅ **P1.4b 완료** — Wizard + Top 3 + AI 설명 + `user_interest_regions` UPSERT
- **V (Peer Validation)** — `post_validations` 모델·테이블 P1.1 완료. 투표 UI는 Phase 2.

---

## Test plan (docker-up PC 1세션 작업)

```bash
# 1. PG + worker 컨테이너
docker compose -f docker-compose.local.yml up -d

# 2. 마이그레이션 적용 (head: 8a4f9b3c2d51)
uv run alembic upgrade head
uv run alembic current   # 확인

# 3. 데모 시드
uv run python -m app.scripts.seed_demo --reset

# 4. 풀 pytest (180+ 테스트)
uv run pytest app/tests/ -q

# 5. 린트
uv run ruff check app/

# 6. 개발 서버
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Manual QA 체크리스트 (golden path)

- [ ] 비로그인 `/` → 🎯 시군 매칭 CTA → wizard 5문항 → `/match/result` Top 3 카드
- [ ] 가입 → `/me/badge` 신청 → admin이 `/admin/badge-queue` 승인 → 신청자 🔔 bell unread 1
- [ ] 다른 사용자 댓글 → 글 작성자 🔔 unread 증가 → 클릭 → `/post/{id}` 이동 + 알림 read
- [ ] admin `/admin/content` → 게시글 hide → published 목록에서 사라짐 + AuditLog row
- [ ] admin `/admin/users` → username 검색 → 결과 표시
- [ ] admin `/admin/reports` → "현재 처리 대기 중인 신고가 없습니다" (또는 pending 목록)
- [ ] 카카오톡으로 사이트 URL 공유 → 인앱 브라우저 진입 → 노란 배너 노출
- [ ] Chrome DevTools Lighthouse → PWA installable + manifest detected + SW registered

### (선택) 외부 서비스 통합 검증

- [ ] `.env`에 `ANTHROPIC_OAUTH_TOKEN` 설정 → wizard 결과 페이지에서 자연어 1-2문장 설명 (정적 fallback 대신)
- [ ] prod 배포 + `POSTHOG_API_KEY` 설정 → PostHog dashboard에 첫 이벤트 도착 확인

---

## P2로 이월 (PRD §9.4 Phase 2)

- **카카오 알림톡 발송** — OI-12 비즈채널 등록 결정 후. `JobKind.NOTIFICATION` worker handler stub 활성화.
- **신고 resolve/reject 액션** (관리자 v2)
- **사용자 본인 신고 제출** (`POST /post/{id}/report`)
- **Web Push** (PWA + VAPID 키)
- **TIMELAPSE_REMIND · REVALIDATION_PROMPT 일배치** — Pillar T 응답률 측정 시작
- **사용자 비활성화·차단** (관리자 v2)
- **Pillar V 활성화** (cross-validation 투표 UI · 자동 큐잉)
- **Pillar C 출시** (regret_items 통계 + 시군 허브 `/regret`)
- **Journey 시리즈 view + 팔로우 + 새 에피소드 알림**
- **Q&A 답변 작성 surface** (모델은 P1.4 완료, UX 추가)
- **N년차 배지 자동 계산 + 재검증 일배치**

---

## 알려진 잔여 / 기술 부채

- `app/routers/me.py:82` — pre-existing E501 line-too-long (P1.5 작업과 무관). 별도 cleanup 필요.
- 일부 P1.4 cleanup 후속 작업: `app/routers/content.py`·`journey.py`의 SQLAlchemy 1.x `db.query()` 잔존 — 신규 P1.4 코드는 모두 2.x `select()` 사용. 별도 cleanup task.
- `Post.metadata_` Python ↔ DB `metadata` column 컨벤션 (Phase 0 이후 유지).
- `partials/journey_card.html` 일부 미사용 (Journey 시리즈 페이지 P2 진입 시 사용 예정).
- LLM `anthropic` SDK auth — 현재 `default_headers` Bearer 방식. SDK 업그레이드 시 `auth_token`/`api_key` 파라미터 재검토.

---

## Phase 1 메트릭 (PRD §9.3 성공 기준 게이트)

> 본 PR은 코드만 머지. 운영 메트릭은 별도 시점.

- 파일럿 지역 실거주자 10명 / 후기 30건 / 주간 활성 100+ — Phase 1 종료 게이트 측정 필요
- TTFB p95 ≤ 600ms / 검색 첫 페이지 LCP ≤ 2.5s — Phase 1 운영 시작 후 PostHog/외부 모니터링

---

## 검토 포인트 (리뷰어 우선순위)

1. **Region Match Wizard의 LLM fallback 안전성** (`app/services/match.py:generate_explanations`): 모든 예외를 catch + 정적 텍스트 — 페이지 항상 200. 운영 시 OAuth 만료/네트워크 장애 시에도 표시 가능.
2. **알림 trigger emit이 자기 자신 skip 통과** (`create_notification` helper): 4 trigger 모두 helper 경유. 자기 글에 자기 댓글 시 알림 row X.
3. **PostHog 환경별 분기**: `app_env != production` 시 emit no-op. 개발/테스트 환경에서 PostHog 트래픽 0.
4. **관리자 콘텐츠 hide/unhide AuditLog**: `AuditAction.CONTENT_HIDDEN`이 hide와 unhide 양쪽에 사용됨 — `note` 필드로 구분 (`unhide:` prefix). 별도 `CONTENT_UNHIDDEN` enum 추가는 P2.
5. **카카오 인앱 배너 강제 우회 X**: 사용자 선택권 우선. P2에서 `kakaolink` deeplink 외부 호출 검토 가능.

---

🤖 본 PR은 Claude Code (Opus 4.7 1M context) 자율 작업으로 구현됨. 코드 품질·spec 매핑은 sub-plan별 review subagent + 최종 holistic review 통과.
