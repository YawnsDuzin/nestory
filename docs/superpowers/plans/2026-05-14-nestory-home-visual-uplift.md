# 로그인 후 홈 — 비주얼/사용자 친화 개선 (Visual Uplift)

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use checkbox (`- [ ]`) tracking.

**Goal:** 로그인 후 메인 페이지를 4가지 축으로 비주얼 강화 + 신규 로고(A안 둥지 집) 반영.

- **A) Hero Status Card** — 평면 _welcome_strip → 그라데이션 hero 카드 + 4 Pillar stat 3개 (회고·계획·답변)
- **B) Quick Write 4-카드** — 본문 진입 직후 후기/Journey/질문/계획 카드 grid (배지 가드 시각 반영)
- **C) My Region Spotlight** — 첫 관심 시군은 큰 spotlight, 나머지는 작은 chip grid
- **D) post_card type chip 변주** — review(후회비용)·journey_ep(시리즈)·question(답변 N개+CTA) 메타 차별화
- **Logo Swap** — `logo-c-*.svg` → `logo-a-*.svg` (nav, favicon, manifest)

**Architecture:**
1. `feed.py`에 `UserHomeStats` dataclass + `user_home_stats(db, user)` 함수 추가, `HomeData.user_stats` 필드 추가.
2. `_welcome_strip.html` 전면 교체(Hero Status Card).
3. 신규 컴포넌트 `_quick_write.html` (배지 가드 반영).
4. `home.html` 로그인 블록 재구성: hero → quick_write → mixed feed → 매칭 CTA → region spotlight.
5. `post_card.html`에 type별 chip row 추가 (기존 status_chip 위에).
6. `base.html`, `nav.html` 로고 경로 교체.

**Scope:**
- 비로그인 marketing landing은 **변경 없음**.
- 데이터 모델 변경 0, 마이그레이션 0.
- 라우트 변경 0 (`pages.py` 그대로 — `home_data`만 확장).

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Jinja2 SSR, Tailwind CDN, Alpine.js 3.x, pytest.

---

## File Structure

**Backend**

| 파일 | 변경 |
|---|---|
| `app/services/feed.py` | `UserHomeStats` + `user_home_stats()` 추가, `HomeData.user_stats` 필드 |

**Frontend**

| 파일 | 변경 |
|---|---|
| `app/templates/base.html` | favicon `logo-c-mark.svg` → `logo-a-mark.svg` |
| `app/templates/components/nav.html` | `logo-c-full.svg` → `logo-a-full.svg` |
| `app/templates/components/_welcome_strip.html` | **전면 재작성** — Hero Status Card |
| `app/templates/components/_quick_write.html` | **신규** — 4-카드 grid |
| `app/templates/partials/region_activity_card.html` | 변경 없음 (재사용) |
| `app/templates/partials/_region_spotlight.html` | **신규** — 큰 spotlight 카드 |
| `app/templates/partials/post_card.html` | type별 metadata chip row 추가 |
| `app/templates/pages/home.html` | `{% if current_user %}` 블록 재구성 |
| `app/static/manifest.webmanifest` | icon 경로 갱신 (있다면) |

**Tests**

| 파일 | 변경 |
|---|---|
| `app/tests/integration/test_feed_service.py` | `user_home_stats` 단위 테스트 3개 |
| `app/tests/integration/test_home_dynamic.py` | hero stat / quick_write / spotlight 통합 테스트 4개 |

---

## Tasks

### Task 1: 로고 스왑 (C → A)
- [ ] `base.html`의 favicon · apple-touch-icon path 갱신
- [ ] `nav.html`의 main logo path 갱신
- [ ] manifest 확인 후 필요시 갱신
- [ ] `theme-color` meta 검토 (A안 darker green `#1f3d36` 동일 — 그대로)

### Task 2: Backend — `user_home_stats` 서비스
- [ ] `UserHomeStats` dataclass (review_count, plan_count, answer_count, journey_ep_count, resident_years_label)
- [ ] `user_home_stats(db, user)` — 단일 GROUP BY 쿼리로 type별 published post count
- [ ] `HomeData.user_stats` 필드 추가
- [ ] `home_data()`에서 `user is not None`일 때 채움
- [ ] feed_service 테스트 3개 추가

### Task 3: A) Hero Status Card
- [ ] `_welcome_strip.html` 전면 교체:
  - emerald-50 그라데이션 카드
  - 64px 아바타 + username + badge chip
  - resident_years (있으면) + region (있으면) 1줄
  - 인라인 3 stat row (회고·계획·답변) — 아이콘 + 카운트

### Task 4: B) Quick Write 4-카드
- [ ] `_quick_write.html` 신규:
  - 모바일 grid-cols-2 / sm:grid-cols-4
  - 후기·Journey·질문·계획 — type별 컬러
  - 거주자 미인증 시 후기/Journey는 lock overlay + /me/badge 링크

### Task 5: C) My Region Spotlight
- [ ] `_region_spotlight.html` 신규:
  - 좌측: region.cover_image (없으면 sigungu 이니셜 plate)
  - 우측: sigungu + sido + 주간 카운터 + "허브 보기 →"
  - 사용자 관심 시군 있을 때만 노출
- [ ] home.html: 첫 카드는 spotlight, 나머지는 기존 region_activity_card grid

### Task 6: D) post_card type chip 변주
- [ ] `post_card.html` body chip row 확장:
  - **review**: regret_cost 가 metadata에 있으면 `💸 후회 N만원` chip
  - **journey_episode**: 「title」 ep N/total (total은 journey 메타에서, 없으면 ep N만)
  - **question**: 답변 N + 거주자 답변 CTA chip (이미 detail에서 처리되니 카운터만)
- [ ] metadata 접근은 `post.metadata or {}` 안전 fallback

### Task 7: home.html 로그인 블록 재구성
- [ ] 순서: hero → quick_write → 오늘의 발견 → 매칭 CTA → My Region Spotlight + 추천 시군
- [ ] 비로그인 블록은 1줄도 변경 X

### Task 8: 테스트 갱신
- [ ] 기존 `test_home_dynamic` 의 "안녕하세요" / "거주자 인증" 문구 의존성 점검
- [ ] hero stat 노출, quick_write 4 entry, region spotlight 통합 테스트 4개 추가

### Task 9: Lint + 수동 시각 검증
- [ ] `uv run ruff check app/`
- [ ] `uv run pytest app/tests/ -q`
- [ ] 브라우저 수동 확인 (alice 로그인 / dave 로그인 / 비로그인)

---

## 변경 요약 (예상)

- 데이터 모델 변경 0, 마이그레이션 0, 라우트 변경 0.
- 백엔드: `feed.py` `UserHomeStats` + 함수 1개.
- 프론트엔드: 신규 컴포넌트 2개, 신규 partial 1개, 수정 5개.
- 테스트: 신규 7개.
- 비로그인 marketing landing 변경 0.
