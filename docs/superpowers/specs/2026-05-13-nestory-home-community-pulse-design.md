# Nestory — 로그인 후 홈 "커뮤니티 펄스" 리디자인 설계

**작성일**: 2026-05-13
**대상 단계**: P1.5 진입 전·후 어느 쪽이든 가능 (PostHog 이벤트 emit 위치만 stub 주석). 데이터 모델 변경 X — `feed.py` 서비스 확장 + 신규 템플릿 1개 + FAB 컴포넌트만.
**관련 PRD**: §1.5 4축 차별화(T·C·R·V), §1.5.3 Region Match Wizard, §6.2 권한 가드, §14.5 PostHog 이벤트 카탈로그
**관련 메모리**: `project_nestory_handoff.md`, `feedback_consistency_first.md`
**관련 코드**: [home.html:6-135](../../app/templates/pages/home.html#L6-L135) 현재 로그인 홈, [feed.py:22-88](../../app/services/feed.py#L22-L88) home_data, [pages.py](../../app/routers/pages.py) home 라우트, [partials/post_card.html](../../app/templates/partials/post_card.html) Threads 카드

## 0. 핵심 결정 요약

| 항목 | 결정 |
|---|---|
| 적용 범위 | **로그인 사용자 홈(`home.html` `{% if current_user %}` 블록)만**. 비로그인 marketing 랜딩은 변경 없음. |
| 컨셉 | "커뮤니티 펄스" — 오늘의 발견 mixed feed를 1차 시각 자산으로, 쓰기는 FAB로 강등. |
| 정보 구조 | ① 컴팩트 웰컴 스트립 → ② **오늘의 발견 (mixed feed)** → ③ 매칭 위저드 슬림 CTA → ④ 내 관심/추천 시군(activity counter) → FAB. |
| 제거 | 기존 "쓰기" 4-카드 섹션 ([home.html:37-80](../../app/templates/pages/home.html#L37-L80)), "팔로우 중 Journey 새 에피소드" 별도 섹션 ([home.html:83-99](../../app/templates/pages/home.html#L83-L99)). 후자는 mixed feed에 흡수+boost. |
| Mixed feed 구성 | review + journey_episode + question 혼합. 팔로우 중인 journey의 최신 ep는 recency boost. 사용자의 관심 시군 일치 시 +boost. 8개 노출. |
| Region activity | 시군별 최근 7일 신규 published Post 수 → 카드에 표시. 단일 쿼리(GROUP BY region_id)로 처리. |
| Match CTA | wizard 진행 상태 모델(`MatchSession` 등)은 현재 부재(`match.py`는 stateless scoring). 따라서 슬림 CTA는 **"시작 →" 단일 상태**만. 진행률 표시는 향후 별도 spec. |
| FAB | 우하단 floating. Alpine.js dropdown으로 후기/Journey/질문/계획 4 entry. 모바일 우선. 권한 체크는 기존 라우트 가드 그대로(거주자 외엔 `/me/badge` 리다이렉트). |
| Fallback | mixed feed가 비어 있으면 페이지 자체에서 onboarding empty-state (Match Wizard 강조). 관심 시군 없으면 추천 시군 표시(현 동작 유지). |
| 트래킹 | `home_feed_card_click` `home_fab_open` `home_fab_action` `home_region_activity_click` 4개 이벤트 stub 주석 추가. P1.5에서 PostHog 통합. |

## 1. 배경 및 동기

### 1.1 현재 로그인 홈의 문제

스크린샷(2026-05-13) 기준:

1. **시각 위계 부재** — 5개 섹션(웰컴/쓰기/팔로우 Journey/매칭/추천 시군)이 동일한 회색 테두리 흰 카드. 어느 게 중요한지 첫 스캔으로 모름.
2. **빈 상태가 전면 노출** — "아직 팔로우하는 Journey가 없습니다"가 큰 섹션 헤더와 함께 노출. 신규 사용자 대부분이 보는 첫 인상이 빈 화면.
3. **"쓰기" 4-카드가 vertical real estate를 점유** — 사용자가 홈에 와서 가장 자주 하는 행동은 **읽기**(다른 후기·질문 탐색). 쓰기는 nav `/쓰기` 드롭다운 + 페이지별 진입점도 이미 존재.
4. **권한 위계가 시각적으로 평면** — 후기/Journey는 거주자 인증 필요, 질문/계획은 누구나 가능. 4-그리드 동일 스타일이 이 차이를 가림.
5. **차별화 4축의 첫 화면 노출 약함** — T(시계열)·C(후회 비용)·V(거주자 검증)는 mixed feed의 카드 메타(badge·Journey ep 번호·시군)로만 잠재 노출됨. 현재 홈은 R(Region Match)을 "5문항 추천" CTA 1개로만 노출.
6. **추천 시군 카드가 무미건조** — "양평군 / 경기도" 텍스트 2줄. 사용자가 클릭할 동인이 없음 — 이 시군이 지금 활발한지, 신규 후기가 있는지 모름.

### 1.2 왜 피드 우선인가

PRD §1.5 4축이 모두 **콘텐츠 카드**로 표현된다 — Time-lag(1년차 vs 3년차 회고 카드), Regret Cost(후회 카테고리 태그·금액), Region Match(시군 라벨·관심 시군 boost), Peer Validation(거주자 verified 아이콘). 따라서 mixed feed는 4축을 동시에 시각화하는 가장 자연스러운 수단.

읽기 우선 동선은 또한 **체류 시간 증가 → 가입 직후 onboarding drop 감소** 가설을 검증할 수 있게 한다 (P1.5 PostHog 분석 첫 가설로 활용).

## 2. 결정한 구조

### 2.1 섹션 순서·위계

```
┌─────────────────────────────────────────────────┐
│ [A] @alice_yp  [🏡 거주자 인증]    [🔔] [⚙]    │ ← compact strip (h ~ 56px)
├─────────────────────────────────────────────────┤
│ ✨ 오늘의 발견                                   │ ← H2
│ ┌──────────────┐ ┌──────────────┐               │
│ │ [thumb 16:9] │ │ [thumb 16:9] │               │ ← Threads 카드 재사용
│ │ @bob.yp · 양평 · 3년차          │               │
│ │ "단열 후회 한 줄..."           │               │
│ │ [후기] ♥ 12 · 💬 4             │               │
│ └──────────────┘ └──────────────┘               │
│ ... 총 8개 (2-col, mobile 1-col)                 │
│              [더 보기 →]                         │
├─────────────────────────────────────────────────┤
│ 🎯 나에게 맞는 시군 찾기  (slim)                  │
│   5문항 매칭 시작 · 또는 진행 중이면 "이어하기 3/5" │
├─────────────────────────────────────────────────┤
│ 🌳 내 관심 시군 / 추천 시군                       │
│ ┌──────────────┐ ┌──────────────┐               │
│ │ 양평군 · 경기도                 │               │
│ │ 이번 주 새 후기 3 · 답변 가능 2 │               │ ← region_activity
│ │ [허브 가기 →]                  │               │
│ └──────────────┘ └──────────────┘               │
└─────────────────────────────────────────────────┘
                           ┌──[+ 쓰기]──┐  ← FAB (fixed bottom-right)
                           │            │
                           │ 클릭 시:    │
                           │  ✎ 후기    │
                           │  🗺 Journey │
                           │  ? 질문    │
                           │  📅 계획   │
                           └────────────┘
```

### 2.2 컴팩트 웰컴 스트립

현행 그라데이션 카드(`[home.html:8-35]`)를 1행으로 압축:

- 좌: 40px 아바타 + `@username` + 배지 칩 (작게).
- 우: 알림 벨(nav에 이미 있으므로 제거 가능), 또는 비움.
- 그라데이션 배경 제거 → 페이지 전체가 mixed feed에 시각 자원 집중.
- 모바일에선 username 옆 배지 칩이 1줄에 맞도록 `truncate` 또는 wrap.

### 2.3 오늘의 발견 (mixed feed) — 핵심

**데이터** (`feed.py` 신규 함수 `home_mixed_feed(db, user)`):

쿼리 1개로 review + journey_episode + question을 union — Python에서 score 계산해서 정렬.

```python
# 후보군: 최근 14일 published, deleted_at IS NULL,
#         type ∈ {REVIEW, JOURNEY_EPISODE, QUESTION},
#         status = PUBLISHED
candidates = limit_30  # 충분히 넉넉히 가져와서 Python에서 score+sort

# score(post) =
#   base_recency: max(0, 14 - days_since_published) / 14   (0..1)
# + popularity:  log10(view_count + 1) * 0.3              (clamp 0..0.6)
# + follow_boost: post.journey_id in user.followed_journey_ids ? 0.5 : 0
# + interest_region_boost: post.region_id in user_interest_region_ids ? 0.3 : 0
#   (user_interest_region_ids = SELECT region_id FROM user_interest_regions WHERE user_id=?)
# + type_diversity_penalty: 이미 같은 type이 3개 이상 선택됐으면 -0.2
```

상위 8개. type 다양성 페널티는 한 타입(가령 review)이 피드를 독점하지 않도록 함.

**카드** — 기존 `partials/post_card.html`을 그대로 사용. 이미 다음 모두 처리:
- 아바타, 작성자, 거주자 verified 배지
- 본문 line-clamp-4 + 첫 이미지 미리보기 (rounded-2xl)
- post_type chip (review/journey_ep/question), 시군 라벨
- 좋아요·댓글·스크랩·공유 액션, 조회수

추가 분기 1개 — journey_episode 카드일 때 작성자 라인에 `Journey「{title}」ep {episode_no}` 표시(이미 detail_url 분기는 됨, 메타 텍스트만 추가).

**그리드** — sm 이상 2-col(`grid sm:grid-cols-2 gap-4`), 모바일 1-col. 카드 사이 구분선은 카드 자체의 그림자/border로 처리(기존 Threads 카드는 separator가 없으므로 wrapper에 `divide-y sm:divide-y-0`).

**"더 보기"** — `/discover`로 (기존 라우트). hubpage가 type별 필터 지원하므로 query string 안 붙임.

**빈 상태** — 후보 0개일 때 (시드 데이터 없는 신규 환경):
```
아직 추천할 콘텐츠가 없어요.
[5문항 매칭으로 시군 찾기 →]  [Journey 탐색하기 →]
```
이 빈 상태는 onboarding 신호로 작동.

### 2.4 매칭 위저드 슬림 CTA

현재(`[home.html:101-113]`)의 emerald 박스 카드를 1행 슬림 CTA로 축소:

```
🎯 나에게 맞는 시군 찾기 — 5문항으로 Top 3 추천   [시작 →]
```

진행률 표시는 **이번 spec 범위 외**. `match.py`가 stateless deterministic scoring이라 wizard 진행 세션 모델이 부재함. 추후 wizard step persistence가 도입되면 별도 spec으로 진행률 UI 추가.

### 2.5 내 관심 시군 / 추천 시군

`feed.py:home_data`에 `region_activity` 필드 추가:

```python
@dataclass
class RegionActivity:
    region: Region
    new_reviews_7d: int
    new_questions_7d: int
```

쿼리 — 단일 쿼리 (`SELECT region_id, type, COUNT(*) ... WHERE published_at > now() - interval '7 days' GROUP BY region_id, type`). 사용자의 `UserInterestRegion` 항목이 있으면 그 시군들 우선 노출, 없으면 기존 `is_pilot DESC, id ASC` 순(현 `home_data` 동작 유지).

카드 — region label + sido + 활동 카운터 2개:

```
양평군 · 경기도
이번 주  ✎ 새 후기 3   ? 새 질문 2
```

카운터가 0인 항목은 숨김. 둘 다 0이면 기존 description(있을 때)으로 fallback.

호버 시 emerald accent (현 `hover:border-stone-300`보다 강조).

### 2.6 쓰기 FAB

새 컴포넌트 `app/templates/components/_write_fab.html` — Alpine.js 사용.

```html
<div class="fixed bottom-6 right-6 z-40 sm:bottom-8 sm:right-8" x-data="{ open: false }">
  <button type="button" class="..." @click="open = !open" aria-label="쓰기">
    {{ icon("pen-square", 24) }}
  </button>
  <div x-show="open" x-transition x-cloak class="absolute bottom-16 right-0 w-56 rounded-xl bg-white shadow-lg border border-stone-200 py-2">
    <a href="{{ '/write/review' if is_resident else '/me/badge' }}" class="..."> ✎ 후기 </a>
    <a href="{{ '/write/journey' if is_resident else '/me/badge' }}" class="..."> 🗺 Journey </a>
    <a href="/write/question" class="..."> ? 질문 </a>
    <a href="/write/plan" class="..."> 📅 정착 계획 </a>
  </div>
</div>
```

- 거주자 권한 분기는 **템플릿 분기 + 서비스 가드 양쪽 유지** (안티패턴 회피 — `CLAUDE.md`의 services-only 권한 원칙). 즉 `/write/review` 라우트는 가드에서 `require_badge(RESIDENT)`로 막힘, 템플릿은 표시 단순화를 위해 `/me/badge`로 분기.
- FAB 자체는 모든 로그인 사용자 노출. 권한 없는 사용자가 후기 클릭 → `/me/badge`로 자연스럽게 유도(현재 4-카드 섹션과 같은 동작).
- 모바일 safe area를 위해 `bottom-6` 사용. iOS PWA에서 `env(safe-area-inset-bottom)`은 P1.5 PWA 작업에 위임.
- nav의 "쓰기" 드롭다운은 그대로 유지 — desktop nav 사용자에겐 두 진입점이 공존. (드롭다운 제거는 별도 결정 사항.)

### 2.7 페이지 wrapper

`<main class="mx-auto max-w-3xl px-5 sm:px-6 py-6">` — 기존 `base.html`의 `max-w-3xl`이 mobile-first 의도와 정확히 일치하므로 유지. FAB은 viewport-fixed이므로 wrapper 영향 없음.

## 3. 기술 설계

### 3.1 백엔드 — `app/services/feed.py` 변경

**신규 dataclass:**

```python
@dataclass
class RegionActivity:
    region: Region
    new_reviews_7d: int
    new_questions_7d: int

@dataclass
class HomeData:
    # 기존 필드 유지 (popular_reviews / recent_journeys / featured_testimonial 는
    # 비로그인 랜딩이 계속 사용하므로 제거 X)
    recommended_regions: list[Region]
    popular_reviews: list[Post]
    recent_journeys: list[Post]
    followed_episodes: list[Post]
    featured_testimonial: Post | None
    # 신규
    mixed_feed: list[Post]                # 로그인 사용자용 8개
    region_activity: list[RegionActivity] # 4개 (recommended_regions와 1:1 매핑)
```

**신규 함수:**

```python
def home_mixed_feed(db: Session, user: User, *, limit: int = 8) -> list[Post]: ...
def region_activity_summary(db: Session, regions: list[Region]) -> list[RegionActivity]: ...
```

`home_data()`는 이 두 함수를 호출해 `HomeData`를 채움. 비로그인 사용자에겐 `mixed_feed=[]`, `region_activity=[]`. `recommended_regions`는 로그인 시 `UserInterestRegion`이 있으면 그 시군들 우선 + 부족 시 기본 정렬 보충.

**쿼리 성능 검토:**

- mixed_feed: 1 query (3 type WHERE IN + 14일 윈도 + 30개 LIMIT) + Python sort. 30 rows 정도면 `selectinload(author, region)`까지 포함해도 100ms 이내. 추가로 사용자의 followed journey id / user_interest_region id를 가져오는 lightweight query 2개.
- region_activity: 1 query (4개 region × 2 type = 8 row GROUP BY). 빠름.

총 약 4 추가 query — 기존 home_data 4 query + 4 = 8 query, max-w-3xl 단일 페이지 기준 acceptable. N+1 없음.

### 3.2 프론트엔드 — 템플릿 변경

**변경 파일:**

| 파일 | 변경 |
|---|---|
| `app/templates/pages/home.html` | `{% if current_user %}` 블록 전체 재작성. 비로그인 블록은 1줄도 변경 X. |
| `app/templates/components/_write_fab.html` | **신규**. Alpine dropdown FAB. |
| `app/templates/components/_welcome_strip.html` | **신규**. compact welcome row. |
| `app/templates/partials/post_card.html` | journey_episode 카드 메타에 `「{title}」ep {episode_no}` 표시. **최소 변경 1줄**. |
| `app/templates/partials/region_activity_card.html` | **신규**. 시군 카드. |
| `app/templates/base.html` | FAB include 추가 (current_user 있을 때만): `{% if current_user %}{% include "components/_write_fab.html" %}{% endif %}`. 푸터 위. |

**경로 가정 검증:** 모두 P1.2/P1.4에 도입된 디렉토리 구조와 일치 — `components/_xxx.html`은 underscore prefix(unused alone), `partials/xxx.html`은 직접 포함.

### 3.3 권한 가드

라우트는 변경 없음. 기존 가드 동작 그대로:

- `home.html` 자체는 anon 허용 (라우터에서 user nullable).
- 쓰기 라우트(`/write/review`, `/write/journey`)는 P1.2 도입된 `require_badge(BadgeLevel.RESIDENT)` 그대로.
- FAB의 거주자 분기는 표시만 단순화 — 가드 우회 아님.

### 3.4 PostHog 이벤트 stub

새 이벤트 4개를 `app/services/analytics.py:EventName`에 enum value로만 추가, emit은 P1.5에서:

```python
# 신규
HOME_FEED_CARD_CLICK = "home_feed_card_click"
HOME_FAB_OPEN = "home_fab_open"
HOME_FAB_ACTION = "home_fab_action"     # props: action ∈ {review|journey|question|plan}
HOME_REGION_ACTIVITY_CLICK = "home_region_activity_click"
```

템플릿에는 `{# TODO(P1.5 PostHog): home_feed_card_click {post_id: ..., type: ...} #}` 주석으로 emit 위치 표시.

### 3.5 테스트

**서비스 단위(`app/tests/integration/test_feed_service.py` 확장):**

| 테스트 | 검증 |
|---|---|
| `test_home_mixed_feed_returns_max_limit` | 후보 다수일 때 8개 LIMIT |
| `test_home_mixed_feed_boosts_followed_journey` | 팔로우 ep가 비-팔로우보다 상위 정렬 |
| `test_home_mixed_feed_boosts_interest_region` | 관심 시군 post가 상위 정렬 |
| `test_home_mixed_feed_diversity_penalty` | 같은 type 4개 이상 연속 노출 안 됨 |
| `test_home_mixed_feed_empty_when_no_content` | 후보 0개 → 빈 리스트 |
| `test_region_activity_counts_correctly` | 7일 윈도 GROUP BY 정확성 |
| `test_home_data_prefers_user_interest_regions` | UserInterestRegion 있을 때 recommended_regions 상위 정렬 |

**통합 페이지(`app/tests/integration/test_home_dynamic.py` 확장):**

| 테스트 | 검증 |
|---|---|
| `test_home_shows_mixed_feed_when_logged_in` | 로그인 + 시드 → "오늘의 발견" 섹션 + 8 카드 |
| `test_home_shows_empty_state_when_no_content` | 빈 DB → empty state CTA |
| `test_home_renders_fab_for_logged_in_user` | FAB 버튼 + dropdown 4 link |
| `test_home_no_fab_for_anon` | 비로그인엔 FAB 없음 |
| `test_home_region_activity_shows_counters` | 시드된 시군의 weekly counter 표시 |

**factory 사용** — 기존 PostFactory/RegionFactory + `add_journey_follow`/`add_user_interest_region` helper 사용. 신규 factory 추가 없음.

### 3.6 데모 시드 영향

`scripts/seed_yangpyeong_demo.py`는 그대로 mixed feed에 다양한 type을 채워주므로 변경 불필요. 로컬에서 demo seed 후 `alice.yp@example.com`로 로그인하면 mixed feed가 시각적으로 채워져야 함 — 이게 1차 수동 확인 체크포인트.

## 4. UX 세부

### 4.1 카드 시각 처리

- 이미지 첨부가 있는 post는 16:9 thumbnail 크게 (기존 Threads 카드 그대로).
- 이미지 없는 post는 type별 그라데이션 placeholder(작은 thumb 영역):
  - review: emerald-50 → white
  - journey_ep: amber-50 → white
  - question: sky-50 → white
- 카드 hover: `hover:shadow-md transition`. border 색 변화 X (Threads 톤 유지).

### 4.2 모바일 우선

- ≤ sm: 1-col grid, FAB은 우하단 `bottom-6 right-6`.
- ≥ sm: 2-col grid, FAB은 `bottom-8 right-8`.
- max-w-3xl 컨테이너로 desktop도 좁게 — 사진 위주 콘텐츠가 더 잘 읽힘.

### 4.3 접근성

- FAB 버튼 `aria-label="쓰기 메뉴 열기"`, dropdown 열린 상태 `aria-expanded`.
- Mixed feed 카드는 기존 `<article>` 시맨틱 + 각 액션 버튼 `aria-label` 그대로.
- 키보드: FAB 버튼 focus → Enter로 dropdown 열기 → Tab으로 4 항목 순회 → Esc로 닫기 (Alpine `@keydown.escape.window`).

### 4.4 다크모드

현재 사이트 전체가 light only. 본 변경에서도 darkmode 미고려 — 기존 톤 유지.

## 5. 영향 범위 / 비-목표

### 5.1 영향 범위

- 코드 변경:
  - `app/services/feed.py` — 3 신규 함수 + HomeData 필드 3개.
  - `app/templates/pages/home.html` — `{% if current_user %}` 블록 재작성.
  - `app/templates/base.html` — FAB include 1줄 추가.
  - `app/templates/components/_write_fab.html`, `_welcome_strip.html` — 신규.
  - `app/templates/partials/region_activity_card.html` — 신규.
  - `app/templates/partials/post_card.html` — journey_ep 메타 1줄 추가.
  - `app/services/analytics.py` — EventName 4개 추가.
  - 테스트 — 위 §3.5 목록.
- 모델 변경 **없음**. 마이그레이션 **없음**.
- 비로그인 사용자 경험 변경 **없음**.

### 5.2 비-목표 (이번 작업에 포함 X)

- PostHog 실제 호출 — P1.5 OI-14에서 통합.
- 카드 좋아요·스크랩 인터랙티브 동작 — 기존 라우트 그대로(현재도 detail page 이동 동작).
- 다크모드, i18n, 회전 위젯.
- 새 모델/마이그레이션. (`MatchSession`이 P1.4에서 도입 안 됐다면 match_progress=None만 반환 — 신규 도입 X.)
- nav "쓰기" 드롭다운 제거 — FAB과 공존 결정.

## 6. 빌드 순서 (구현 계획용 힌트)

1. `feed.py`에 신규 dataclass + 함수 3개 추가, 기존 home_data 확장. 서비스 단위 테스트 7개.
2. `partials/region_activity_card.html`, `partials/post_card.html`(journey_ep 메타) 작성.
3. `components/_welcome_strip.html`, `components/_write_fab.html` 작성.
4. `pages/home.html`의 `{% if current_user %}` 블록 재작성, `base.html`에 FAB include.
5. 페이지 통합 테스트 5개.
6. `analytics.py`에 EventName 4개 추가 + 템플릿 TODO 주석.
7. 로컬에서 demo seed → `alice.yp` 로그인 → 수동 확인 체크리스트 (mixed feed 8개·FAB·시군 활동 카운터·빈 상태).

## 7. 리스크 / 미결

| 항목 | 리스크 | 완화 |
|---|---|---|
| Mixed feed 정렬 가중치 | 사용자 cohort별 효과 다를 수 있음 | P1.5 PostHog로 click-through 측정 후 weight 튜닝 |
| Region activity 카운터 0/0 | 신규 시군 카드가 비어 보임 | description fallback + 양평 외 카운터 0이면 카드 자체 숨김도 가능(폴리시 결정) |
| Wizard 진행률 표시 부재 | "이어하기 X/5" UX 못 함 | 본 spec 범위 외. wizard step persistence 모델 도입 시 후속 spec에서 처리. |
| FAB이 콘텐츠 가림(모바일 긴 스크롤 끝) | 마지막 액션(예: 시군 카드 클릭) 영역 일부 겹침 | 푸터에 `pb-24 sm:pb-16` 추가해 viewport 하단 safe area 확보 |
| nav 드롭다운과 FAB 중복 | 데스크톱 사용자에게 2개 진입점 | 의도된 공존. nav 드롭다운 제거는 사용 데이터 본 뒤 결정 |

## 8. 수동 확인 체크리스트 (구현 완료 시점)

- [ ] `alice.yp@example.com` 로그인 → 홈 mixed feed 8개 표시, 이미지 thumbnail 정상.
- [ ] `dave.yp@example.com` (REGION_VERIFIED) 로그인 → FAB 후기/Journey 클릭 시 `/me/badge`로 리다이렉트.
- [ ] FAB Alpine dropdown: 클릭 열림 / Esc 닫힘 / 바깥 클릭 닫힘.
- [ ] 모바일 viewport(375px) — 1-col grid, FAB가 본문 마지막 카드 가리지 않음.
- [ ] 빈 DB (fresh `alembic upgrade head` 후 demo seed 없이) → empty state CTA 노출.
- [ ] 비로그인 방문 → 기존 marketing landing 그대로(변경 0).
- [ ] `ruff check app/` 통과.
- [ ] 신규 + 기존 pytest 모두 통과.
