# Nestory 제품 요구사항 문서 (PRD)

**문서 버전**: 1.0
**작성일**: 2026-04-17
**상태**: 초안 (사용자 리뷰 대기)
**작성**: Claude + 제품 오너 (브레인스토밍 세션)

---

## 0. 요약 (Executive Summary)

**Nestory** (Nest + Story, 둥지 + 이야기) 는 은퇴자와 전원주택 예비 입주자를 위한 커뮤니티 웹 서비스입니다. 핵심 가치는 **"전원주택 정착의 전 과정 — 터잡기 → 건축 → 입주 → 3년차 — 을 실거주자의 솔직한 여정으로 아카이빙하고, 예비 은퇴자가 실패·후회 없이 결정할 수 있도록 돕는다."** 입니다.

사용자는 크게 **예비 은퇴자(검토자)** 와 **실거주 은퇴자** 로 나뉘며, 거주자가 콘텐츠를 공급하고 예비자가 소비하는 하이브리드 구조입니다. 제품의 히어로 기능은 **구조화된 입주 후기** 와 **타임라인형 정착 일지(Journey)** 로, 둘은 단일 데이터 모델로 통합됩니다.

초기 버전은 **수도권 근교 5개 시군 파일럿** 으로 시작하고, 기술 스택은 **Python · FastAPI · PostgreSQL · Jinja2 · HTMX · Alpine.js** 를 사용해 **라즈베리파이에서 호스팅** 하는 프로토타입 구조입니다. 신뢰는 **4단계 하이브리드 배지 시스템** 으로 확보합니다.

전체 개발은 **Phase 0–3 (약 27주, 6.5개월)** 로 분해되며, 각 Phase 끝은 독립적으로 출시 가능한 증분입니다. 수익화는 Phase 3 (시공사 디렉토리·리드)에서 도입합니다.

---

## 1. 비전 및 목표

### 1.1 제품 비전

> 전원주택 정착의 전 과정을 실거주자의 솔직한 여정으로 아카이빙하고, 예비 은퇴자가 실패·후회 없이 결정할 수 있도록 돕는 모바일 퍼스트 웹 커뮤니티.

### 1.2 북극성 지표 (North Star Metric)

**"검증된 입주 후기 + 진행 중 Journey의 합계 × 월간 활성 예비자 수"**

콘텐츠 공급(거주자)과 수요(예비자) 가 양쪽 모두 성장해야 지표가 증가하는 복합 구조. 한쪽만 성장하면 의미가 없음.

### 1.3 포지셔닝

| 경쟁 제품 | 핵심 도메인 | Nestory와의 차이 |
|---|---|---|
| 호갱노노 | 도시 아파트 · 투자 | Nestory는 **전원주택 · 정착·삶의 질** |
| 오늘의집 | 인테리어 · 커머스 | Nestory는 **집 외부 + 지역 + 여정** |
| 네이버 카페 | 레거시 PC 중심 | Nestory는 **모바일 · 구조화 · 검색성** |
| 당근 | 현재 거주자 이웃 | Nestory는 **예비자 + 거주자 브리지** |
| 직방 · Zillow | 거래 중개 | Nestory는 **커뮤니티 · 콘텐츠 아카이브** |

**시장 공백**: "예비 입주자가 기존 입주자의 3–5년 여정을 시간순으로 볼 수 있는 모바일 앱"은 국내에 없음. 특히 **"실패·후회 포인트"를 검증된 실명으로 공유** 하는 포맷이 비어 있음. (근거: 섹션 A 레퍼런스 리서치 참조)

### 1.4 핵심 가치 제안

| 대상 | 가치 | 근거 |
|---|---|---|
| **예비 은퇴자** | 실패 사례 기반 의사결정 단축 | 배지로 검증된 후기, Journey로 3년치 경험 압축 |
| **실거주 은퇴자** | 경험이 사라지지 않는 아카이브 + 지역 연결 | 오프라인 카페보다 구조화·검색성·영속성 |
| **관리자** | 품질과 신뢰를 지키는 도구 | 배지 시스템으로 자연스러운 품질 계층 |

---

## 2. 사용자 (Personas)

### 2.1 주요 페르소나

#### P1. 예비 은퇴자 (Prospect) — 주요 수요자

- 연령: 50–65세
- 상태: 전원주택 이주를 검토 중이거나 준비 초기
- 니즈: "실패 사례를 먼저 알고 싶다", "시행착오 비용 줄이기"
- 기기: 모바일 우선, 카카오톡 상시, 네이버 검색 주력
- 앱 내 행동: 후기 탐색·스크랩, Journey 팔로우, Q&A 작성, 지역 허브 방문

#### P2. 실거주 은퇴자 (Resident) — 주요 공급자

- 연령: 55–70세
- 상태: 이미 전원주택 입주. 최근 1개월 ~ 5년차
- 니즈: "내 경험을 남기고 싶다", "이웃을 찾고 싶다", "업자·자재 정보 공유"
- 기기: 모바일 + 데스크톱 혼용
- 앱 내 행동: 후기·Journey 작성, Q&A 답변, 지역 허브 활동, 오프라인 정모 (v2+)

#### P3. 관리자 (Admin) — 내부 운영

- 역할: 배지 승인, 신고 처리, 콘텐츠 큐레이션, 공지
- 초기 인원: 1명 (미정, OI-5 참조)
- 도구: /admin 대시보드

#### P4. 전문가 / 시공사 (Phase 3+)

- 역할: 공식 프로필, 실수요자 응답, 리드 수신
- 인증: 사업자등록증 검증

### 2.2 배지 기반 권한 매트릭스

