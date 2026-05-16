# Landing Hero Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 비로그인 방문자용 랜딩 페이지 hero 섹션을 PRD T축(시계열 회고) 직접 노출 + featured testimonial 인용 + 페르소나 자가선택 통합 구조로 교체. 데이터 모델 변경 없이 service 1 필드 + Jinja filter 2개 + template 수정으로 구현.

**Architecture:** `HomeData.featured_testimonial`을 기존 `popular_reviews[0]`에서 파생(추가 쿼리 0). Jinja filter `excerpt`(본문 발췌)·`resident_year`(거주 연차 라벨) 2개를 `app/templating_filters.py`에 추가하고 `app/templating.py`에서 등록. `home.html` 비로그인 분기 hero 마크업 교체 + 기존 페르소나 섹션 삭제 + "인기 후기" 그리드에서 featured 중복 skip.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLAlchemy 2.x, pytest + factory-boy. PostgreSQL 16 (host port 5433). 변경 없는 인프라.

**관련 spec**: [docs/superpowers/specs/2026-05-13-nestory-landing-hero-redesign-design.md](../specs/2026-05-13-nestory-landing-hero-redesign-design.md)

---

## File Structure

| 파일 | 동작 | 책임 |
|---|---|---|
| `app/templating_filters.py` | Modify | `excerpt(body, max_chars)` + `resident_year(verified_at)` 추가 |
| `app/templating.py` | Modify | 두 filter 등록 (`templates.env.filters[...] = ...`) |
| `app/services/feed.py` | Modify | `HomeData.featured_testimonial: Post \| None` 필드 + `home_data()`에서 채우기 |
| `app/templates/pages/home.html` | Modify | 비로그인 분기 hero 교체 (line 140-164) + 페르소나 섹션 삭제 (line 211-241) + "인기 후기" 그리드 skip-if 추가 (line 289 부근) |
| `app/tests/unit/test_excerpt_filter.py` | Create | excerpt filter 단위 테스트 (Postgres 불필요) |
| `app/tests/unit/test_resident_year_filter.py` | Create | resident_year filter 단위 테스트 (Postgres 불필요) |
| `app/tests/integration/test_feed_service.py` | Modify | `featured_testimonial` 검증 테스트 2개 추가 |
| `app/tests/integration/test_pages.py` | Modify | 비로그인 hero 통합 테스트 4개 추가 |

