# Nestory — 랜딩 히어로 섹션 리디자인 설계

**작성일**: 2026-05-13
**대상 단계**: P1.4 직후 / P1.5 진입 전. 데이터 모델·서비스 신규 X — UI·카피·feed 서비스 1개 필드 추가만.
**관련 PRD**: §1.5 4축 차별화(T·C·R·V), §1.5.3 Region Match Wizard, §14.5 PostHog 이벤트 카탈로그
**관련 메모리**: `project_nestory_handoff.md` (P1.4 종료 상태), `feedback_consistency_first.md`
**관련 코드**: [home.html:140-164](../../app/templates/pages/home.html#L140-L164) 현재 히어로, [feed.py:22-86](../../app/services/feed.py#L22-L86) home_data, [pages.py:13-23](../../app/routers/pages.py#L13-L23) home 라우트

## 0. 핵심 결정 요약

| 항목 | 결정 |
|---|---|
| 적용 범위 | 비로그인 방문자 marketing landing의 hero 섹션만. 로그인 사용자 홈은 변경 없음. |
| 차별화 메시지 축 | PRD T축(Time-lag, 시계열 회고)을 헤드라인으로 직접 노출. C축(Regret Cost) 보조. |
| 후기 인용 출처 | 동적 — `home_data.featured_testimonial = popular_reviews[0]`. 하드코딩 금지. |
| 회전 위젯 | **불채택**. 정적 1개 인용. (접근성·SEO·구현 비용 모두 X) |
| 페르소나 카드 | 하단 별도 섹션([home.html:211-241](../../app/templates/pages/home.html#L211-L241))을 히어로로 흡수, 기존 위치 삭제. |
| CTA | 1차 = 카카오, 2차 = 이메일 가입(보조 텍스트 링크로 강등). 의사결정 단순화. |
| 트래킹 | PostHog 이벤트 emit 위치 주석만 남김. 실제 호출은 P1.5(OI-14) 시점에 통합. |
| Fallback | featured_testimonial 없을 때(시드 전 환경) 인용 카드 자체 숨김. 헤드라인·페르소나·CTA는 항상 노출. |

## 1. 배경 및 동기

### 1.1 현재 hero의 문제

```
"전원생활 정착의 여정, 우리가 함께합니다"
"예비 입주자부터 1년차·3년차 거주자까지. 후기·Journey·Q&A로 이어지는 신뢰 커뮤니티."
[카카오로 1초 시작] [이메일로 가입]
```

- **차별점이 카피 어디에도 없음** — "신뢰 커뮤니티"는 모든 부동산 후기 사이트가 쓰는 카피.
- **PRD 4축의 첫 화면 노출 0** — T·C·R·V 중 한 축도 hero에서 보이지 않음.
- **제너릭 vague** — "예비 입주자부터 1년차·3년차 거주자까지"는 카테고리 나열일 뿐, 사용자가 "왜 여기여야 하나"를 모름.
- **페이지 정보 구조 역전** — hero는 추상적이고 하단 섹션(4 Pillar·페르소나·How it works)이 구체적. 첫 화면에서 흥미를 잃은 방문자는 스크롤하지 않음.

### 1.2 왜 T축을 직접 노출하나

PRD §1.5에 정의된 4축 중 **T(Time-lag, 시계열 회고)**가 경쟁 후보 사이트들과 가장 차별화된다 — "1년차에 좋다고 했던 사람의 3년차 회고"는 일회성 후기 사이트(다방·직방·블로그)가 구조적으로 만들 수 없는 데이터. 이를 첫 줄에 질문형으로 노출하면 방문자가 "그게 뭐지?"로 호기심 진입 → 페이지 체류 시간 증가 가설.

C축(후회 비용 정량 데이터)은 인용 카드의 구체적 금액으로 동시 전달.

### 1.3 왜 회전 위젯이 아닌 정적 1개

| 비교 | 회전 위젯 | 정적 1개 |
|---|---|---|
| 구현 비용 | htmx polling 또는 vanilla JS | 0 (Jinja 변수 1개) |
| 접근성 | 자동 회전은 prefers-reduced-motion 분기·일시정지 버튼 필수 | 해당 없음 |
| SEO | 첫 인용만 SSR에 포함 | 인용 자체가 본문 텍스트로 SSR |
| 콘텐츠 신선도 | 새로고침 시마다 다른 후기 | popular_reviews 정렬이 바뀌면 자연 갱신 |
| ROI | P1 단계에 비용 대비 효익 ↓ | 즉시 적용 가능 |

P2에서 인용이 핵심 KPI에 영향을 미치는 것이 측정되면 그때 회전 도입 검토.

## 2. 범위

### 2.1 In-scope

- `app/templates/pages/home.html` 비로그인 분기(`{% else %}` 이후) 수정:
  - hero 섹션(line 140-164) 재구성
  - 기존 페르소나 섹션(line 211-241) 삭제 — hero로 흡수
  - "인기 후기" 그리드(line 282-297) — `featured_testimonial`과 중복되는 post 1개 skip하는 if 절 추가
  - 다른 섹션(4 Pillar, Match Wizard CTA, How it works, Bottom CTA)은 변경 없음
- `app/services/feed.py`의 `HomeData`에 `featured_testimonial: Post | None` 필드 추가
- `app/services/feed.py`의 `home_data()` — 기존 `popular_reviews` 첫 항목을 `featured_testimonial`로 노출(추가 쿼리 없음)
- 인용 본문 추출 helper — Jinja filter 또는 service 내 utility (`first_paragraph_excerpt(body, max_chars=120)`)
- `app/templates/pages/home.html`에 PostHog 이벤트 emit placeholder 주석 4개:
  - `landing_hero_view`
  - `landing_persona_select` (3 카드)
  - `landing_cta_kakao_click`
  - `landing_cta_signup_click`
- 단위 테스트:
  - `home_data().featured_testimonial`이 `popular_reviews[0]`과 일치
  - 발행된 review 0개일 때 `featured_testimonial = None`
  - excerpt helper — 빈 문자열·짧은 문자열·긴 문자열·markdown image 라인이 첫 paragraph인 경우 모두 안전

### 2.2 Out of scope

- 로그인 사용자 홈([home.html:5-136](../../app/templates/pages/home.html#L5-L136)) 수정
- 4 Pillar 섹션·Match Wizard CTA·인기 후기·How it works·Bottom CTA 카피 수정
- PostHog 실제 호출 통합 (OI-14 P1.5에서 [2026-05-09-nestory-p15c-posthog-design.md](2026-05-09-nestory-p15c-posthog-design.md) 따름)
- 회전형 인용 위젯 또는 다중 인용 grid
- Region별 인용 큐레이션 (현재는 popular_reviews 전체에서 첫 항목)
- A/B 테스트 인프라 (P2 이후)
- hero 배경 이미지·일러스트 (gradient + 이모지로 충분)
- 모바일 전용 별도 카피 (responsive로 같은 카피 사용)

## 3. 신규 hero 섹션 구조

### 3.1 시각적 레이아웃 (mobile-first)

```
┌──────────────────────────────────────────────────┐
│  (rounded-xl, emerald gradient bg, py-12 sm:py-16)│
│                                                  │
│   "1년차에 좋다는 후기는 많아도,                    │
│    3년차의 진실은 어디서 듣나요?"                    │
│                                                  │
│   같은 사람의 1년차→3년차 회고로                     │
│   가짜 후기 없이 정착의 진실을 봅니다.                │
│                                                  │
│   ╭─ featured_testimonial 카드 (조건부 렌더) ──╮    │
│   │ "5년 살아보니 후회 비용이 보이네요.       │    │
│   │  1. 단열 (북측 벽 보강): 약 800만원       │    │
│   │  2. 화목난로 굴뚝 위치 잘못: 재시공…"      │    │
│   │  — 양평 5년차 @alice_yp · 후기 보기 →     │    │
│   ╰────────────────────────────────────────╯    │
│                                                  │
│   당신은 어떤 분이신가요?                         │
│   ┌────────┬────────┬────────┐                  │
│   │🔍 예비  │🏡 1-3년 │🌳 5년+│                  │
│   │입주자  │차 거주자│ 베테랑 │                  │
│   │→ 지역  │→ 가입+ │→ Journey│                  │
│   │  매칭  │  후기  │ 연재   │                  │
│   └────────┴────────┴────────┘                  │
│                                                  │
│   [💬 카카오로 1초 시작]                          │
│   이메일로 가입 · 이미? 로그인                     │
└──────────────────────────────────────────────────┘
```

### 3.2 카피 (확정)

| 요소 | 카피 |
|---|---|
| H1 | `1년차에 좋다는 후기는 많아도,` (block) ` 3년차의 진실은 어디서 듣나요?` (block sm:inline) |
| 서브 | `같은 사람의 1년차 → 3년차 회고로 가짜 후기 없이 정착의 진실을 봅니다.` |
| 인용 카드 헤더 | (없음 — 인용 자체가 본문) |
| 인용 attribution | `— {region.sigungu} {거주_연차_label} @{author.username} · 후기 보기 →` |
| 페르소나 H3 | `당신은 어떤 분이신가요?` |
| 카드 1 (예비 입주자) | 제목 `🔍 예비 입주자` · 본문 `정착 검토 중이신가요?` · CTA `→ 5문항 매칭` · 링크 `/match/wizard` |
| 카드 2 (1-3년차) | 제목 `🏡 1-3년차 거주자` · 본문 `겪은 일을 데이터로` · CTA `→ 가입하고 후기 남기기` · 링크 `/auth/signup` |
| 카드 3 (5년+) | 제목 `🌳 5년+ 베테랑` · 본문 `정착 전 과정 아카이빙` · CTA `→ Journey 연재` · 링크 `/auth/signup` |
| 1차 CTA | `💬 카카오로 1초 시작` → `/auth/kakao/start` (yellow-300 버튼, 큼) |
| 2차 액션 | 텍스트 링크 `이메일로 가입` (`/auth/signup`) · `이미 계정이 있으신가요? 로그인` (`/auth/login`) |

### 3.3 H1 디자인 결정 사항

- 줄바꿈은 `<span class="block">` + `<span class="block sm:inline">` 패턴(현 코드의 break-keep 흐름과 동일)
- 의문형 종결 — 흥미 유발. 단언형보다 클릭률 가설 우위.
- "1년차/3년차" 숫자 — PRD T축의 가장 구체적 표현. 추상어("시간이 지나도", "장기적으로") 사용 금지.

### 3.4 Featured testimonial 카드 — 데이터·렌더링 규칙

- `data.featured_testimonial` 존재 시에만 렌더(`{% if data.featured_testimonial %}`)
- 본문 추출 — `excerpt(body, max_chars=140)` filter:
  - markdown image-only paragraph(`![]...`로만 구성된 줄들)는 건너뜀
  - 나머지 paragraph들을 공백 1칸으로 join → 단일 텍스트 stream
  - markdown bold(`**X**`) → `X`, heading(`# X`) → `X` 정도만 단순 strip
  - max_chars 초과 시 `[:max_chars].rstrip() + "…"`
  - 빈 결과면 → testimonial 카드 자체 숨김
- 이렇게 하면 시드 alice_yp 후기("5년 살아보니 후회 비용이 보이네요.\n\n1. 단열 (북측 벽 보강): 약 800만원\n2. 화목난로 굴뚝 위치 잘못: 재시공 220만원...")가 hero에서 "5년 살아보니 후회 비용이 보이네요. 1. 단열 (북측 벽 보강): 약 800만원 2. 화목난로 굴뚝 위치 잘못: 재시공 220만원…" 형태로 노출 — T·C축 동시 전달
- attribution `거주_연차_label`:
  - `author.resident_verified_at` 있으면 `(now - resident_verified_at).days // 365` → `"{n}년차"` (0년차는 "1년차로 표시" — UI상 N+1 표기)
  - 없으면 빈 문자열 + 점 구분자 생략
- 카드 클릭 → `/p/{post.slug}` (Post detail) 이동
- 추가 쿼리 0 — `popular_reviews[0]` 재사용

### 3.5 페르소나 카드 — 행동 분기

| 카드 | 클릭 | 의도 | 기존 위치에서의 변화 |
|---|---|---|---|
| 예비 입주자 | `/match/wizard` | 즉시 가치 제공(비로그인 가능) → 전환 우위 | 기존: 카드만 표시, 클릭 X. 신규: 클릭 시 wizard 진입 |
| 1-3년차 | `/auth/signup` | 후기 작성 권한 = 거주자 배지 = 가입 필수 | 신규: 클릭 시 가입 페이지 |
| 5년+ | `/auth/signup` | Journey 연재 = 거주자 배지 필요 = 가입 필수 | 신규: 클릭 시 가입 페이지 |

페르소나 카드 클릭은 곧 `landing_persona_select` 이벤트(P1.5 PostHog) 트리거 — `persona` property로 분기 측정.

### 3.6 CTA 위계 — 1개로 단순화 이유

현재 hero는 카카오·이메일 2개를 동등 노출. 결정 피로도. 카카오를 1차로 명확히 두고 이메일을 2차 텍스트 링크로 강등:

- 카카오 OAuth는 가입 + 인증 + 첫 진입을 1회로 압축 (PRD 시니어 친화)
- 이메일 가입은 폼 1단계 더 — 이탈 가능성 ↑
- 둘 다 큰 버튼이면 시각 위계 무너짐

## 4. 코드 변경 상세

### 4.1 `app/services/feed.py`

```python
@dataclass
class HomeData:
    recommended_regions: list[Region]
    popular_reviews: list[Post]
    recent_journeys: list[Post]
    followed_episodes: list[Post]
    featured_testimonial: Post | None  # 신규


def home_data(db: Session, user: User | None) -> HomeData:
    # ... 기존 popular_reviews 쿼리 그대로 ...
    return HomeData(
        recommended_regions=regions,
        popular_reviews=popular_reviews,
        recent_journeys=recent_journeys,
        followed_episodes=followed_episodes,
        featured_testimonial=popular_reviews[0] if popular_reviews else None,
    )
```

선택 단순화: 별도 큐레이션 쿼리 X. `popular_reviews` 정렬이 바뀌면(좋아요 수 증가 등) 자동 갱신. 큐레이션 정교화는 P2 — featured 별도 큐레이션 정책 도입 시점에.

**중복 처리** — 같은 post가 hero 인용 카드와 기존 "인기 후기" 그리드(line 282-297) 양쪽에 노출되는 것을 방지하기 위해, "인기 후기" 그리드는 `data.featured_testimonial`이 있을 경우 첫 항목을 건너뜀:

```jinja
{# 변경: line 289 직전 #}
{% for post in data.popular_reviews if not (data.featured_testimonial and post.id == data.featured_testimonial.id) %}
  {% include "partials/post_card.html" %}
{% endfor %}
```

또는 동등하게 `data.popular_reviews[1:]` (featured는 항상 [0]이라는 보장이 있을 때). `if not ... id ==` 형태가 견고함 (큐레이션 정책이 P2에 변할 때 안전).

### 4.2 인용 본문 excerpt helper

위치: `app/templating.py`에 Jinja filter로 등록 (가장 단순). 또는 `app/services/feed.py` 내부 utility (template에서 직접 호출 X). **결정: Jinja filter** — template-pure operation이고 다른 곳(추후 search snippet 등)에서도 재사용 가능.

```python
# app/templating.py
import re

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_HEADING_RE = re.compile(r"^#+\s+", flags=re.MULTILINE)


def _is_image_only_paragraph(paragraph: str) -> bool:
    lines = [ln.strip() for ln in paragraph.splitlines() if ln.strip()]
    return bool(lines) and all(ln.startswith("![") for ln in lines)


def excerpt(body: str | None, max_chars: int = 140) -> str:
    """Strip image paragraphs + light markdown, join with space, truncate."""
    if not body:
        return ""
    chunks: list[str] = []
    for paragraph in body.split("\n\n"):
        stripped = paragraph.strip()
        if not stripped or _is_image_only_paragraph(stripped):
            continue
        # markdown 단순 strip
        cleaned = _HEADING_RE.sub("", stripped)
        cleaned = _BOLD_RE.sub(r"\1", cleaned)
        # 줄바꿈을 공백으로(목록 번호 같은 구조 보존)
        cleaned = " ".join(line.strip() for line in cleaned.splitlines() if line.strip())
        chunks.append(cleaned)
    text = " ".join(chunks)
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "…"
    return text


env.filters["excerpt"] = excerpt
```

template 사용:

```jinja
{{ data.featured_testimonial.body | excerpt(140) }}
```

### 4.3 거주 연차 helper

위치: 동일 `app/templating.py`. `resident_verified_at`가 None인 경우 빈 문자열 반환.

```python
def resident_year_label(verified_at: datetime | None) -> str:
    if verified_at is None:
        return ""
    days = (datetime.now(UTC) - verified_at).days
    years = max(1, days // 365)  # 0년차는 1년차로 표시
    return f"{years}년차"

env.filters["resident_year"] = resident_year_label
```

### 4.4 `app/templates/pages/home.html` 변경

- line 140-164(현 hero) 전체 교체
- line 210-241(페르소나 섹션) 전체 삭제
- line 289 `{% for post in data.popular_reviews %}` → 위 4.1의 if-skip 절로 교체
- 다른 섹션 변경 없음

신규 hero 마크업 골격 (정확한 Tailwind 클래스는 implementation 시점에 확정):

```jinja
{# 1. Hero — 통합 개편 #}
<section class="rounded-2xl bg-gradient-to-br from-emerald-50 via-white to-emerald-50 px-4 sm:px-8 py-12 sm:py-16">
  <h1 class="text-3xl sm:text-5xl font-bold text-stone-900 leading-tight tracking-tight break-keep text-center">
    <span class="block">1년차에 좋다는 후기는 많아도,</span>
    <span class="block sm:inline">3년차의 진실은 어디서 듣나요?</span>
  </h1>
  <p class="mt-6 text-base sm:text-lg text-stone-600 max-w-xl mx-auto text-center">
    같은 사람의 1년차 → 3년차 회고로<br>
    가짜 후기 없이 정착의 진실을 봅니다.
  </p>

  {# Featured testimonial — 조건부 렌더 #}
  {% if data.featured_testimonial %}
    {% set t = data.featured_testimonial %}
    <a href="/p/{{ t.slug }}"
       class="block mt-8 mx-auto max-w-2xl rounded-xl border border-emerald-200 bg-white/80 backdrop-blur p-5 sm:p-6 hover:border-emerald-300 hover:shadow-sm transition"
       {# TODO(P1.5 PostHog): emit landing_testimonial_click {post_id: t.id} #}>
      <p class="text-stone-800 leading-relaxed">
        "{{ t.body | excerpt(120) }}"
      </p>
      <p class="mt-3 text-sm text-stone-500">
        — {{ t.region.sigungu }}
        {% set _yl = t.author.resident_verified_at | resident_year %}
        {% if _yl %} {{ _yl }}{% endif %}
        @{{ t.author.username }} · 후기 보기 →
      </p>
    </a>
  {% endif %}

  {# 페르소나 자가선택 — hero 통합 #}
  <div class="mt-10">
    <h2 class="text-lg sm:text-xl font-semibold text-stone-900 text-center mb-4">
      당신은 어떤 분이신가요?
    </h2>
    <div class="grid gap-3 sm:grid-cols-3 max-w-3xl mx-auto">
      <a href="/match/wizard" {# TODO(P1.5 PostHog): landing_persona_select {persona: "considering"} #}
         class="rounded-lg border border-emerald-200 bg-white p-4 hover:border-emerald-400 hover:shadow-sm transition">
        <span class="inline-flex h-9 w-9 items-center justify-center rounded-md bg-emerald-50 text-emerald-700">{{ icon("search", 18) }}</span>
        <h3 class="mt-2 font-bold text-stone-900">예비 입주자</h3>
        <p class="mt-1 text-sm text-stone-600">정착 검토 중이신가요?</p>
        <p class="mt-2 text-sm font-medium text-emerald-700">→ 5문항 매칭</p>
      </a>
      <a href="/auth/signup" {# TODO(P1.5 PostHog): landing_persona_select {persona: "early_resident"} #}
         class="rounded-lg border border-emerald-200 bg-white p-4 hover:border-emerald-400 hover:shadow-sm transition">
        <span class="inline-flex h-9 w-9 items-center justify-center rounded-md bg-emerald-50 text-emerald-700">{{ icon("home", 18) }}</span>
        <h3 class="mt-2 font-bold text-stone-900">1-3년차 거주자</h3>
        <p class="mt-1 text-sm text-stone-600">겪은 일을 데이터로</p>
        <p class="mt-2 text-sm font-medium text-emerald-700">→ 가입하고 후기 남기기</p>
      </a>
      <a href="/auth/signup" {# TODO(P1.5 PostHog): landing_persona_select {persona: "veteran"} #}
         class="rounded-lg border border-emerald-200 bg-white p-4 hover:border-emerald-400 hover:shadow-sm transition">
        <span class="inline-flex h-9 w-9 items-center justify-center rounded-md bg-emerald-50 text-emerald-700">{{ icon("trees", 18) }}</span>
        <h3 class="mt-2 font-bold text-stone-900">5년+ 베테랑</h3>
        <p class="mt-1 text-sm text-stone-600">정착 전 과정 아카이빙</p>
        <p class="mt-2 text-sm font-medium text-emerald-700">→ Journey 연재</p>
      </a>
    </div>
  </div>

  {# 1차 CTA — 카카오 single. 이메일은 텍스트 링크로 강등 #}
  <div class="mt-10 flex flex-col items-center gap-3">
    <a href="/auth/kakao/start"
       {# TODO(P1.5 PostHog): landing_cta_kakao_click #}
       class="inline-flex items-center justify-center gap-2 rounded-md bg-yellow-300 px-8 py-3 text-base font-semibold text-stone-900 hover:bg-yellow-400">
      {{ icon("message-circle", 20) }}카카오로 1초 시작
    </a>
    <p class="text-sm text-stone-500">
      <a href="/auth/signup" class="text-emerald-700 hover:underline" {# TODO PostHog: landing_cta_signup_click #}>이메일로 가입</a>
      ·
      이미 계정이 있으신가요?
      <a href="/auth/login" class="text-emerald-700 hover:underline">로그인</a>
    </p>
  </div>
</section>
```

### 4.5 페르소나 섹션 삭제 (line 210-241)

기존 `<section class="py-12 border-t border-stone-200">` 페르소나 블록을 통째 삭제. hero 안에서 더 짧고 액션 가능한 형태로 흡수했기 때문.

## 5. PostHog 이벤트 (P1.5 placeholder)

본 spec은 코드 emit 미포함. template에 다음 4개 이벤트 발생 위치를 `{# TODO(P1.5 PostHog): event_name {prop: value} #}` 주석으로 표시:

| Event name | 발생 위치 | Properties |
|---|---|---|
| `landing_hero_view` | hero section render(SSR 시점 — JS scroll observer로 P1.5에서 측정) | `has_testimonial: bool` |
| `landing_persona_select` | 페르소나 카드 3개 click | `persona: "considering" \| "early_resident" \| "veteran"` |
| `landing_cta_kakao_click` | 1차 CTA click | (없음) |
| `landing_cta_signup_click` | 2차 텍스트 링크 click | (없음) |

P1.5 PostHog 통합 spec([2026-05-09-nestory-p15c-posthog-design.md](2026-05-09-nestory-p15c-posthog-design.md)) 진행 시 이 주석을 grep으로 일괄 추출 → `EventName` enum 추가 → emit 코드 삽입.

## 6. 테스트 전략

| Test file | Verifies |
|---|---|
| `test_feed_service.py` (기존 확장) | `home_data().featured_testimonial == popular_reviews[0]` 일치 / popular_reviews 비었을 때 None |
| `test_templating_filters.py` (신규) | `excerpt(body, n)` — 빈 / 짧은(<n) / 긴(>n, "…" 절단) / image-only paragraph 단독 / image + 텍스트 혼합 / `**bold**`·heading 포함 / 시드 alice_yp 후기 round-trip 6+케이스 |
| `test_templating_filters.py` (이어서) | `resident_year(verified_at)` — None / 0일 / 365일 / 730일 / 미래 시각 5케이스 |
| `test_pages_home.py` (기존 확장 또는 신규) | 비로그인 GET `/` 200 + h1에 "3년차의 진실" 텍스트 포함 + featured_testimonial 시드 시 hero 카드 렌더 + 동일 post가 "인기 후기" 그리드에 중복 노출되지 않음 + 페르소나 3 카드 href 정확 |

테스트 데이터는 factory-boy 우선:
- `PostFactory(type=PostType.REVIEW, status=PostStatus.PUBLISHED, body="...")` — popular_reviews 쿼리에 잡히도록 `published_at` 설정
- `UserFactory(resident_verified_at=...)` — 거주 연차 검증

## 7. DoD

- 비로그인 `/` 접속 시 신규 hero 정상 렌더 (브라우저 manual QA)
- featured_testimonial 있을 때 인용 카드 렌더, 없을 때 카드 없이 정상 200
- featured_testimonial 있을 때 "인기 후기" 그리드에서 동일 post 중복 미노출
- 페르소나 3카드 클릭 → 각각 `/match/wizard`, `/auth/signup`, `/auth/signup` 정상 이동
- 카카오 CTA 클릭 → `/auth/kakao/start` 정상 이동
- 모바일(SM 미만)·태블릿(SM~MD)·데스크톱(MD+) 3 뷰포트에서 카피 줄바꿈·간격 자연스러움
- 페르소나 섹션(line 210-241) 삭제 후 페이지 다른 섹션과 시각 단절 없음(top border 정리)
- 4개 PostHog placeholder 주석이 신규 코드에 포함됨 (P1.5에서 grep 추출 가능)
- pytest 회귀 0 (현재 baseline pass 유지)
- ruff lint clean

## 8. 마이그레이션 / 롤백

- DB 마이그레이션 없음
- 코드 롤백 = git revert 1 commit으로 복원 가능
- 기능 플래그 불필요 (시각 변경만, 신규 의존성 없음)

## 9. 구현 task 추정

3-5 task. 대략적 분해:

1. `feed.py` HomeData/home_data — `featured_testimonial` 필드 추가 + 단위 테스트
2. `app/templating.py` excerpt + resident_year Jinja filter 등록 + 단위 테스트
3. `home.html` 비로그인 hero 섹션 교체 + 페르소나 섹션 삭제
4. `test_pages_home.py` 비로그인 hero 통합 테스트 1-2개 추가
5. 브라우저 manual QA (3 뷰포트) + 카피 미세 조정

총 예상 시간: 2-3시간 (테스트·QA 포함).

## 10. Open Questions (구현 진입 전 결정 필요)

| 항목 | 옵션 | 권고 |
|---|---|---|
| H1 의문형 종결 — "?"가 시니어에게 너무 캐주얼한가? | (a) 현 카피 유지 / (b) 단언형 "1년차에 좋다고 했던 사람의 3년차 회고를 봅니다" | **(a) 유지** — A/B 측정 가치. 현 단계엔 hypothesis 우위. |
| 페르소나 카드 클릭 시 `?from=hero_persona=X` 쿼리 추가 여부 | (a) 추가 / (b) 미추가 (PostHog가 referrer로 추적) | **(b) 미추가** — URL 오염 방지, PostHog가 발생 페이지로 충분. |
| Hero 그라디언트 색상 — emerald 단색? warm tone 추가? | (a) emerald gradient 유지(현 코드 톤) / (b) emerald + amber gradient (자연·따뜻함) | **(a) 유지** — 디자인 시스템 일관성, 광범위 변경 회피. |
| Featured testimonial이 사용자 본인 글일 경우(로그인 후) — 다른 글로 대체? | (a) 그대로 노출 / (b) 다른 글로 fallback | **N/A** — hero는 비로그인만 렌더. |

위 4개 항목 모두 권고대로 진행하면 별도 결정 회의 불필요.

---

**다음 단계**: 본 spec 사용자 승인 후 `superpowers:writing-plans` 스킬로 implementation plan 작성 → `subagent-driven-development`로 실행.