배지는 **저장 수준 3단계** (DB enum `badge_level`) + **표시 속성 1개** (N년차, 계산값) 구조입니다. "4단계 배지"라는 표현은 사용자 관점의 시각적 구분이며, 실제 권한 분기는 3단계 enum으로 결정됩니다.

| 배지 | 저장 방식 | 획득 방법 | 권한 |
|---|---|---|---|
| 🌱 관심자 | `badge_level = 'interested'` | 회원가입 (기본) | 읽기·댓글·Q&A 작성·스크랩·팔로우 |
| 📍 지역 인증 | `badge_level = 'region_verified'` | GPS 또는 주소 연동 성공 | 위 + 지역 필터 커뮤니티 작성 |
| 🏡 실거주자 | `badge_level = 'resident'` | 증빙 업로드 + 관리자 승인 | 위 + **입주 후기·Journey 작성** + 후기 상단 노출 |
| 🌳 N년차 | 계산값 (`resident_verified_at + N년`) | 실거주자 배지 획득 후 자동 | 실거주자와 동일. 프로필·후기 상단에 "3년차" 등 표시 |

---

## 3. 핵심 사용자 흐름

### 3.1 Flow A — 예비자의 의사결정 여정

```
홈 피드 → 시군 허브 진입 → 후기 필터(예산·평수) →
후기 상세 열람 → 스크랩 → 작성자의 Journey 팔로우 →
관심 있는 Q&A → 카카오 로그인 → 알림 수신
```

### 3.2 Flow B — 거주자의 콘텐츠 생성

```
카카오 로그인 → 프로필 설정 → 실거주자 배지 신청(증빙) →
관리자 승인 대기 → 배지 획득 → 후기 작성(템플릿 + 사진) →
Journey에 묶기 (선택) → 공개 → 댓글·질문 응답
```

### 3.3 Flow C — 관리자 모더레이션

```
관리자 대시보드 → 배지 신청 큐 → 증빙 확인 → 승인/반려 →
신고된 콘텐츠 검토 → 처리(숨김·경고·차단) → 공지 발행
```

---

## 4. 정보 구조 (IA) 및 페이지 맵

### 4.1 전역 네비게이션

모바일 하단 탭 5개:

| 아이콘 | 라벨 | 경로 |
|---|---|---|
| 🏠 | 홈 | `/` |
| 🗺️ | 탐색 | `/discover` |
| ➕ | 작성 (FAB, 로그인 필요) | `/write/*` |
| 🔔 | 알림 | `/notifications` |
| 👤 | 프로필 | `/me` |

데스크톱에서는 상단 헤더로 변환됨.

### 4.2 페이지 트리

```
/                                  홈 피드 (비로그인 OK)
├── /feed                          전체/팔로우 피드
├── /discover                      지역 허브 목록
│   └── /hub/{sigungu}            예) /hub/yangpyeong
│       ├── (허브 홈: 후기+Journey+Q&A+이웃 섹션)
│       ├── /hub/{sigungu}/reviews
│       ├── /hub/{sigungu}/journeys
│       └── /hub/{sigungu}/questions
│
├── /post/{id}                     개별 후기 상세
├── /journey/{id}                  Journey 상세 (연작)
│   └── /journey/{id}/ep/{n}
├── /question/{id}                 Q&A 스레드
│
├── /write/review      🔒🏡        후기 작성 (실거주자 배지 필요)
├── /write/journey     🔒🏡        Journey 생성/편집
├── /write/question    🔒          Q&A 작성 (로그인만)
│
├── /u/{username}                  공개 프로필
│   ├── /u/{username}/posts
│   ├── /u/{username}/journeys
│   └── /u/{username}/scraps
│
├── /me                🔒          내 대시보드
│   ├── /me/scraps
│   ├── /me/following
│   ├── /me/badge                  배지 상태·신청
│   └── /me/settings
│
├── /auth/login                    이메일·카카오 로그인
├── /auth/kakao/callback
├── /auth/signup
│
├── /admin             🛡           관리자 전용
│   ├── /admin/badge-queue
│   ├── /admin/reports
│   ├── /admin/content
│   ├── /admin/users
│   └── /admin/announcements
│
└── (Phase 3+ 예약)
    ├── /map
    ├── /directory/builders
    └── /directory/builder/{id}
```

### 4.3 인증·권한 매트릭스

| 레벨 | 대상 페이지 | 특징 |
|---|---|---|
| Public | `/`, `/feed`, `/discover`, `/hub/*`, `/post/*`, `/journey/*`, `/question/*`, `/u/*` | SEO·공유·검색 유입 대상. 로그인 유도 CTA. |
| 🔒 로그인 | `/me`, `/me/*`, `/notifications`, `/write/question` | 이메일 또는 카카오 로그인 후 접근. |
| 🏡 실거주자 배지 | `/write/review`, `/write/journey` | 관리자 승인된 배지 소유자만. 미획득 시 `/me/badge`로 유도. |
| 🛡 관리자 | `/admin/*` | `users.role = 'admin'`. 초기엔 ENV로 지정, v2에 세분화. |

### 4.4 시군 허브 페이지 구성

시군 허브는 Nestory의 중심 페이지. 섹션 구성:

1. 허브 헤더 — 지역명·등록 거주자 수·후기 수·Journey 수
2. 탭: **후기** / **Journey** / **Q&A** / **이웃**
3. 인기 후기 카드 리스트
4. 진행 중 Journey 카드
5. 실시간 Q&A 스레드
6. (Phase 3) 지역 시공사 섹션

### 4.5 홈 피드 전략