**spec과의 deviation (실제 코드베이스 패턴에 맞춘 조정)**:
- spec §4.2/4.3은 "app/templating.py"에 filter 작성으로 표기 → **실제는 `app/templating_filters.py`에 구현 + `app/templating.py`에서 등록**(현 코드베이스 패턴, [templating_filters.py:54](../../app/templating_filters.py#L54)와 [templating.py:10-12](../../app/templating.py#L10-L12) 참조).
- spec §3.4 testimonial 클릭 URL은 `/p/{post.slug}`로 표기 → **Post 모델에 slug 컬럼 없음** (`grep slug app/models/post.py` → no match). 실제 detail URL은 [content.py:195](../../app/routers/content.py#L195) `/post/{id}`이므로 plan은 `/post/{t.id}`를 사용.
- 신규 filter 테스트 파일명은 [test_markdown_filter.py](../../app/tests/unit/test_markdown_filter.py) 명명 규약 따라 `test_<filter>_filter.py` 분리.

---

## Pre-flight: 환경 점검

- [ ] **Step 1: Postgres 컨테이너 가동 확인**

Run: `docker compose -f docker-compose.local.yml ps`
Expected: `nestory-postgres-local` 상태 `Up`. 아니면 `docker compose -f docker-compose.local.yml up -d` 후 `uv run alembic upgrade head`.

- [ ] **Step 2: 베이스라인 테스트 통과 확인**

Run: `uv run pytest app/tests/ -q`
Expected: 모두 PASS (회귀 baseline 확보). 실패 테스트가 있으면 본 plan과 무관해도 먼저 보고.

- [ ] **Step 3: 현재 브랜치 확인**

Run: `git status --short && git branch --show-current`
Expected: branch `dev` (또는 사용자가 지정한 작업 브랜치). uncommitted 변경은 user의 in-progress이므로 건드리지 말 것.

---

## Task 1: `excerpt` Jinja filter 구현 (TDD)

**Files:**
- Create: `app/tests/unit/test_excerpt_filter.py`
- Modify: `app/templating_filters.py`
- Modify: `app/templating.py`

- [ ] **Step 1: Write the failing tests**

신규 파일 `app/tests/unit/test_excerpt_filter.py`:

```python
"""Tests for excerpt Jinja filter."""
from app.templating_filters import excerpt


def test_excerpt_returns_empty_for_none():
    assert excerpt(None) == ""


def test_excerpt_returns_empty_for_empty_string():
    assert excerpt("") == ""


def test_excerpt_returns_short_body_unchanged():
    assert excerpt("짧은 본문", 140) == "짧은 본문"


def test_excerpt_truncates_long_body_with_ellipsis():
    body = "가" * 200
    out = excerpt(body, 140)
    assert out.endswith("…")
    assert len(out) == 141  # 140 chars + "…"


def test_excerpt_skips_image_only_paragraphs():
    body = "![](/img/1/orig)\n\n실제 본문입니다."
    assert excerpt(body) == "실제 본문입니다."


def test_excerpt_keeps_paragraph_with_text_and_inline_image():
    body = "텍스트와 ![](/img/1/orig) 이미지가 섞임"
    out = excerpt(body)
    # image-only 가 아니므로 paragraph 전체 보존
    assert "텍스트와" in out
    assert "이미지가 섞임" in out


def test_excerpt_joins_multiple_paragraphs_with_space():
    body = "첫 단락.\n\n둘째 단락."
    assert excerpt(body) == "첫 단락. 둘째 단락."


def test_excerpt_strips_bold_markers():
    body = "**의외로 좋은 점**\n\n동네 카페 사장님과 친해짐"
    out = excerpt(body)
    assert "**" not in out
    assert "의외로 좋은 점" in out
    assert "동네 카페 사장님과 친해짐" in out


def test_excerpt_strips_heading_markers():
    body = "# 제목\n\n본문 내용"
    out = excerpt(body)
    assert "#" not in out
    assert "제목" in out
    assert "본문 내용" in out


def test_excerpt_alice_yp_seed_review_round_trip():
    """시드 데이터 alice_yp 5년차 후기 — T·C축 데이터가 hero 인용에 모두 노출되는지."""
    body = (
        "5년 살아보니 후회 비용이 보이네요.\n\n"
        "1. 단열 (북측 벽 보강): 약 800만원\n"
        "2. 화목난로 굴뚝 위치 잘못: 재시공 220만원\n"
        "3. 진입로 콘크리트 두께 부족: 보수 150만원\n\n"
        "이 셋만 처음에 잘했어도 천만원 가까이 아꼈을 거예요."
    )
    out = excerpt(body, 140)
    assert "5년 살아보니" in out  # T축 (시간) 노출
    assert "단열" in out  # C축 (후회비용) 노출
    assert "800만원" in out  # 구체적 금액 노출


def test_excerpt_returns_empty_when_only_images():
    body = "![](/img/1/orig)\n\n![](/img/2/orig)"
    assert excerpt(body) == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/unit/test_excerpt_filter.py -v`
Expected: 11개 모두 `ImportError: cannot import name 'excerpt' from 'app.templating_filters'` 또는 동등 메시지로 FAIL.

- [ ] **Step 3: Implement the filter**

`app/templating_filters.py` 상단 import 추가:

```python
"""Jinja filters for templates."""
import html as _html
import re
```

(기존과 동일 — 이미 `re` import 됨. 추가 변경 없음.)

같은 파일 하단(기존 `__all__` 직전)에 신규 함수 추가:

```python
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_HEADING_RE = re.compile(r"^#+\s+", flags=re.MULTILINE)


def _is_image_only_paragraph(paragraph: str) -> bool:
    lines = [ln.strip() for ln in paragraph.splitlines() if ln.strip()]
    return bool(lines) and all(ln.startswith("![") for ln in lines)


def excerpt(body: str | None, max_chars: int = 140) -> str:
    """Strip image-only paragraphs + light markdown, join with space, truncate."""
    if not body:
        return ""
    chunks: list[str] = []
    for paragraph in body.split("\n\n"):
        stripped = paragraph.strip()
        if not stripped or _is_image_only_paragraph(stripped):
            continue
        cleaned = _HEADING_RE.sub("", stripped)
        cleaned = _BOLD_RE.sub(r"\1", cleaned)
        cleaned = " ".join(line.strip() for line in cleaned.splitlines() if line.strip())
        chunks.append(cleaned)
    text = " ".join(chunks)
    if len(text) > max_chars:
        return text[:max_chars].rstrip() + "…"
    return text
```

`__all__` 갱신:

```python
__all__ = ["excerpt", "first_image_url", "markdown_to_html", "strip_markdown_images"]
```

- [ ] **Step 4: Register filter in `app/templating.py`**

기존 import 라인을 확장:

```python
from app.templating_filters import (
    excerpt,
    first_image_url,
    markdown_to_html,
    strip_markdown_images,
)
```

filter 등록 라인 추가 (기존 `templates.env.filters[...]` 줄들 옆):

```python
templates.env.filters["markdown"] = markdown_to_html
templates.env.filters["first_image_url"] = first_image_url
templates.env.filters["strip_md_images"] = strip_markdown_images
templates.env.filters["excerpt"] = excerpt
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest app/tests/unit/test_excerpt_filter.py -v`
Expected: 11개 모두 PASS.

- [ ] **Step 6: Lint**

Run: `uv run ruff check app/templating_filters.py app/templating.py app/tests/unit/test_excerpt_filter.py`
Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
git add app/templating_filters.py app/templating.py app/tests/unit/test_excerpt_filter.py
git commit -m "feat(templating): add excerpt Jinja filter for testimonial preview"
```

---

## Task 2: `resident_year` Jinja filter 구현 (TDD)

**Files:**
- Create: `app/tests/unit/test_resident_year_filter.py`
- Modify: `app/templating_filters.py`
- Modify: `app/templating.py`

- [ ] **Step 1: Write the failing tests**

신규 파일 `app/tests/unit/test_resident_year_filter.py`:

```python
"""Tests for resident_year Jinja filter."""
from datetime import UTC, datetime, timedelta

from app.templating_filters import resident_year


def test_resident_year_returns_empty_for_none():
    assert resident_year(None) == ""


def test_resident_year_returns_1nyeoncha_for_recently_verified():
    """0일 ~ 364일 = 1년차 (max(1, ...) clamp)."""
    now = datetime.now(UTC)
    assert resident_year(now) == "1년차"
    assert resident_year(now - timedelta(days=10)) == "1년차"
    assert resident_year(now - timedelta(days=200)) == "1년차"


def test_resident_year_returns_1nyeoncha_at_exactly_one_year():
    """365일 = 1년차 (365 // 365 = 1)."""
    now = datetime.now(UTC)
    assert resident_year(now - timedelta(days=365)) == "1년차"


def test_resident_year_returns_2nyeoncha_at_two_years():
    now = datetime.now(UTC)
    assert resident_year(now - timedelta(days=365 * 2)) == "2년차"


def test_resident_year_returns_5nyeoncha_at_five_years():
    now = datetime.now(UTC)
    assert resident_year(now - timedelta(days=365 * 5)) == "5년차"


def test_resident_year_handles_future_timestamp_as_1nyeoncha():
    """미래 시각(데이터 오류)은 음수 days → max(1, ...)로 1년차로 clamp."""
    now = datetime.now(UTC)
    assert resident_year(now + timedelta(days=30)) == "1년차"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/unit/test_resident_year_filter.py -v`
Expected: 6개 모두 `ImportError: cannot import name 'resident_year'` FAIL.

- [ ] **Step 3: Implement the filter**

`app/templating_filters.py` 파일 상단 import 영역에 추가:

```python
from datetime import UTC, datetime
```

같은 파일 하단(이전 task에서 추가한 `excerpt` 아래)에 함수 추가:

```python
def resident_year(verified_at: datetime | None) -> str:
    """Return '{N}년차' label, or '' when verified_at is None.

    0년차도 1년차로 표시 (UI 친화), 미래 시각은 1년차로 clamp.
    """
    if verified_at is None:
        return ""
    days = (datetime.now(UTC) - verified_at).days
    years = max(1, days // 365)
    return f"{years}년차"
```

`__all__` 갱신:

```python
__all__ = ["excerpt", "first_image_url", "markdown_to_html", "resident_year", "strip_markdown_images"]
```

- [ ] **Step 4: Register filter in `app/templating.py`**

기존 import 확장:

```python
from app.templating_filters import (
    excerpt,
    first_image_url,
    markdown_to_html,
    resident_year,
    strip_markdown_images,
)
```

filter 등록 라인 추가:

```python
templates.env.filters["resident_year"] = resident_year
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest app/tests/unit/test_resident_year_filter.py -v`
Expected: 6개 모두 PASS.

- [ ] **Step 6: Re-run excerpt tests to confirm no regression**

Run: `uv run pytest app/tests/unit/test_excerpt_filter.py app/tests/unit/test_resident_year_filter.py -v`
Expected: 17개 모두 PASS.

- [ ] **Step 7: Lint**

Run: `uv run ruff check app/templating_filters.py app/templating.py app/tests/unit/test_resident_year_filter.py`
Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
git add app/templating_filters.py app/templating.py app/tests/unit/test_resident_year_filter.py
git commit -m "feat(templating): add resident_year filter for testimonial attribution"
```

---

## Task 3: `HomeData.featured_testimonial` 필드 추가 (TDD)

**Files:**
- Modify: `app/services/feed.py`
- Modify: `app/tests/integration/test_feed_service.py`

- [ ] **Step 1: Write the failing tests**

`app/tests/integration/test_feed_service.py` 파일 끝에 추가:

```python
# ---------------------------------------------------------------------------
# 10. featured_testimonial — popular_reviews[0] 와 일치
# ---------------------------------------------------------------------------


def test_home_data_featured_testimonial_matches_popular_reviews_first(
    db: Session,
) -> None:
    """featured_testimonial은 popular_reviews[0] (가장 인기 review) 과 동일 instance."""
    region = RegionFactory(slug="feed-featured-match")
    _published_review(region, view_count=10)
    top = _published_review(region, view_count=999)
    _published_review(region, view_count=50)
    db.flush()

    data = feed_service.home_data(db, None)
    assert data.popular_reviews[0].id == top.id
    assert data.featured_testimonial is not None
    assert data.featured_testimonial.id == top.id


# ---------------------------------------------------------------------------
# 11. featured_testimonial — published review 0건이면 None
# ---------------------------------------------------------------------------


def test_home_data_featured_testimonial_none_when_no_reviews(db: Session) -> None:
    """published REVIEW가 하나도 없으면 featured_testimonial == None."""
    # 어떤 region·user도 추가하지 않음. _cleanup_db autouse fixture 가 비움.
    data = feed_service.home_data(db, None)
    assert data.popular_reviews == []
    assert data.featured_testimonial is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/integration/test_feed_service.py::test_home_data_featured_testimonial_matches_popular_reviews_first app/tests/integration/test_feed_service.py::test_home_data_featured_testimonial_none_when_no_reviews -v`
Expected: 2개 모두 `AttributeError: 'HomeData' object has no attribute 'featured_testimonial'` FAIL.

- [ ] **Step 3: Implement the field**

`app/services/feed.py` `HomeData` dataclass에 필드 추가:

```python
@dataclass
class HomeData:
    recommended_regions: list[Region]
    popular_reviews: list[Post]
    recent_journeys: list[Post]
    followed_episodes: list[Post]
    featured_testimonial: Post | None
```

같은 파일 `home_data()` 의 return 문 갱신:

```python
    return HomeData(
        recommended_regions=regions,
        popular_reviews=popular_reviews,
        recent_journeys=recent_journeys,
        followed_episodes=followed_episodes,
        featured_testimonial=popular_reviews[0] if popular_reviews else None,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest app/tests/integration/test_feed_service.py -v`
Expected: 모든 테스트 PASS (신규 2개 + 기존 9개).

- [ ] **Step 5: Lint**

Run: `uv run ruff check app/services/feed.py app/tests/integration/test_feed_service.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add app/services/feed.py app/tests/integration/test_feed_service.py
git commit -m "feat(feed): add featured_testimonial to HomeData (popular_reviews[0])"
```

---

## Task 4: `home.html` hero 섹션 교체 + 페르소나 흡수 + 인기후기 중복 skip

**Files:**
- Modify: `app/templates/pages/home.html`

본 task는 `home.html` 비로그인 분기에 3개 변경을 한 번에 적용. line 번호 의존을 피하기 위해 anchored Edit 사용.

- [ ] **Step 1: 현재 hero 섹션 교체** (Edit tool)

old_string (정확히 매치되는 hero 블록 전체):

```jinja
  {# 1. Hero #}
  <section class="text-center py-12 sm:py-16">
    <h1 class="text-3xl sm:text-5xl font-bold text-stone-900 leading-tight tracking-tight break-keep">
      <span class="block sm:inline">전원생활 정착의 여정,</span>
      <span class="block sm:inline">우리가 함께합니다</span>
    </h1>
    <p class="mt-6 text-base sm:text-lg text-stone-600 max-w-xl mx-auto">
      예비 입주자부터 1년차·3년차 거주자까지.<br>
      후기·Journey·Q&amp;A로 이어지는 신뢰 커뮤니티.
    </p>
    <div class="mt-8 flex flex-col sm:flex-row justify-center gap-3">
      <a href="/auth/kakao/start"
         class="inline-flex items-center justify-center gap-2 rounded-md bg-yellow-300 px-6 py-3 font-semibold text-stone-900 hover:bg-yellow-400">
        {{ icon("message-circle", 20) }}카카오로 1초 시작
      </a>
      <a href="/auth/signup"
         class="rounded-md bg-emerald-600 px-6 py-3 font-semibold text-white hover:bg-emerald-700">
        이메일로 가입
      </a>
    </div>
    <p class="mt-4 text-sm text-stone-500">
      이미 계정이 있으신가요?
      <a href="/auth/login" class="text-emerald-700 hover:underline">로그인</a>
    </p>
  </section>
```

new_string:

```jinja
  {# 1. Hero — T축(시계열) 직접 노출 + featured testimonial + 페르소나 통합 #}
  <section class="rounded-2xl bg-gradient-to-br from-emerald-50 via-white to-emerald-50 px-4 sm:px-8 py-12 sm:py-16">
    <h1 class="text-3xl sm:text-5xl font-bold text-stone-900 leading-tight tracking-tight break-keep text-center">
      <span class="block">1년차에 좋다는 후기는 많아도,</span>
      <span class="block sm:inline">3년차의 진실은 어디서 듣나요?</span>
    </h1>
    <p class="mt-6 text-base sm:text-lg text-stone-600 max-w-xl mx-auto text-center">
      같은 사람의 1년차 → 3년차 회고로<br>
      시간이 지나야 보이는 정착의 진짜 모습을 만나보세요.
    </p>

    {# Featured testimonial — popular_reviews[0] 가 있을 때만 #}
    {% if data.featured_testimonial %}
      {% set t = data.featured_testimonial %}
      {# TODO(P1.5 PostHog): emit landing_testimonial_click {post_id: t.id} on click #}
      <a href="/post/{{ t.id }}"
         class="block mt-8 mx-auto max-w-2xl rounded-xl border border-emerald-200 bg-white/80 backdrop-blur p-5 sm:p-6 hover:border-emerald-300 hover:shadow-sm transition">
        <p class="text-stone-800 leading-relaxed">
          "{{ t.body | excerpt(140) }}"
        </p>
        <p class="mt-3 text-sm text-stone-500">
          — {{ t.region.sigungu }}
          {% set _yl = t.author.resident_verified_at | resident_year %}
          {% if _yl %} {{ _yl }}{% endif %}
          @{{ t.author.username }} · 후기 보기 →
        </p>
      </a>
    {% endif %}

    {# 페르소나 자가선택 — 기존 하단 섹션을 hero 로 흡수 #}
    <div class="mt-10">
      <h2 class="text-lg sm:text-xl font-semibold text-stone-900 text-center mb-4">
        당신은 어떤 분이신가요?
      </h2>
      <div class="grid gap-3 sm:grid-cols-3 max-w-3xl mx-auto">
        {# TODO(P1.5 PostHog): landing_persona_select {persona: "considering"} on click #}
        <a href="/match/wizard"
           class="rounded-lg border border-emerald-200 bg-white p-4 hover:border-emerald-400 hover:shadow-sm transition">
          <span class="inline-flex h-9 w-9 items-center justify-center rounded-md bg-emerald-50 text-emerald-700">{{ icon("search", 18) }}</span>
          <h3 class="mt-2 font-bold text-stone-900">예비 입주자</h3>
          <p class="mt-1 text-sm text-stone-600">정착 검토 중이신가요?</p>
          <p class="mt-2 text-sm font-medium text-emerald-700">→ 5문항 매칭</p>
        </a>
        {# TODO(P1.5 PostHog): landing_persona_select {persona: "early_resident"} on click #}
        <a href="/auth/signup"
           class="rounded-lg border border-emerald-200 bg-white p-4 hover:border-emerald-400 hover:shadow-sm transition">
          <span class="inline-flex h-9 w-9 items-center justify-center rounded-md bg-emerald-50 text-emerald-700">{{ icon("home", 18) }}</span>
          <h3 class="mt-2 font-bold text-stone-900">1-3년차 거주자</h3>
          <p class="mt-1 text-sm text-stone-600">겪은 일을 데이터로</p>
          <p class="mt-2 text-sm font-medium text-emerald-700">→ 가입하고 후기 남기기</p>
        </a>
        {# TODO(P1.5 PostHog): landing_persona_select {persona: "veteran"} on click #}
        <a href="/auth/signup"
           class="rounded-lg border border-emerald-200 bg-white p-4 hover:border-emerald-400 hover:shadow-sm transition">
          <span class="inline-flex h-9 w-9 items-center justify-center rounded-md bg-emerald-50 text-emerald-700">{{ icon("trees", 18) }}</span>
          <h3 class="mt-2 font-bold text-stone-900">5년+ 베테랑</h3>
          <p class="mt-1 text-sm text-stone-600">정착 전 과정 아카이빙</p>
          <p class="mt-2 text-sm font-medium text-emerald-700">→ Journey 연재</p>
        </a>
      </div>
    </div>

    {# 1차 CTA = 카카오. 이메일은 보조 텍스트 링크로 강등. #}
    <div class="mt-10 flex flex-col items-center gap-3">
      {# TODO(P1.5 PostHog): landing_cta_kakao_click on click #}
      <a href="/auth/kakao/start"
         class="inline-flex items-center justify-center gap-2 rounded-md bg-yellow-300 px-8 py-3 text-base font-semibold text-stone-900 hover:bg-yellow-400">
        {{ icon("message-circle", 20) }}카카오로 1초 시작
      </a>
      <p class="text-sm text-stone-500">
        {# TODO(P1.5 PostHog): landing_cta_signup_click on click #}
        <a href="/auth/signup" class="text-emerald-700 hover:underline">이메일로 가입</a>
        ·
        이미 계정이 있으신가요?
        <a href="/auth/login" class="text-emerald-700 hover:underline">로그인</a>
      </p>
    </div>
  </section>
```

- [ ] **Step 2: 기존 페르소나 섹션 삭제** (Edit tool)

old_string:

```jinja
  {# 3. 페르소나 #}
  <section class="py-12 border-t border-stone-200">
    <h2 class="text-2xl font-bold text-center text-stone-900 mb-10">
      당신은 어떤 분이신가요?
    </h2>
    <div class="grid gap-4 sm:grid-cols-3">
      <div class="rounded-lg border border-emerald-100 bg-emerald-50 p-6">
        <span class="inline-flex h-10 w-10 items-center justify-center rounded-md bg-white text-emerald-700">{{ icon("search", 22) }}</span>
        <h3 class="mt-3 font-bold text-stone-900">예비 입주자</h3>
        <p class="mt-2 text-sm text-stone-700">
          정착을 검토 중이신가요? 먼저 도착한 분들의 후기로
          시군을 비교하고, "정착 계획"을 작성해 미리 조언을 받으세요.
        </p>
      </div>
      <div class="rounded-lg border border-emerald-100 bg-emerald-50 p-6">
        <span class="inline-flex h-10 w-10 items-center justify-center rounded-md bg-white text-emerald-700">{{ icon("home", 22) }}</span>
        <h3 class="mt-3 font-bold text-stone-900">1-3년차 거주자</h3>
        <p class="mt-2 text-sm text-stone-700">
          겪은 일을 데이터로 남기고, 후배 정착자의
          질문에 답하세요. 같은 지역 거주자가 당신을 검증합니다.
        </p>
      </div>
      <div class="rounded-lg border border-emerald-100 bg-emerald-50 p-6">
        <span class="inline-flex h-10 w-10 items-center justify-center rounded-md bg-white text-emerald-700">{{ icon("trees", 22) }}</span>
        <h3 class="mt-3 font-bold text-stone-900">5년+ 베테랑</h3>
        <p class="mt-2 text-sm text-stone-700">
          Journey 연재로 정착의 전 과정을 아카이빙하세요.
          지역의 멘토가 되어 후배에게 길을 알려주세요.
        </p>
      </div>
    </div>
  </section>

```

new_string (페르소나 섹션을 통째로 삭제 — 결과적으로 `{# 2. 4 Pillar #}` 의 `</section>` 직후 빈 줄 1개를 거쳐 `{# 3.5. Region Match Wizard CTA #}` 섹션이 이어짐):

```

```

(new_string은 빈 줄 1개. old_string의 마지막 `</section>\n` 다음의 빈 줄 1개를 보존해 `{# 2. 4 Pillar #}` 섹션 이후 자연 호흡 유지.)

- [ ] **Step 3: "인기 후기" 그리드에 featured 중복 skip 추가** (Edit tool)

old_string:

```jinja
    <div class="grid gap-4 sm:grid-cols-2">
      {% for post in data.popular_reviews %}
        {% include "partials/post_card.html" %}
      {% endfor %}
    </div>
    <div class="mt-6 text-center">
      <a href="/discover" class="text-emerald-700 hover:underline text-sm">후기 더 보기 →</a>
    </div>
  </section>
  {% endif %}

  {# 5. How it works #}
```

new_string:

```jinja
    <div class="grid gap-4 sm:grid-cols-2">
      {% for post in data.popular_reviews if not (data.featured_testimonial and post.id == data.featured_testimonial.id) %}
        {% include "partials/post_card.html" %}
      {% endfor %}
    </div>
    <div class="mt-6 text-center">
      <a href="/discover" class="text-emerald-700 hover:underline text-sm">후기 더 보기 →</a>
    </div>
  </section>
  {% endif %}

  {# 5. How it works #}
```

- [ ] **Step 4: Jinja syntax 검증 — `get_template` parse-only**

Run: `uv run python -c "from app.templating import templates; templates.get_template('pages/home.html'); print('OK')"`
Expected: `OK` 출력. (Jinja parse error만 잡음; 렌더는 Task 5의 integration test가 검증.)

- [ ] **Step 5: Lint**

Run: `uv run ruff check app/templates/`
Expected: `All checks passed!` (templates 디렉토리에 .py 파일 없으므로 사실상 noop이지만 안전)

- [ ] **Step 6: Commit**

```bash
git add app/templates/pages/home.html
git commit -m "feat(ui): redesign landing hero with T-axis copy + featured testimonial + persona cards

- Replace generic hero with question-form headline emphasizing PRD T-pillar
- Add featured_testimonial quote card (conditional on data.featured_testimonial)
- Absorb persona section into hero with per-card action paths
- Demote email signup to text link, kakao becomes single primary CTA
- Skip duplicate post in 인기 후기 grid when featured_testimonial is set
- Add PostHog event placeholder comments (to be wired in P1.5 OI-14)"
```

---

## Task 5: 비로그인 hero 통합 테스트 추가 (TDD)

**Files:**
- Modify: `app/tests/integration/test_pages.py`

- [ ] **Step 1: Write the failing tests**

먼저 `app/tests/integration/test_pages.py` 상단의 기존 import (`from fastapi.testclient import TestClient`) **바로 다음 줄들에** 신규 import를 추가 (top-of-file 규칙 — ruff E402 회피):

```python
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import PostStatus
from app.tests.factories import RegionFactory, ResidentUserFactory, ReviewPostFactory
```

(기존 `from fastapi.testclient import TestClient`를 위 블록으로 교체.)

같은 파일 **끝**에 신규 테스트 4개 추가:

```python
# ---------------------------------------------------------------------------
# Hero redesign — anonymous landing
# ---------------------------------------------------------------------------


def test_anonymous_home_hero_shows_t_axis_headline(client: TestClient) -> None:
    """헤드라인이 PRD T축(1년차 / 3년차) 카피를 직접 노출."""
    r = client.get("/")
    assert r.status_code == 200
    assert "1년차에 좋다는 후기는 많아도" in r.text
    assert "3년차의 진실은 어디서 듣나요" in r.text


def test_anonymous_home_renders_when_no_featured_testimonial(
    client: TestClient,
) -> None:
    """published review 0건 — featured 카드 미렌더, 페이지는 200."""
    r = client.get("/")
    assert r.status_code == 200
    # featured 카드가 없어도 페르소나 3카드는 렌더
    assert "예비 입주자" in r.text
    assert "1-3년차 거주자" in r.text
    assert "5년+ 베테랑" in r.text


def test_anonymous_home_persona_card_links(client: TestClient) -> None:
    """페르소나 카드 클릭 → 각각 wizard·signup·signup."""
    r = client.get("/")
    body = r.text
    # 예비 입주자 → /match/wizard
    assert 'href="/match/wizard"' in body
    # 1-3년차·5년+ → /auth/signup (정확히 2회 — 페르소나 카드 2개)
    # 본문 중 다른 위치(보조 텍스트 링크)에서 한 번 더 노출 → 총 3회
    assert body.count('href="/auth/signup"') >= 2


def test_anonymous_home_hero_renders_featured_testimonial(
    client: TestClient,
    db: Session,
) -> None:
    """published REVIEW가 있으면 hero에 featured 인용 카드가 렌더되고,
    동일 post가 '인기 후기' 그리드에 중복 노출되지 않음."""
    region = RegionFactory(slug="hero-featured-region")
    author = ResidentUserFactory(
        username="alice_yp",
        resident_verified_at=datetime.now(UTC) - timedelta(days=365 * 5),
    )
    top_review = ReviewPostFactory(
        author=author,
        region=region,
        status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC),
        view_count=999,
        title="정착 5년차 — 가장 큰 후회 비용 Top 3",
        body=(
            "5년 살아보니 후회 비용이 보이네요.\n\n"
            "1. 단열 (북측 벽 보강): 약 800만원\n"
            "2. 화목난로 굴뚝 위치 잘못: 재시공 220만원"
        ),
    )
    db.flush()

    r = client.get("/")
    assert r.status_code == 200
    body = r.text
    # featured 인용 본문 일부 노출
    assert "5년 살아보니 후회 비용이 보이네요" in body
    # attribution: 거주 연차 라벨 + 사용자 이름
    assert "5년차" in body
    assert "@alice_yp" in body
    # 인기 후기 그리드에 동일 post 의 detail link 가 추가로 노출되지 않음
    # (hero 카드에서 1번, popular_reviews 그리드에서 0번 → 총 1번)
    detail_url_marker = f'href="/post/{top_review.id}"'
    assert body.count(detail_url_marker) == 1
```

- [ ] **Step 2: Run tests to verify they fail (or some pass already from prior tasks)**

Run: `uv run pytest app/tests/integration/test_pages.py -v`
Expected:
- `test_anonymous_home_hero_shows_t_axis_headline` → PASS (Task 4에서 카피 적용됨)
- `test_anonymous_home_renders_when_no_featured_testimonial` → PASS
- `test_anonymous_home_persona_card_links` → PASS
- `test_anonymous_home_hero_renders_featured_testimonial` → PASS (Task 3·4가 모두 적용된 상태)

만약 어떤 test가 FAIL이라면, 정확한 assertion 메시지를 보고 Task 4 마크업 또는 본 테스트 데이터 setup을 디버그.

- [ ] **Step 3: Verify mobile responsive copy by inspecting key Tailwind classes**

Run: `uv run pytest app/tests/integration/test_pages.py -v && grep -E "(text-3xl sm:text-5xl|sm:grid-cols-3|max-w-2xl)" app/templates/pages/home.html`

Expected: 모든 테스트 PASS + grep이 hero 마크업에서 핵심 responsive 클래스 매치 라인을 출력.

- [ ] **Step 4: 풀 회귀 — 전체 testsuite**

Run: `uv run pytest app/tests/ -q`
Expected: 모든 테스트 PASS. 회귀 0.

- [ ] **Step 5: Lint**

Run: `uv run ruff check app/tests/integration/test_pages.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add app/tests/integration/test_pages.py
git commit -m "test(pages): cover redesigned anonymous hero (headline / persona / featured)"
```

---

## Task 6: 브라우저 manual QA + 최종 lint

**Files:** (no modifications — verification only)

- [ ] **Step 1: 개발 서버 가동**

Run: `uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &`
또는 `run_in_background=true`로. 5-10초 대기 후 다음 step.

- [ ] **Step 2: 비로그인 상태로 `/` 접속 — 데스크톱 시야 (>= 1024px)**

브라우저에서 `http://localhost:8000/` 비로그인 또는 시크릿 창. 다음 항목 시각 검증:

- [ ] 헤드라인 2줄 (sm 이상에서 두 번째 줄이 옆으로 붙는지)
- [ ] featured 인용 카드가 렌더되는지 (양평 시드 데이터가 있으면 alice_yp 후기)
- [ ] 페르소나 3카드가 한 줄 grid 로 정렬
- [ ] 카카오 노란 버튼이 한가운데에 단일 노출
- [ ] 보조 링크 "이메일로 가입 · 로그인" 정확
- [ ] 헤더와 카피 사이 호흡(padding) 자연
- [ ] 기존 4 Pillar / Match Wizard CTA / 인기 후기 / How it works / Bottom CTA 섹션이 변동 없이 이어짐
- [ ] "인기 후기" 그리드에 alice_yp 5년차 후기가 중복 노출되지 않음 (다른 후기들만 노출)

- [ ] **Step 3: 비로그인 상태로 `/` 접속 — 태블릿 시야 (640~1023px)**

DevTools → responsive mode → 768px 폭. 다음 검증:

- [ ] 헤드라인 두 번째 줄이 별도 줄로 바뀌는지 또는 한 줄에 붙는지 — break-keep 흐름이 자연스러운지
- [ ] 페르소나 3카드가 여전히 3열이거나 1열로 fall-back (sm:grid-cols-3 → 640px+ 3열)
- [ ] featured 인용 카드 max-w-2xl 안쪽 padding 적정

- [ ] **Step 4: 비로그인 상태로 `/` 접속 — 모바일 시야 (< 640px)**

DevTools → 375px 폭. 다음 검증:

- [ ] 헤드라인 줄바꿈이 자연 (block 으로 분리됨)
- [ ] 페르소나 3카드 1열 세로 스택
- [ ] 카카오 버튼이 여전히 충분히 크고 탭 가능
- [ ] 인용 카드가 화면을 넘치지 않음

- [ ] **Step 5: 페르소나 카드·CTA 클릭 동작 검증**

브라우저에서 차례로 클릭하여 navigation 확인:

- [ ] "예비 입주자" 카드 → `/match/wizard` 200 응답
- [ ] "1-3년차 거주자" 카드 → `/auth/signup` 200 응답
- [ ] "5년+ 베테랑" 카드 → `/auth/signup` 200 응답
- [ ] "카카오로 1초 시작" → `/auth/kakao/start` (실제 OAuth 시도까지는 dev 환경 설정에 의존; 라우트 호출만 확인)
- [ ] "이메일로 가입" 텍스트 링크 → `/auth/signup`
- [ ] "로그인" 텍스트 링크 → `/auth/login`
- [ ] featured 인용 카드 클릭 → `/post/{id}` 후기 detail 페이지

- [ ] **Step 6: 로그인 상태에서 `/` 접속하여 회귀 없음 확인**

DevTools 시크릿 창 닫고 일반 창에서 로그인 (`alice.yp@example.com` / `demo1234` 또는 보유 계정). `/` 접속 후:

- [ ] 비로그인 hero 마크업이 노출되지 **않음** (`{% if current_user %}` 분기 정상 작동)
- [ ] 기존 로그인 사용자 홈(인사 헤더 / 쓰기 / 팔로우 Journey / Match Wizard / 추천 시군) 모두 정상

- [ ] **Step 7: 백엔드 로그·콘솔 에러 부재 확인**

uvicorn 로그를 1분간 관찰. 위 모든 navigation에서:

- [ ] 500 응답 없음
- [ ] Jinja `UndefinedError` 없음
- [ ] DeprecationWarning 외 신규 warning 없음

- [ ] **Step 8: 최종 풀 lint**

Run: `uv run ruff check app/`
Expected: `All checks passed!`

- [ ] **Step 9: 최종 회귀**

Run: `uv run pytest app/tests/ -q`
Expected: 모든 테스트 PASS, 회귀 0.

- [ ] **Step 10: 백그라운드 uvicorn 종료**

Run: `pkill -f "uvicorn app.main:app"` (Linux/macOS) 또는 PowerShell: `Get-Process -Name "uvicorn" -ErrorAction SilentlyContinue | Stop-Process -Force` (Windows).

- [ ] **Step 11: 최종 git status 확인 + dev push 여부 사용자에게 확인 요청**

Run: `git status --short && git log --oneline -10`
Expected: working tree clean (또는 본 plan 외 사용자의 in-progress 변경만 남음). 직전 6개 commit 이 본 plan 의 task 1-5와 일치 (filter 1, filter 2, feed, ui, test, manual QA → 5 commits).

push 는 사용자 승인 후 별도 단계에서 진행 (본 plan에 포함하지 않음).

---

## DoD (Definition of Done — spec §7과 1:1 매칭)

| spec §7 항목 | Plan task | 검증 방법 |
|---|---|---|
| 비로그인 `/` 신규 hero 정상 렌더 | Task 4·6 | manual QA Step 2-4 + integration test 1 |
| featured 있을 때 카드 렌더 / 없을 때 카드 미렌더 200 | Task 3·4·5 | feed_service test 10·11 + pages test 2·4 |
| featured와 동일 post 가 인기후기 그리드 중복 미노출 | Task 4·5 | pages test 4 (`detail_url_marker count == 1`) |
| 페르소나 3카드 → wizard·signup·signup 정확 이동 | Task 4·5·6 | pages test 3 + manual QA Step 5 |
| 카카오 CTA → /auth/kakao/start 정상 | Task 4·6 | manual QA Step 5 |
| 모바일·태블릿·데스크톱 3 뷰포트 자연 | Task 6 | manual QA Step 2-4 |
| 페르소나 섹션 삭제 후 시각 단절 없음 | Task 4·6 | manual QA Step 2 ("기존 섹션 변동 없이 이어짐") |
| 4 PostHog placeholder 주석 포함 | Task 4 | grep `TODO(P1.5 PostHog)` 4 hits |
| pytest 회귀 0 | 모든 task | manual QA Step 9 |
| ruff lint clean | 모든 task | manual QA Step 8 |

---

## Rollback

전체 task 가 6 commit (filter 1, filter 2, feed, ui, test, plus pre-flight setup) 으로 분리되어 있어 임의 시점으로 `git revert <hash>` 또는 `git reset --hard <pre-feature-hash>` 로 복원 가능. DB 마이그레이션 없으므로 schema rollback 불필요.

---

## Out of plan (spec §10 Open Questions — 권고대로 진행)

다음 항목은 spec 권고를 따라 본 plan에서 별도 구현 없음:

- H1 의문형 종결 — 그대로 사용 (A/B 측정 가치)
- 페르소나 카드에 `?from=...` 쿼리 미추가 (PostHog referrer 사용)
- emerald gradient 색상 — 기존 톤 유지
- 사용자 본인 글이 featured 일 때 처리 — hero는 비로그인 only 이므로 N/A