**비로그인** (획득 우선): 추천 허브 3–4개, 인기 후기, 진행 중 Journey, "카카오로 1초 시작" CTA.

**로그인** (개인화): 팔로우 Journey의 새 에피소드, 관심 지역 새 글, 팔로우 추천.

---

## 5. 데이터 모델

### 5.1 핵심 엔티티

#### users
```
id PK
email UNIQUE
password_hash NULLABLE     -- 카카오 전용이면 NULL
kakao_id UNIQUE NULLABLE
username UNIQUE            -- URL 슬러그용
display_name
bio, profile_image_id FK → images
role ENUM('user','admin')
badge_level ENUM('interested','region_verified','resident')
primary_region_id FK → regions NULLABLE
resident_verified_at TIMESTAMPTZ NULLABLE
last_login_at
created_at, updated_at, deleted_at (soft delete)
```

#### regions
```
id PK
sido, sigungu              -- 경기도, 양평군
slug UNIQUE                -- 'yangpyeong'
description, cover_image
is_pilot BOOL              -- 파일럿 시군 여부
created_at
```

#### posts (통합 콘텐츠 테이블)
```
id PK
author_id FK → users
region_id FK → regions
journey_id FK → journeys NULLABLE
parent_post_id FK → posts NULLABLE   -- 답변이 질문을 참조
type ENUM('review','journey_episode','question','answer')
episode_no INT NULLABLE              -- Journey 내 순서
title
body TEXT                            -- 마크다운
metadata JSONB                       -- 타입별 구조화 필드 (5.3)
status ENUM('draft','published','hidden')
view_count INT DEFAULT 0
published_at TIMESTAMPTZ NULLABLE
created_at, updated_at
```

#### journeys
```
id PK
author_id FK → users
region_id FK → regions
title, description, cover_image_id FK → images NULLABLE
start_date DATE                      -- 터잡기 시작일 등
status ENUM('in_progress','completed')
created_at, updated_at
```

#### badge_applications
```
id PK
user_id FK → users
requested_level ENUM('region_verified','resident')
region_id FK → regions
status ENUM('pending','approved','rejected')
reviewer_id FK → users NULLABLE
applied_at, reviewed_at
review_note TEXT
```

#### badge_evidence
```
id PK
application_id FK → badge_applications
evidence_type ENUM('utility_bill','contract','building_cert','geo_selfie')
file_path                            -- 비공개 디렉토리
uploaded_at
scheduled_delete_at                   -- 승인 30일 후 자동 삭제
```

#### images
```
id PK
owner_id FK → users
post_id FK → posts NULLABLE
file_path_orig, file_path_thumb, file_path_medium, file_path_webp
width, height, size_bytes
alt_text
order_idx INT                        -- 포스트 내 순서
status ENUM('processing','ready','failed')
uploaded_at
```

#### comments
```
id PK
post_id FK → posts
author_id FK → users
parent_id FK → comments NULLABLE     -- 스레디드
body TEXT
status ENUM('visible','hidden')
created_at, updated_at
```

#### tags, post_tags
```
tags(id, name UNIQUE, slug UNIQUE)
post_tags(post_id, tag_id)  -- M:N
```

#### 라이트 테이블 (상호작용)
```
post_likes(post_id, user_id, created_at)
post_scraps(post_id, user_id, created_at)
user_follows(follower_id, following_id, created_at)
journey_follows(journey_id, user_id, created_at)
```

#### notifications
```
id PK
user_id FK → users         -- 수신자
type ENUM(...)
source_user_id FK NULLABLE
target_type, target_id
is_read BOOL DEFAULT FALSE
created_at
```

#### reports
```
id PK
reporter_id FK → users
target_type, target_id
reason ENUM(...)
detail TEXT
status ENUM('pending','resolved','rejected')
handled_by FK → users NULLABLE
handled_at
created_at
```

#### audit_logs
```
id PK
actor_id FK → users
action ENUM(...)
target_type, target_id
note TEXT
created_at
```

#### announcements
```
id PK
author_id FK → users        -- admin
title, body
pinned BOOL DEFAULT FALSE
published_at
```

### 5.2 주요 인덱스

- `posts (region_id, published_at DESC)` — 허브 피드
- `posts (journey_id, episode_no)` — Journey 에피소드
- `posts (author_id, published_at DESC)` — 프로필
- `posts (type, status, published_at DESC)` — 전체 피드
- GIN `posts.metadata` — JSONB 필드 필터
- GIN `to_tsvector(title || body)` — 전문 검색 (한국어는 Phase 2+ mecab)
- `notifications (user_id, is_read, created_at DESC)` — 알림 큐
- `badge_applications (status, applied_at)` — 관리자 큐

### 5.3 Post.metadata JSONB 스키마 (type=review/journey_episode)

```json
{
  "house_type": "단독|타운하우스|듀플렉스",
  "size_pyeong": 32,
  "land_size_pyeong": 180,
  "budget_total_manwon": 32000,
  "budget_breakdown": {
    "land": 15000,
    "construction": 14000,
    "etc": 3000
  },
  "move_in_date": "2024-03",
  "construction_period_months": 9,
  "satisfaction_overall": 4,
  "regrets": ["단열", "부지 선정"],
  "highlights": ["마당", "자연광"],
  "builder_info": { "name": "**건축", "verified": false },
  "journey_ep_meta": {
    "phase": "터|건축|입주|1년차|3년차",
    "period_label": "2024 봄"
  }
}
```

JSONB로 시작. 안정화되면 자주 조회되는 필드는 컬럼으로 승격. 최종 템플릿 필드는 파일럿 거주자 인터뷰로 검증 (OI-11).

### 5.4 배지 상태 머신

```
가입 시 → badge_level='interested' 🌱
  │
  │ (GPS 또는 주소 인증)
  ▼
badge_level='region_verified' 📍
primary_region_id = X
  │
  │ BadgeApplication 생성 (requested_level='resident')
  │ → 증빙 업로드 → status='pending'
  │
  │ 관리자 검토
  ├─ rejected → interested 상태 유지 (재신청 가능)
  │
  ▼ approved
badge_level='resident' 🏡
resident_verified_at = now()
→ 후기·Journey 작성 권한 부여
  │
  │ 시간 경과 (일배치 계산)
  ▼
🌳 N년차 표시 속성 (resident_verified_at + 365d / 3y / 5y)
```

### 5.5 증빙 유형

| 타입 | 요구사항 | 신뢰도 |
|---|---|---|
| utility_bill | 전기·수도·가스 고지서 (본인명 + 주소, 금액 마스킹) | ⭐⭐⭐ |
| contract | 매매·건축 계약서 일부 (인감·금액 마스킹) | ⭐⭐⭐ |
| building_cert | 건축물대장 사본 | ⭐⭐⭐ |
| geo_selfie | 집 앞 셀카 + GPS EXIF | ⭐⭐ |

정확한 허용 조합은 OI-3에서 확정.

---

## 6. 기술 아키텍처

### 6.1 기술 스택

| 레이어 | 선택 | 비고 |
|---|---|---|
| 언어 | Python 3.12 | 단일 언어 풀스택 |
| 웹 프레임워크 | FastAPI | ASGI, Pydantic v2 |
| ASGI 서버 | Uvicorn (uvloop) | 워커 2 |
| 리버스 프록시 | Nginx | 정적 파일·미디어 캐싱 |
| DB | PostgreSQL 16 (arm64) | RPi 공식 지원 |
| ORM | SQLAlchemy 2.x + Alembic | 마이그레이션 |
| 템플릿 | Jinja2 | SSR |
| 프론트엔드 인터랙션 | HTMX + Alpine.js | 빌드 단계 없음 |
| 인증 | itsdangerous 서명 쿠키 + argon2-cffi | 카카오 OAuth 2.0 |
| 이미지 처리 | Pillow + pillow-heif | WebP 지원 |
| 백그라운드 태스크 | FastAPI BackgroundTasks (v1) | v2+ ARQ 검토 |
| 호스팅 | Raspberry Pi (OS Bookworm 64) | 프로토타입 |
| 외부 노출 | Cloudflare Tunnel (cloudflared) | DDoS·SSL 위임 |
| CSS | Tailwind CSS (CDN 시작 → Build 전환) | OI-4에서 최종 결정 |
| 관측성 | structlog + Sentry + UptimeRobot | 무료 티어 |
| 테스트 | pytest + FastAPI TestClient + Playwright | 단위·통합·E2E |
| 컨테이너 (선택) | Docker | 개발 환경 재현성용 |

### 6.2 디렉토리 구조

```
nestory/
├── app/
│   ├── main.py                   # FastAPI 엔트리
│   ├── config.py                 # pydantic-settings (ENV)
│   ├── deps.py                   # DI (세션·현재 사용자·배지 가드)
│   ├── db/
│   │   ├── base.py               # SQLAlchemy Base
│   │   ├── session.py            # engine, session
│   │   └── migrations/           # Alembic
│   ├── models/                   # ORM 모델 (user, post, journey, badge, ...)
│   ├── schemas/                  # Pydantic (form·JSON)
│   ├── repositories/             # DB 접근 (쿼리 함수)
│   ├── services/                 # 비즈니스 로직
│   │   ├── auth.py
│   │   ├── badges.py
│   │   ├── posts.py
│   │   ├── images.py             # Pillow 리사이즈·WebP·EXIF 제거
│   │   ├── storage.py            # 로컬 FS 추상화 (→ 후일 S3 스왑)
│   │   └── notifications.py
│   ├── routers/
│   │   ├── pages/                # Jinja2 전체 페이지
│   │   ├── htmx/                 # HTMX 파샬 (댓글·좋아요·무한스크롤)
│   │   ├── api/                  # JSON API (모바일 앱 v3+ 대비)
│   │   └── admin/
│   ├── templates/
│   │   ├── base.html
│   │   ├── layouts/
│   │   ├── pages/                # (home, hub, post, journey, me, admin)
│   │   ├── components/           # 카드·배지·네비
│   │   └── partials/             # HTMX 응답 조각
│   ├── static/
│   │   ├── css/
│   │   ├── js/                   # htmx.min.js, alpine.min.js, app.js
│   │   └── icons/
│   ├── workers/                  # BackgroundTasks
│   └── tests/ (unit · integration · e2e)
├── alembic.ini
├── pyproject.toml                # uv 또는 poetry
├── .env.example
├── deploy/
│   ├── nginx.conf
│   ├── systemd/nestory.service
│   └── cloudflared.yml
└── scripts/
    ├── seed_regions.py           # 시군 초기 데이터
    ├── backup.sh
    └── restore.sh
```

### 6.3 시스템 다이어그램 (요청 흐름)

```
┌──────────┐  HTTPS  ┌──────────────────┐ Tunnel  ┌─────────────────────────────┐
│ Browser  │ ──────▶ │ Cloudflare Edge  │ ──────▶ │ Raspberry Pi                │
│ (모바일  │ ◀────── │ (DDoS·SSL·캐시)  │ ◀────── │ cloudflared 아웃바운드      │
│  / 데탑) │         └──────────────────┘         │                             │
└──────────┘                                      │ ┌─────────────────────────┐ │
                                                  │ │ Nginx (:80 내부)        │ │
                                                  │ │ · 정적 캐싱 · gzip      │ │
                                                  │ └──────┬──────────────────┘ │
                                                  │        │ reverse proxy      │
                                                  │        ▼                    │
                                                  │ ┌─────────────────────────┐ │
                                                  │ │ Uvicorn (:8000)         │ │
                                                  │ │  FastAPI app            │ │
                                                  │ │   Jinja2 SSR + HTMX     │ │
                                                  │ │   BackgroundTasks       │ │
                                                  │ └────┬──────────┬─────────┘ │
                                                  │      ▼          ▼           │
                                                  │ ┌─────────┐ ┌──────────┐    │
                                                  │ │Postgres │ │Local FS  │    │
                                                  │ │  :5432  │ │/var/     │    │
                                                  │ └────┬────┘ │ nestory/ │    │
                                                  │      │      └────┬─────┘    │
                                                  │      ▼           ▼          │
                                                  │ ┌────────────────────────┐  │
                                                  │ │백업: pg_dump · rsync   │  │
                                                  │ │ → 외장 USB + B2 무료   │  │
                                                  │ │ 일 1회 · 14일 보관     │  │
                                                  │ └────────────────────────┘  │
                                                  └─────────────────────────────┘
```

### 6.4 이미지 업로드 파이프라인

1. **검증** (동기): 크기 ≤ 10MB · MIME 화이트리스트 · magic bytes 확인 · 치수 ≤ 6000x6000
2. **EXIF 제거** (동기, 중요): GPS·개인정보 제거. HEIC는 JPEG로 변환 후.
3. **원본 저장** (동기): `/media/orig/YYYY/MM/{uuid}.jpg`
4. **images 레코드** 생성 (status='processing')
5. **BackgroundTasks**:
   - Pillow로 thumb(320px)·medium(960px) 생성
   - WebP 변환 (원본·medium)
   - images 레코드 업데이트 (status='ready', 경로 저장)

RPi 성능 주의: 동시 업로드 세마포어 2–3. 10MB 사진 1장 ~1.5–3초 (RPi 4B).

### 6.5 인증 흐름

**이메일/비밀번호**: argon2id 해싱 · 세션 쿠키 발급

**카카오 OAuth 2.0**:
```
1. /auth/kakao/start → 302 https://kauth.kakao.com/oauth/authorize
2. 사용자 동의 → callback?code=...&state=...
3. /auth/kakao/callback
   · state 검증 (CSRF)
   · code → access_token 교환
   · GET /v2/user/me → kakao_id, nickname, email (동의 시)
   · users upsert (kakao_id 기준)
   · 세션 쿠키 발급 (SessionMiddleware · SameSite=Lax · HTTPOnly · Secure)
4. → Redirect /
```

### 6.6 HTMX 파샬 패턴

```
[서버 렌더 페이지]
  /post/123 → 전체 HTML (base layout 포함)

[HTMX 파샬]
  POST /htmx/post/123/like → <button class="liked">♥ 42</button>
  POST /htmx/post/123/comment → <article class="comment">...</article>
  GET /htmx/post/123/comments?page=2 → <div>...더 많은 댓글...</div>
```

클라이언트 상태관리 라이브러리 없음. Alpine.js는 드롭다운·토글 등 소규모 UI에만.

---

## 7. 배포 및 운영

### 7.1 환경

| 환경 | 용도 | 인프라 |
|---|---|---|
| local | 개발 | macOS/Windows · Docker Compose (Postgres) · uvicorn --reload |
| staging (선택) | 검증 | RPi 또는 VPS 작은 인스턴스 |
| production | 실서비스 | Raspberry Pi 4B 4GB · 64-bit Bookworm |

### 7.2 외부 노출

**Cloudflare Tunnel (cloudflared)** 채택.
- 장점: 포트포워딩 불필요, DDoS·SSL 자동, 홈 IP 비공개, 무료
- 대체: DDNS + 공유기 포트포워딩 (비추천: IP 노출·보안 부담)
- 폴백: DDNS 경로 비활성 상태로 사전 설정 (CF 장애 대비)

### 7.3 백업

- **DB**: `pg_dump` 일 1회 → 외장 USB (`/mnt/backup/pg/YYYY-MM-DD.sql.gz`) + Backblaze B2 rsync
- **미디어**: rsync `--link-dest` 증분 → 외장 USB + B2
- **보관**: 14일 일간 + 6개월 주간
- **복원 리허설**: 월 1회 (Docker로 임시 DB 복원 + 주요 쿼리 확인). 미실행 시 경보.

### 7.4 systemd 유닛

- `nestory.service` — Uvicorn
- `nestory-backup.timer` — 백업 일배치
- `nestory-maintenance.timer` — 증빙 파일 만료 삭제·N년차 승급 계산

---

## 8. 보안 및 개인정보

### 8.1 보안 체크리스트

| 영역 | 조치 |
|---|---|
| 비밀번호 | argon2id (passlib) |
| 세션 | itsdangerous 서명 쿠키 · SameSite=Lax · HTTPOnly · Secure |
| CSRF | form hidden token + HTMX hx-headers 검증 |
| 레이트 리밋 | slowapi — 로그인 5/min · 업로드 10/hour · 댓글 20/hour |
| 파일 업로드 | magic bytes · 크기 제한 · EXIF 제거 · 파일명 UUID |
| XSS | Jinja2 autoescape · 마크다운은 bleach 화이트리스트 |
| SQL 인젝션 | SQLAlchemy ORM 전용 · raw SQL 금지 |
| CSP | script-src self · img-src self data: |
| 증빙 파일 | 비공개 디렉토리 · 승인 30일 후 자동 삭제 |
| 주소 공개 | 시군 단위까지만 (상세 주소 DB 저장만, 공개 안 함) |
| 회원 탈퇴 | soft delete 7일 유예 후 영구 삭제 · 법정 보존 항목 익명화 유지 |

### 8.2 개인정보 수집 최소화 원칙

- 필수: 이메일 또는 카카오 ID, 표시명
- 선택: 프로필 이미지, 소개, 주요 시군 (배지용)
- 민감: 증빙 파일 → 승인 30일 후 자동 삭제, 비공개 저장소

---

## 9. Phased 로드맵

### 9.1 전체 타임라인

| Phase | 기간 | 한 줄 요약 |
|---|---|---|
| **Phase 0** · Foundation | Week 1–3 (약 3주) | 인프라·로그인·기반 세팅 |
| **Phase 1** · Core MVP | Week 4–11 (약 8주) | 허브 + 입주 후기 + 배지 |
| **Phase 2** · Journey + 커뮤니티 | Week 12–19 (약 8주) | Journey·Q&A·팔로우·모더레이션 |
| **Phase 3** · 플랫폼 확장 | Week 20–27 (약 8주) | 지도·시공사·수익화 |

총 27주 (약 6.5개월). 각 Phase 끝은 독립적으로 출시 가능한 증분.

### 9.2 Phase 0 · Foundation (Week 1–3)

**인프라·기반**
- 프로젝트 스캐폴딩 (uv · pyproject)
- RPi 환경 구축 (Python 3.12 · PostgreSQL 16)
- Cloudflare Tunnel + Nginx + systemd
- Alembic 초기 마이그레이션
- Sentry + UptimeRobot 연동
- CI (GitHub Actions — lint · test · build)

**도메인 초기**
- User · Region 모델 + seed (수도권 5개 시군)
- 이메일/비밀번호 로그인
- Kakao OAuth 연동
- Admin 부트스트랩 (ENV 지정)
- Base layout · Jinja2 템플릿 · HTMX·Alpine 로드
- 테스트 인프라 (pytest · factory-boy · httpx)

**완료 기준**: 로컬에서 로그인 → 빈 홈 페이지 렌더. RPi에 배포되어 도메인 접속 가능. pg_dump 자동 실행.

### 9.3 Phase 1 · Core MVP (Week 4–11)

**포함 기능**
- 배지 3단계 (관심자·지역인증·실거주자). 신청·증빙·관리자 승인 큐
- Post CRUD (type=review). 구조화 템플릿 · 초안/발행
- 이미지 파이프라인 (EXIF 제거 · 3단 리사이즈 · WebP)
- 시군 허브 페이지 `/hub/{slug}` (후기 목록·필터·정렬)
- 후기 상세 `/post/{id}` + 스크랩·좋아요·댓글
- 검색 (PostgreSQL FTS 기본 · 지역·평수·예산 필터)
- 홈 피드 (비로그인/로그인 분기)
- 프로필 `/u/{username}` · `/me`
- 알림 (bell UI)
- 관리자 v1 (배지 승인 · 콘텐츠 숨김 · 사용자 조회)
- 반응형 UI

**성공 기준**: 파일럿 지역에서 실거주자 10명 · 후기 30건. 주간 활성 사용자 100+. TTFB p95 ≤ 600ms.

### 9.4 Phase 2 · Journey + 커뮤니티 (Week 12–19)

**포함 기능**
- Journey CRUD · 에피소드 순서 · phase 라벨 · 타임라인 뷰
- Journey 팔로우 + 새 에피소드 알림
- N년차 배지 자동 계산
- Q&A (type=question/answer) · 허브 내 섹션 · 태그
- User follow · 개인화 피드 가중치
- 신고 · 모더레이션 워크플로우
- 공지사항 (`/admin/announcements`)
- 관리자 v2 (KPI 대시보드 · 신고 처리 이력)
- 이메일 알림 (주간 다이제스트 · 배지 승인)

**성공 기준**: Journey 5건 이상 진행 중 · 팔로우 100+ · 주간 재방문율 40% · Q&A 답변률 60%+.

### 9.5 Phase 3 · 플랫폼 확장 (Week 20–27)

**포함 기능**
- Kakao Map 통합 (`/map` · 마커 · 클러스터)
- 고급 검색 (JSONB 필터 · 저장된 검색 · 알림)
- 시공사 디렉토리 (`/directory/builders` · 프로필 · 인증 배지 · 평점)
- 업체 온보딩 (사업자등록증 검증 · 프리미엄 리스팅)
- 리드 폼 ("상담 요청" · 이메일·알림 · 전환 추적)
- 수익화 훅 (스폰서드 허브 배너 · 프리미엄 슬롯 · 리드 수수료)
- 분석 확장 (코호트 · 리텐션 · 콘텐츠 성과)
- 확장 준비 (미디어 R2/S3 이관 옵션 · DB 읽기 복제본 옵션)

**성공 기준**: 시공사 10+ · 월 리드 30+ · 첫 유료 계약 1건 이상.

### 9.6 Phase별 리스크 게이트

| Phase | 게이트 질문 | 미달 시 대응 |
|---|---|---|
| 1 종료 | 파일럿 지역에서 콘텐츠 30건·사용자 100명 확보됐는가? | Phase 2 대신 콘텐츠 시딩 스프린트 (오프라인·파트너십) |
| 2 종료 | Journey가 실제로 쓰이는가? 재방문율 상승? | Journey UX 재설계 · Phase 3 지연 |
| 3 종료 | RPi가 현재 트래픽을 감당하는가? | CCU 50 넘으면 VPS 이관 · 미디어 R2 분리 |

### 9.7 오프-로드맵

| 항목 | 재검토 시점 |
|---|---|
| 모바일 네이티브 앱 | DAU 300+ |
| 한 달 살기 체험 매칭 | 별도 서비스로 분리 검토 |
| 오프라인 정모 매칭 | Phase 2 팔로우 안정화 후 |
| VR·드론 투어 | 시공사 프로필 외부 링크로만 |
| AI 추천·자동 요약 | 콘텐츠 5,000건 이상 후 |

---

## 10. 비기능 요구사항 (NFR)

| 영역 | 요구사항 |
|---|---|
| 성능 | TTFB p95 ≤ 600ms (허브·홈) · LCP ≤ 2.5s (4G) · 20 CCU 목표 / 50 CCU 상한 |
| 가용성 | 월 99% (월 약 7h 다운타임 허용) · VPS 이관 후 99.5% |
| 백업·복구 | RPO 24h · RTO 4h · 월 1회 복원 리허설 의무 |
| 접근성 | WCAG 2.1 AA · 최소 폰트 16px · 버튼 44×44px · 대비 4.5:1 |
| 브라우저 | Chrome/Safari/Edge/Samsung Internet 최근 2버전 · 구형은 graceful degradation |
| 반응형 | 모바일(375–414px) · 태블릿(768px) · 데스크톱(1280px) |
| SEO | SSR · OG 태그 · sitemap.xml · robots.txt · JSON-LD (Article·Review) |
| 언어 | 한국어 단일 (키-값 파일 · v3+ 다국어 대응 여지) |
| 관측성 | structlog · Sentry · UptimeRobot · /healthz · Phase 2+ Prometheus /metrics |

---

## 11. 법적 · 컴플라이언스

| 항목 | 처리 |
|---|---|
| 개인정보보호법 (PIPA) | 처리방침 페이지 · 증빙 파일 30일 자동 삭제 · 탈퇴 7일 유예 후 파기 |
| 정보통신망법 | 카카오 OAuth로 본인확인 간접 충족 · 마케팅 이메일 별도 동의 |
| 14세 미만 | 약관에 "만 14세 이상" 명시 · 가입 시 생년 확인 |
| 위치기반서비스 | v1 시군 단위는 해당 없음 · Phase 3 지도 도입 시 신고 검토 |
| 통신판매중개 (Phase 3+) | 런칭 전 사업자등록 + 통신판매업 신고 |
| 쿠키 | 필수만 사용 (분석 쿠키 도입 시 동의 배너) |
| 저작권 | 사용자 소유 + 서비스 운영용 비독점 라이선스 · 탈퇴 후 처리 명시 |

---

## 12. 주요 리스크 및 완화

| 리스크 | 영향 | 완화 |
|---|---|---|
| 콜드 스타트 | 🔴 치명적 | 파일럿 5개 시군 집중 · 관리자 10건 시드 · 네이버 카페 파트너십 · 오프라인 |
| 광고성·위장 후기 | 🔴 치명적 | 배지 엄격 승인 · 패턴 감지 · 신고 24h 처리 · 연 1회 재검증 |
| RPi 하드웨어 장애 | 🟠 높음 | 일일 백업 · 이중화 · 예비 SD · 복원 리허설 · VPS 이관 48h 런북 |
| 관리자 1인 병목 | 🟠 높음 | 배지 주 5건 이내 · 자동 반려 룰 · Phase 2 모더레이터 승격 |
| 주소·프라이버시 노출 | 🟠 높음 | 시군 단위 공개 · DB는 별도 · EXIF 제거 · 프로필 시군 비공개 옵션 |
| Cloudflare 터널 의존 | 🟡 중간 | 폴백 DDNS 경로 사전 설정 |
| 50 CCU 스케일 한계 | 🟡 중간 | VPS 이관 런북 · 미디어 R2 분리 · 읽기 복제본 |
| 법적 분쟁 (시공사) | 🟡 중간 | 신고 절차 명시 · 표현 가이드 · 반론권 보장 |
| 1인 개발 번아웃·스코프 크립 | 🟡 중간 | Phase 게이트 엄격 준수 · 오프-로드맵 방어 · 주간 범위 점검 |

---

## 13. 테스트 전략

| 유형 | 도구 | 적용 |
|---|---|---|
| Unit | pytest · factory-boy · freezegun | services · repositories · utils · 커버리지 70%+ |
| Integration | FastAPI TestClient + Docker Postgres | 페이지 · HTMX 파샬 · API · 인증 가드 |
| E2E (Phase 2+) | Playwright | 핵심 플로우: 가입→후기 작성, 배지 신청→승인, Q&A |
| 부하 | locust · k6 | Phase 1 말 허브 페이지 50 CCU · Phase 3 지도 API |
| 보안 | bandit · trivy · ZAP | CI SAST · 릴리스 전 수동 ZAP |
| 수동 QA | 실기기 체크리스트 | Galaxy 중저가 · iPhone · 데스크톱 · 시니어 접근성 워크스루 |

---

## 14. KPI · 성공 지표

### 성장
- 월간 활성 사용자 (MAU)
- 신규 가입 / 로그인 전환율
- 실거주자 배지 보유자 수
- 월 신규 후기 · Journey 에피소드 수

### 품질
- 후기 평균 길이 · 사진 수
- Q&A 답변률 · 첫 답변 소요시간
- 신고 처리 시간 p50/p95
- 배지 승인 소요시간 (목표: 48h 이내)

### 참여
- 주간 재방문율 (WAU/MAU)
- 스크랩 · 팔로우 · Journey 팔로우
- Journey 완독률

### 기술
- 페이지 TTFB p50/p95
- 이미지 처리 대기열 길이
- 에러율 (목표 < 0.5%)
- 업타임 (목표 99%)

### 수익 (Phase 3+)
- 시공사 온보딩 수
- 월 리드 수 · 유료 전환율

---

## 15. 오픈 아이템 (미결정)

| 번호 | 결정 필요 | 결정 시점 |
|---|---|---|
| OI-1 | 파일럿 5개 시군 정확 선정 (예: 양평·가평·남양주·춘천·홍천) | Phase 0 |
| OI-2 | 지역 연고 · 초기 콘텐츠 시딩 전략 | Phase 0 |
| OI-3 | 실거주자 증빙 허용 유형 최종 조합 | Phase 1 초 |
| OI-4 | CSS 프레임워크 (Tailwind CDN · Build · 순수 · DaisyUI) | Phase 0 |
| OI-5 | 첫 관리자 (본인 · 별도 모집 · 지인) | Phase 0 |
| OI-6 | 네이버 카페 등 기존 커뮤니티 관계 | Phase 1 |
| OI-7 | 예산 (도메인 · Sentry 유료 · Kakao 비즈 · 백업 스토리지) | Phase 0 |
| OI-8 | 팀 구성 (1인 · 2–3인 · 외주 일부) | Phase 0 |
| OI-9 | 브랜드 · 로고 · 톤앤매너 · 컬러 팔레트 | Phase 0 |
| OI-10 | 도메인 · SNS 계정 등록 (nestory.kr? 동명 체크) | Phase 0 |
| OI-11 | Post metadata 템플릿 필드 최종 (파일럿 거주자 인터뷰) | Phase 1 초 |

---

## 부록 A · 레퍼런스 리서치 요약

브레인스토밍 중 분석한 10+ 레퍼런스. 자세한 분석은 브레인스토밍 전사 참조.

### A.1 국내 참조

- **호갱노노** — 지도 기반 아파트 후기·데이터 플랫폼. 벤치마크: 데이터 + 후기 결합, 환경 데이터 시각화. 회피: 투자·시세 프레임.
- **직방** — 매물 중개 + VR 홈투어. 벤치마크: VR 투어, 중개사 인증 배지. 회피: 거래 중심 프레임(커뮤니티 약함).
- **네이버 카페 (전원생활·전원주택 라이프)** — 레거시 커뮤니티. 벤치마크: 카테고리 구조, "집짓기 일지" 연재 포맷. 회피: 광고성 글·진입장벽.
- **오늘의집** — 홈 인테리어 UGC 슈퍼앱. **가장 중요한 벤치마크**: 집들이 포맷·사진 태그·스크랩·팔로우 루프. 회피: 커머스 과몰입.
- **당근** — 하이퍼로컬 커뮤니티. 벤치마크: 동네 인증, 매너온도, 비즈프로필. 회피: 도시 밀집 전제.

### A.2 해외 참조

- **Nextdoor** — 미국 동네 SNS. 벤치마크: 주소 인증 온보딩, Recommendations 탭. 회피: 부정적 민원 게시물 → 모더레이션 정책.
- **Zillow/Redfin** — 부동산 플랫폼. 벤치마크: "What Locals Say" · 데이터 투명성. 회피: AVM은 한국 전원주택에 부적합.
- **The Villages · 55places** — 미국 은퇴자 커뮤니티. 벤치마크: 은퇴자 UX · 라이프스타일 카테고리 · 동호회. 회피: 게이티드 전제(한국 정서 다름).

### A.3 추가 참조

- **미스터멘션/리브애니웨어** — 한 달 살기. 체험 입주 아이디어 (v3+ 검토).
- **Reddit r/homestead** — 실패담 공유 문화. AMA 시리즈 포맷 벤치마크.
- **삼쩜삼·뱅크샐러드** — 시니어 친화 UX (큰 폰트 · 단계별 위저드 · 대화식 입력).

### A.4 핵심 결론

- **시장 공백**: "전원주택 정착 전 과정(Pre-move → Move-in → Post-move)을 구조화된 후기로 아카이빙하는 모바일 커뮤니티"
- **Must-have Top 3**: 구조화된 입주 후기 템플릿 · 지역 기반 실거주 인증 · 타임라인형 정착 일지
- **안티패턴 Top 2**: 커머스·거래 중개 과몰입 · 투자·시세 프레임

---

## 부록 B · 용어집

- **Nest + Story**: 제품명 (둥지 + 이야기)
- **Prospect**: 예비 은퇴자 (검토자)
- **Resident**: 실거주 은퇴자 (콘텐츠 공급자)
- **Journey**: 터잡기→건축→입주→N년차로 이어지는 여정형 연작 콘텐츠 컨테이너
- **Post**: 모든 콘텐츠 단위 (type 필드로 review/episode/question/answer 구분)
- **Hub**: 시군 단위 지역 허브 페이지 (`/hub/{slug}`)
- **Badge**: 4단계 신뢰 인증 시스템 (관심자 🌱 / 지역인증 📍 / 실거주자 🏡 / N년차 🌳)
- **Evidence**: 배지 신청 증빙 파일 (승인 30일 후 자동 삭제)
- **OI**: Open Item — 브레인스토밍 중 미결정 사항

---

**끝**
