# 로그인 후 홈 "커뮤니티 펄스" 리디자인 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 로그인 사용자 홈을 "오늘의 발견" mixed feed 중심으로 재구성. 데이터 모델 변경 없이 `feed.py` 확장 + 신규 템플릿 3개 + FAB 컴포넌트 추가.

**Architecture:** ① `feed.py`에 `RegionActivity` dataclass + `home_mixed_feed`/`region_activity_summary` 두 함수 추가. `HomeData`에 `mixed_feed`·`region_activity` 필드 2개 추가. ② 기존 `partials/post_card.html`(Threads 스타일) 재사용 — journey_episode 메타 1줄만 추가. ③ 신규 컴포넌트 3개(`_welcome_strip.html`·`_write_fab.html`·`region_activity_card.html`). ④ `home.html`의 `{% if current_user %}` 블록 전체 재작성, 비로그인 블록은 손대지 않음.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Jinja2 SSR, Tailwind CDN, Alpine.js 3.x, HTMX 1.9, pytest, factory-boy.

**Related Spec:** [docs/superpowers/specs/2026-05-13-nestory-home-community-pulse-design.md](../specs/2026-05-13-nestory-home-community-pulse-design.md)

---

## File Structure

**Backend (서비스 + 분석)**

| 파일 | 역할 | 변경 종류 |
|---|---|---|
| `app/services/feed.py` | `home_data` 확장, `RegionActivity` dataclass, `home_mixed_feed`, `region_activity_summary` | Modify |
| `app/services/analytics.py` | 신규 `EventName` 4개 (HOME_FEED_CARD_CLICK / HOME_FAB_OPEN / HOME_FAB_ACTION / HOME_REGION_ACTIVITY_CLICK) | Modify |

**Frontend (템플릿)**

| 파일 | 역할 | 변경 종류 |
|---|---|---|
| `app/templates/components/_welcome_strip.html` | 1행 컴팩트 웰컴 (아바타+username+배지 칩) | Create |
| `app/templates/components/_write_fab.html` | 우하단 floating "+ 쓰기" + Alpine.js dropdown | Create |
| `app/templates/partials/region_activity_card.html` | 시군 카드 (sigungu/sido + weekly counters) | Create |
| `app/templates/partials/post_card.html` | journey_episode일 때 `「title」ep N` 메타 1줄 추가 | Modify |
| `app/templates/pages/home.html` | `{% if current_user %}` 블록 재작성 | Modify |
| `app/templates/base.html` | FAB include + 푸터 safe-area padding 1줄 | Modify |

**Tests**

| 파일 | 역할 | 변경 종류 |
|---|---|---|
| `app/tests/integration/test_feed_service.py` | 7 신규 서비스 단위 테스트 | Modify |
| `app/tests/integration/test_home_dynamic.py` | 5 신규 페이지 통합 테스트 | Modify |

---

## Task 1: feed.py — `RegionActivity` dataclass + `region_activity_summary` 함수 (TDD)

**Files:**
- Modify: [app/services/feed.py](../../app/services/feed.py)
- Test: [app/tests/integration/test_feed_service.py](../../app/tests/integration/test_feed_service.py)

- [ ] **Step 1: Write the failing test**

[app/tests/integration/test_feed_service.py](../../app/tests/integration/test_feed_service.py) 파일 끝에 추가:

```python
from datetime import timedelta

from app.services.feed import RegionActivity, region_activity_summary
from app.tests.factories import QuestionPostFactory


def test_region_activity_counts_within_7d_window(db: Session) -> None:
    """RegionActivity는 7일 내 published review·question을 카운트한다."""
    region = RegionFactory(slug="ra-region")
    now = datetime.now(UTC)
    # 7일 내 — 카운트
    _published_review(region, published_at=now - timedelta(days=1))
    _published_review(region, published_at=now - timedelta(days=6))
    QuestionPostFactory(
        region=region, status=PostStatus.PUBLISHED, published_at=now - timedelta(days=2)
    )
    # 7일 밖 — 제외
    _published_review(region, published_at=now - timedelta(days=8))
    # DRAFT — 제외
    ReviewPostFactory(region=region, status=PostStatus.DRAFT)
    db.commit()

    result = region_activity_summary(db, [region])
    assert len(result) == 1
    assert isinstance(result[0], RegionActivity)
    assert result[0].region.id == region.id
    assert result[0].new_reviews_7d == 2
    assert result[0].new_questions_7d == 1


def test_region_activity_returns_zero_for_inactive_region(db: Session) -> None:
    """활동 없는 시군은 카운터 0/0으로 반환."""
    region = RegionFactory(slug="ra-quiet")
    db.commit()
    result = region_activity_summary(db, [region])
    assert result[0].new_reviews_7d == 0
    assert result[0].new_questions_7d == 0


def test_region_activity_preserves_input_order(db: Session) -> None:
    """입력 region 순서 그대로 RegionActivity를 반환."""
    r1 = RegionFactory(slug="ra-a")
    r2 = RegionFactory(slug="ra-b")
    r3 = RegionFactory(slug="ra-c")
    db.commit()
    result = region_activity_summary(db, [r2, r3, r1])
    assert [ra.region.id for ra in result] == [r2.id, r3.id, r1.id]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/integration/test_feed_service.py::test_region_activity_counts_within_7d_window app/tests/integration/test_feed_service.py::test_region_activity_returns_zero_for_inactive_region app/tests/integration/test_feed_service.py::test_region_activity_preserves_input_order -v`

Expected: 3개 모두 FAIL with `ImportError: cannot import name 'RegionActivity' from 'app.services.feed'`.

- [ ] **Step 3: Implement `RegionActivity` + `region_activity_summary`**

[app/services/feed.py](../../app/services/feed.py)의 기존 import 블록 아래에 추가:

```python
from datetime import datetime, timedelta, UTC
```

(이미 있다면 skip. 파일 상단 dataclass 정의 근처에 다음 추가:)

```python
@dataclass
class RegionActivity:
    region: Region
    new_reviews_7d: int
    new_questions_7d: int
```

함수 추가 — 기존 `home_data` 정의 위 또는 아래:

```python
def region_activity_summary(db: Session, regions: list[Region]) -> list[RegionActivity]:
    """주어진 시군들의 최근 7일 published review·question 카운터를 반환.

    입력 순서를 보존한다. 단일 GROUP BY 쿼리 — N+1 없음.
    """
    if not regions:
        return []
    region_ids = [r.id for r in regions]
    cutoff = datetime.now(UTC) - timedelta(days=7)

    rows = db.execute(
        select(Post.region_id, Post.type, func.count().label("cnt"))
        .where(
            Post.region_id.in_(region_ids),
            Post.status == PostStatus.PUBLISHED,
            Post.deleted_at.is_(None),
            Post.published_at >= cutoff,
            Post.type.in_([PostType.REVIEW, PostType.QUESTION]),
        )
        .group_by(Post.region_id, Post.type)
    ).all()

    # (region_id, type) → count
    counts: dict[tuple[int, PostType], int] = {
        (r.region_id, r.type): r.cnt for r in rows
    }
    return [
        RegionActivity(
            region=region,
            new_reviews_7d=counts.get((region.id, PostType.REVIEW), 0),
            new_questions_7d=counts.get((region.id, PostType.QUESTION), 0),
        )
        for region in regions
    ]
```

`PostType` import 확인 — `from app.models._enums import PostStatus, PostType`로 이미 있어야 함.

`__all__`에 `"RegionActivity"`, `"region_activity_summary"` 추가.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest app/tests/integration/test_feed_service.py -v -k region_activity`

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/feed.py app/tests/integration/test_feed_service.py
git commit -m "feat(feed): RegionActivity dataclass + region_activity_summary

홈 시군 카드에 7일 weekly 카운터를 표시하기 위한 서비스. 단일 GROUP BY
쿼리로 review·question 카운트 — N+1 없음. 입력 region 순서 보존.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: feed.py — `home_mixed_feed` 함수 (TDD)

**Files:**
- Modify: [app/services/feed.py](../../app/services/feed.py)
- Test: [app/tests/integration/test_feed_service.py](../../app/tests/integration/test_feed_service.py)

- [ ] **Step 1: Write the failing tests**

[app/tests/integration/test_feed_service.py](../../app/tests/integration/test_feed_service.py) 파일 끝에 추가:

```python
from app.services.feed import home_mixed_feed
from app.tests.factories import (
    UserInterestRegionFactory,
)


def test_home_mixed_feed_returns_max_limit(db: Session, login) -> None:
    """후보가 충분할 때 limit 개수까지만 반환."""
    user = UserFactory()
    region = RegionFactory(slug="mf-region")
    for i in range(15):
        _published_review(region, view_count=i)
    db.commit()
    feed = home_mixed_feed(db, user, limit=8)
    assert len(feed) == 8


def test_home_mixed_feed_includes_all_three_types(db: Session) -> None:
    """review + journey_episode + question을 혼합한다."""
    user = UserFactory()
    region = RegionFactory(slug="mf-types")
    journey = JourneyFactory(author=user, region=region)
    for _ in range(3):
        _published_review(region)
    for _ in range(3):
        _published_episode(region, journey)
    for _ in range(3):
        QuestionPostFactory(
            region=region, status=PostStatus.PUBLISHED,
            published_at=datetime.now(UTC),
        )
    db.commit()
    feed = home_mixed_feed(db, user, limit=9)
    types = {p.type for p in feed}
    assert PostType.REVIEW in types
    assert PostType.JOURNEY_EPISODE in types
    assert PostType.QUESTION in types


def test_home_mixed_feed_boosts_followed_journey(db: Session) -> None:
    """팔로우 중인 journey의 ep가 비-팔로우 동시점 ep보다 상위."""
    user = UserFactory()
    region = RegionFactory(slug="mf-follow")
    same_published = datetime.now(UTC) - timedelta(days=3)
    followed_j = JourneyFactory(author=UserFactory(), region=region, title="팔로우저니")
    other_j = JourneyFactory(author=UserFactory(), region=region, title="다른저니")
    followed_ep = _published_episode(
        region, followed_j, published_at=same_published, title="팔로우에피"
    )
    other_ep = _published_episode(
        region, other_j, published_at=same_published, title="비팔로우에피"
    )
    add_journey_follow(db, user, followed_j)
    db.commit()

    feed = home_mixed_feed(db, user, limit=8)
    followed_idx = next(i for i, p in enumerate(feed) if p.id == followed_ep.id)
    other_idx = next(i for i, p in enumerate(feed) if p.id == other_ep.id)
    assert followed_idx < other_idx


def test_home_mixed_feed_boosts_interest_region(db: Session) -> None:
    """관심 시군 post가 비-관심 시군 동시점 post보다 상위."""
    user = UserFactory()
    interest_region = RegionFactory(slug="mf-interest")
    other_region = RegionFactory(slug="mf-other")
    same_published = datetime.now(UTC) - timedelta(days=3)
    interest_post = _published_review(
        interest_region, published_at=same_published, title="관심후기"
    )
    other_post = _published_review(
        other_region, published_at=same_published, title="비관심후기"
    )
    UserInterestRegionFactory(user=user, region=interest_region)
    db.commit()

    feed = home_mixed_feed(db, user, limit=8)
    interest_idx = next(i for i, p in enumerate(feed) if p.id == interest_post.id)
    other_idx = next(i for i, p in enumerate(feed) if p.id == other_post.id)
    assert interest_idx < other_idx


def test_home_mixed_feed_excludes_draft_and_deleted(db: Session) -> None:
    user = UserFactory()
    region = RegionFactory(slug="mf-excl")
    ReviewPostFactory(region=region, status=PostStatus.DRAFT, title="드래프트")
    _published_review(region, title="삭제됨").deleted_at = datetime.now(UTC)
    visible = _published_review(region, title="공개")
    db.commit()
    feed = home_mixed_feed(db, user, limit=8)
    titles = {p.title for p in feed}
    assert "공개" in titles
    assert "드래프트" not in titles
    assert "삭제됨" not in titles


def test_home_mixed_feed_empty_when_no_content(db: Session) -> None:
    user = UserFactory()
    db.commit()
    assert home_mixed_feed(db, user, limit=8) == []


def test_home_mixed_feed_excludes_old_posts(db: Session) -> None:
    """14일 윈도 밖 post는 후보 제외."""
    user = UserFactory()
    region = RegionFactory(slug="mf-old")
    old = _published_review(
        region, published_at=datetime.now(UTC) - timedelta(days=20), title="옛글"
    )
    recent = _published_review(
        region, published_at=datetime.now(UTC) - timedelta(days=1), title="새글"
    )
    db.commit()
    feed = home_mixed_feed(db, user, limit=8)
    ids = {p.id for p in feed}
    assert recent.id in ids
    assert old.id not in ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/integration/test_feed_service.py -v -k home_mixed_feed`

Expected: 7 FAIL with `ImportError: cannot import name 'home_mixed_feed' from 'app.services.feed'`.

- [ ] **Step 3: Implement `home_mixed_feed`**

[app/services/feed.py](../../app/services/feed.py)에 추가:

```python
from math import log10

from app.models import UserInterestRegion
from app.models.interaction import journey_follows


_FEED_WINDOW_DAYS = 14
_FEED_CANDIDATE_LIMIT = 30
_MAX_PER_TYPE = 3  # 같은 type이 3개 이상이면 페널티 적용


def _score_post(
    post: Post,
    *,
    now: datetime,
    followed_journey_ids: set[int],
    interest_region_ids: set[int],
    selected_type_counts: dict[PostType, int],
) -> float:
    """단일 post의 mixed feed 정렬용 score.

    base recency (0..1) + log popularity + follow boost + interest_region boost
    - diversity penalty (selected_type_counts >= _MAX_PER_TYPE 시).
    """
    days = (now - post.published_at).total_seconds() / 86400 if post.published_at else _FEED_WINDOW_DAYS
    recency = max(0.0, (_FEED_WINDOW_DAYS - days) / _FEED_WINDOW_DAYS)  # 0..1
    popularity = min(0.6, log10(max(post.view_count, 0) + 1) * 0.3)
    follow = 0.5 if post.journey_id and post.journey_id in followed_journey_ids else 0.0
    interest = 0.3 if post.region_id in interest_region_ids else 0.0
    penalty = -0.2 if selected_type_counts.get(post.type, 0) >= _MAX_PER_TYPE else 0.0
    return recency + popularity + follow + interest + penalty


def home_mixed_feed(db: Session, user: User, *, limit: int = 8) -> list[Post]:
    """로그인 사용자의 "오늘의 발견" mixed feed 8개.

    Score 기반 정렬: recency + popularity + follow boost + interest_region boost
    - diversity penalty. 단일 query로 후보 30개를 가져온 뒤 Python에서 정렬.
    """
    cutoff = datetime.now(UTC) - timedelta(days=_FEED_WINDOW_DAYS)
    candidates = list(
        db.scalars(
            select(Post)
            .where(
                Post.type.in_([PostType.REVIEW, PostType.JOURNEY_EPISODE, PostType.QUESTION]),
                Post.status == PostStatus.PUBLISHED,
                Post.deleted_at.is_(None),
                Post.published_at >= cutoff,
            )
            .options(selectinload(Post.author), selectinload(Post.region))
            .order_by(Post.published_at.desc())
            .limit(_FEED_CANDIDATE_LIMIT)
        ).all()
    )
    if not candidates:
        return []

    followed_journey_ids: set[int] = set(
        db.scalars(
            select(journey_follows.c.journey_id).where(
                journey_follows.c.user_id == user.id
            )
        ).all()
    )
    interest_region_ids: set[int] = set(
        db.scalars(
            select(UserInterestRegion.region_id).where(
                UserInterestRegion.user_id == user.id
            )
        ).all()
    )

    now = datetime.now(UTC)
    selected: list[Post] = []
    selected_type_counts: dict[PostType, int] = {}
    remaining = list(candidates)

    while remaining and len(selected) < limit:
        # 매 라운드마다 (selected_type_counts 변동) score 재계산 후 best 선택
        scored = sorted(
            remaining,
            key=lambda p: _score_post(
                p, now=now,
                followed_journey_ids=followed_journey_ids,
                interest_region_ids=interest_region_ids,
                selected_type_counts=selected_type_counts,
            ),
            reverse=True,
        )
        pick = scored[0]
        selected.append(pick)
        selected_type_counts[pick.type] = selected_type_counts.get(pick.type, 0) + 1
        remaining.remove(pick)

    return selected
```

`__all__`에 `"home_mixed_feed"` 추가.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest app/tests/integration/test_feed_service.py -v -k home_mixed_feed`

Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/feed.py app/tests/integration/test_feed_service.py
git commit -m "feat(feed): home_mixed_feed — recency + boost 기반 8개 추천

review/journey_ep/question 혼합 피드. 후보 30개를 단일 query로 가져온 뒤
Python에서 매 라운드 score 재계산하며 best를 뽑는다. type diversity
penalty로 한 종류가 피드를 독점하지 않도록 함. 팔로우 journey +0.5,
관심 시군 +0.3 boost.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: feed.py — `HomeData` 필드 추가 + `home_data` 통합 (TDD)

**Files:**
- Modify: [app/services/feed.py](../../app/services/feed.py)
- Test: [app/tests/integration/test_feed_service.py](../../app/tests/integration/test_feed_service.py)

- [ ] **Step 1: Write the failing tests**

[app/tests/integration/test_feed_service.py](../../app/tests/integration/test_feed_service.py) 파일 끝에 추가:

```python
def test_home_data_includes_mixed_feed_for_logged_in(db: Session) -> None:
    user = UserFactory()
    region = RegionFactory(slug="hd-region")
    _published_review(region, title="피드후기")
    db.commit()
    data = feed_service.home_data(db, user)
    assert len(data.mixed_feed) >= 1
    assert any(p.title == "피드후기" for p in data.mixed_feed)


def test_home_data_empty_mixed_feed_for_anon(db: Session) -> None:
    region = RegionFactory(slug="hd-anon")
    _published_review(region)
    db.commit()
    data = feed_service.home_data(db, None)
    assert data.mixed_feed == []


def test_home_data_region_activity_aligned_with_recommended(db: Session) -> None:
    """region_activity와 recommended_regions의 길이·순서가 일치."""
    PilotRegionFactory(slug="hd-r1")
    PilotRegionFactory(slug="hd-r2")
    db.commit()
    data = feed_service.home_data(db, None)
    assert len(data.region_activity) == len(data.recommended_regions)
    for ra, region in zip(data.region_activity, data.recommended_regions):
        assert ra.region.id == region.id


def test_home_data_prefers_user_interest_regions(db: Session) -> None:
    """로그인 시 UserInterestRegion이 있으면 recommended_regions 상위에 포함."""
    user = UserFactory()
    interest = RegionFactory(slug="hd-interest", is_pilot=False, sigungu="관심시군")
    # pilot region은 default 정렬상 우선이지만, interest region이 더 상위여야 함
    PilotRegionFactory(slug="hd-pilot-1")
    UserInterestRegionFactory(user=user, region=interest)
    db.commit()
    data = feed_service.home_data(db, user)
    assert data.recommended_regions[0].id == interest.id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/integration/test_feed_service.py -v -k home_data`

Expected: 4 신규 테스트 FAIL with `AttributeError: 'HomeData' object has no attribute 'mixed_feed'` 등. 기존 home_data 테스트는 그대로 PASS.

- [ ] **Step 3: Extend `HomeData` and `home_data()`**

[app/services/feed.py](../../app/services/feed.py)의 `HomeData` 정의를 수정:

```python
@dataclass
class HomeData:
    recommended_regions: list[Region]
    popular_reviews: list[Post]
    recent_journeys: list[Post]
    followed_episodes: list[Post]
    featured_testimonial: Post | None
    mixed_feed: list[Post]
    region_activity: list["RegionActivity"]
```

`home_data()` 함수 내 `regions` 계산 부분을 다음과 같이 교체:

```python
def home_data(db: Session, user: User | None) -> HomeData:
    """Return home page data: recommended regions, popular/recent posts, followed episodes."""
    # recommended_regions: 로그인 + UserInterestRegion 있으면 그 시군 우선, 부족분은 기본 정렬로 보충
    interest_ids: list[int] = []
    if user is not None:
        interest_ids = list(
            db.scalars(
                select(UserInterestRegion.region_id)
                .where(UserInterestRegion.user_id == user.id)
                .order_by(UserInterestRegion.priority.asc(), UserInterestRegion.created_at.asc())
            ).all()
        )

    base_query = (
        select(Region)
        .order_by(Region.is_pilot.desc(), Region.id.asc())
    )
    if interest_ids:
        interest_regions = list(
            db.scalars(
                select(Region)
                .where(Region.id.in_(interest_ids))
                .order_by(
                    # interest_ids 순서를 유지하기 위해 array_position 같은 dialect-specific
                    # 함수 대신 Python에서 정렬
                    Region.id.asc()
                )
            ).all()
        )
        # interest_ids 순서로 재정렬
        order = {rid: i for i, rid in enumerate(interest_ids)}
        interest_regions.sort(key=lambda r: order[r.id])

        fill_count = max(0, 4 - len(interest_regions))
        fill_regions = list(
            db.scalars(
                base_query
                .where(Region.id.not_in(interest_ids))
                .limit(fill_count)
            ).all()
        ) if fill_count > 0 else []
        regions = interest_regions[:4] + fill_regions
    else:
        regions = list(db.scalars(base_query.limit(4)).all())

    # ... 기존 popular_reviews / recent_journeys / followed_episodes 블록 그대로 유지 ...

    mixed_feed = home_mixed_feed(db, user) if user is not None else []
    region_activity = region_activity_summary(db, regions)

    return HomeData(
        recommended_regions=regions,
        popular_reviews=popular_reviews,
        recent_journeys=recent_journeys,
        followed_episodes=followed_episodes,
        featured_testimonial=popular_reviews[0] if popular_reviews else None,
        mixed_feed=mixed_feed,
        region_activity=region_activity,
    )
```

(전체 함수를 그대로 두지 말 것 — `regions = ...` 한 줄을 위 블록으로 치환하고, return 직전에 `mixed_feed` / `region_activity` 계산 후 키워드 인수 2개를 `HomeData(...)` 호출에 추가.)

- [ ] **Step 4: Run all feed service tests**

Run: `uv run pytest app/tests/integration/test_feed_service.py -v`

Expected: 신규 4개 포함 모든 테스트 PASS. 기존 `test_home_data_*` 테스트도 그대로 PASS여야 함.

- [ ] **Step 5: Commit**

```bash
git add app/services/feed.py app/tests/integration/test_feed_service.py
git commit -m "feat(feed): HomeData에 mixed_feed·region_activity 필드 추가

로그인 사용자에겐 mixed_feed 8개를 채우고, recommended_regions는
UserInterestRegion 우선 + 기본 정렬로 부족분 보충(최대 4개). 비로그인
사용자는 mixed_feed=[]. region_activity는 recommended_regions와 1:1 매핑.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `post_card.html` — journey_episode 메타 1줄 추가

**Files:**
- Modify: [app/templates/partials/post_card.html](../../app/templates/partials/post_card.html)

이 task는 시각 변경 + 기존 home_dynamic 테스트로 회귀 검증. 별도 단위 테스트 없음 (단순 1줄 추가).

- [ ] **Step 1: Modify post_card.html**

[app/templates/partials/post_card.html:23-32](../../app/templates/partials/post_card.html#L23-L32) 의 `<header>` 블록을 다음으로 교체 — `relative_time` 라인 **앞**에 journey 메타를 한 줄 추가:

```html
    <header class="flex items-center gap-1 text-[15px]">
      <a href="/u/{{ post.author.username }}" class="font-semibold text-stone-900 truncate hover:underline">
        {{ post.author.username }}
      </a>
      {% if post.author.badge_level.value in ("resident", "ex_resident") %}
        <span title="거주자 인증" class="inline-flex">{{ icon("verified", 14) }}</span>
      {% endif %}
      {% if post.type.value == "journey_episode" and post.journey %}
        <span class="ml-1.5 text-sm text-stone-500 truncate">
          · 「{{ post.journey.title }}」 ep {{ post.episode_no }}
        </span>
      {% endif %}
      <span class="ml-1.5 text-sm text-stone-500">{{ relative_time(post.published_at, now()) }}</span>
      <button type="button" class="ml-auto rounded-full p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-600" aria-label="더보기">{{ icon("more-horizontal", 18) }}</button>
    </header>
```

- [ ] **Step 2: Run existing home_dynamic tests for regression**

Run: `uv run pytest app/tests/integration/test_home_dynamic.py -v`

Expected: 기존 테스트 모두 PASS.

- [ ] **Step 3: Run all integration tests for regression**

Run: `uv run pytest app/tests/integration/ -q`

Expected: 전체 통합 테스트 PASS (이 변경은 1줄 conditional 추가일 뿐).

- [ ] **Step 4: Commit**

```bash
git add app/templates/partials/post_card.html
git commit -m "feat(ui): journey_episode 카드에 「title」 ep N 메타 표시

mixed feed에서 journey ep와 review를 구별하기 쉽게 작성자 줄 옆에
journey 제목과 에피소드 번호를 추가. 비-ep type엔 영향 없음.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `partials/region_activity_card.html` — 신규

**Files:**
- Create: `app/templates/partials/region_activity_card.html`

- [ ] **Step 1: Create the partial**

`app/templates/partials/region_activity_card.html` — 새 파일:

```html
{% from "components/_icon.html" import icon %}
{# partials/region_activity_card.html — Expects: activity (RegionActivity).
   주간 활동 카운터가 0/0이면 description fallback 또는 카드 자체에서 sigungu만 노출. #}
{% set region = activity.region %}
{% set has_activity = activity.new_reviews_7d > 0 or activity.new_questions_7d > 0 %}
{# TODO(P1.5 PostHog): home_region_activity_click {region_id: region.id} on click #}
<a href="/hub/{{ region.slug }}"
   class="block rounded-lg border border-stone-200 bg-white p-5 hover:border-emerald-300 hover:shadow-sm transition">
  <p class="font-semibold text-stone-900">{{ region.sigungu }}</p>
  <p class="text-xs text-stone-500 mt-1">{{ region.sido }}</p>
  {% if has_activity %}
    <div class="mt-3 flex items-center gap-3 text-xs text-stone-600">
      <span class="text-stone-400">이번 주</span>
      {% if activity.new_reviews_7d > 0 %}
        <span class="inline-flex items-center gap-1">
          <span class="text-emerald-600">{{ icon("file-pen", 12) }}</span>
          새 후기 {{ activity.new_reviews_7d }}
        </span>
      {% endif %}
      {% if activity.new_questions_7d > 0 %}
        <span class="inline-flex items-center gap-1">
          <span class="text-sky-600">{{ icon("help-circle", 12) }}</span>
          새 질문 {{ activity.new_questions_7d }}
        </span>
      {% endif %}
    </div>
  {% elif region.description %}
    <p class="text-sm text-stone-600 mt-2 line-clamp-2">{{ region.description }}</p>
  {% endif %}
</a>
```

- [ ] **Step 2: Sanity check 렌더링 (단독 검증은 Task 8 통합 시점)**

이 partial은 Task 8에서 home.html로부터 include되며 그때 페이지 통합 테스트로 검증. 단독 검증 step 없음.

- [ ] **Step 3: Commit**

```bash
git add app/templates/partials/region_activity_card.html
git commit -m "feat(ui): region_activity_card 신규 — 시군 카드 + 주간 카운터

후기·질문 카운터가 0/0이면 description fallback. 둘 다 0이고 description
도 없으면 sigungu/sido만 표시. PostHog 이벤트 emit 위치는 TODO 주석.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `components/_welcome_strip.html` — 신규

**Files:**
- Create: `app/templates/components/_welcome_strip.html`

- [ ] **Step 1: Create the component**

`app/templates/components/_welcome_strip.html`:

```html
{% from "components/_icon.html" import icon %}
{% from "components/_avatar.html" import avatar %}
{# components/_welcome_strip.html — 로그인 사용자 컴팩트 웰컴.
   Expects: current_user. #}
<header class="flex items-center gap-3 py-3 border-b border-stone-100">
  {{ avatar(current_user, 40, "shadow-sm") }}
  <div class="min-w-0 flex-1">
    <p class="text-sm text-stone-600 truncate">
      안녕하세요, <span class="font-semibold text-stone-900">@{{ current_user.username }}</span> 님
    </p>
    <div class="mt-0.5">
      {% set _bv = current_user.badge_level.value %}
      {% if _bv == "resident" %}
        <span class="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
          <span class="text-emerald-600">{{ icon("home", 12) }}</span>거주자 인증
        </span>
      {% elif _bv == "ex_resident" %}
        <span class="inline-flex items-center gap-1 rounded-full border border-stone-200 bg-white px-2 py-0.5 text-xs font-medium text-stone-700">
          <span class="text-stone-600">{{ icon("home", 12) }}</span>전 거주자
        </span>
      {% elif _bv == "region_verified" %}
        <span class="inline-flex items-center gap-1 rounded-full border border-sky-200 bg-sky-50 px-2 py-0.5 text-xs font-medium text-sky-700">
          <span class="text-sky-600">{{ icon("check-circle", 12) }}</span>지역 인증
        </span>
      {% else %}
        <span class="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-white px-2 py-0.5 text-xs font-medium text-emerald-700">
          <span class="text-emerald-600">{{ icon("heart", 12) }}</span>관심자
        </span>
      {% endif %}
    </div>
  </div>
</header>
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/components/_welcome_strip.html
git commit -m "feat(ui): _welcome_strip 컴팩트 1행 웰컴 컴포넌트

기존 home의 그라데이션 카드(p-5)를 압축 — 40px 아바타 + username +
배지 칩 작은 사이즈. 페이지 첫 화면을 mixed feed에 시각 자원 집중.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: `components/_write_fab.html` — 신규 FAB (Alpine.js)

**Files:**
- Create: `app/templates/components/_write_fab.html`

- [ ] **Step 1: Create the FAB component**

`app/templates/components/_write_fab.html`:

```html
{% from "components/_icon.html" import icon %}
{# components/_write_fab.html — 우하단 floating "+ 쓰기" FAB.
   Expects: current_user. 권한 분기는 표시 단순화용 — 실제 가드는 라우트에서. #}
{% set is_resident = current_user.badge_level.value in ("resident", "ex_resident") %}
<div class="fixed bottom-6 right-6 z-40 sm:bottom-8 sm:right-8"
     x-data="{ open: false }"
     @keydown.escape.window="open = false"
     @click.outside="open = false">
  {# TODO(P1.5 PostHog): home_fab_open on toggle to true #}
  <button type="button"
          class="inline-flex h-14 w-14 items-center justify-center rounded-full bg-emerald-600 text-white shadow-lg hover:bg-emerald-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2"
          @click="open = !open"
          :aria-expanded="open.toString()"
          aria-label="쓰기 메뉴 열기">
    <span x-show="!open">{{ icon("pencil", 24) }}</span>
    <span x-show="open" x-cloak>{{ icon("x", 24) }}</span>
  </button>
  <div x-show="open" x-cloak x-transition
       class="absolute bottom-16 right-0 w-56 rounded-xl border border-stone-200 bg-white py-2 shadow-lg">
    {# TODO(P1.5 PostHog): home_fab_action {action: "review"} on click #}
    <a href="{{ '/write/review' if is_resident else '/me/badge' }}"
       class="flex items-center gap-3 px-4 py-2.5 text-sm text-stone-900 hover:bg-stone-50">
      <span class="text-emerald-600">{{ icon("file-pen", 18) }}</span>
      <span>후기 작성</span>
      {% if not is_resident %}<span class="ml-auto text-xs text-stone-400">🔒</span>{% endif %}
    </a>
    {# TODO(P1.5 PostHog): home_fab_action {action: "journey"} on click #}
    <a href="{{ '/write/journey' if is_resident else '/me/badge' }}"
       class="flex items-center gap-3 px-4 py-2.5 text-sm text-stone-900 hover:bg-stone-50">
      <span class="text-amber-600">{{ icon("map", 18) }}</span>
      <span>Journey 시작</span>
      {% if not is_resident %}<span class="ml-auto text-xs text-stone-400">🔒</span>{% endif %}
    </a>
    {# TODO(P1.5 PostHog): home_fab_action {action: "question"} on click #}
    <a href="/write/question"
       class="flex items-center gap-3 px-4 py-2.5 text-sm text-stone-900 hover:bg-stone-50">
      <span class="text-sky-600">{{ icon("help-circle", 18) }}</span>
      <span>질문 작성</span>
    </a>
    {# TODO(P1.5 PostHog): home_fab_action {action: "plan"} on click #}
    <a href="/write/plan"
       class="flex items-center gap-3 px-4 py-2.5 text-sm text-stone-900 hover:bg-stone-50">
      <span class="text-violet-600">{{ icon("calendar", 18) }}</span>
      <span>정착 계획</span>
    </a>
  </div>
</div>
```

- [ ] **Step 2: Verify icon names exist**

위에서 사용한 아이콘은 모두 `_icon.html`에 정의돼 있음 — `pencil` (home.html에서 이미 사용), `x` (line 63), `file-pen`, `map`, `help-circle`, `calendar`. 추가 검증:

Run: `uv run python -c "from pathlib import Path; t = Path('app/templates/components/_icon.html').read_text(encoding='utf-8'); [print(n, n in t) for n in ['pencil', 'x', 'file-pen', 'map', 'help-circle', 'calendar']]"`

Expected: 6개 모두 `True`. False 있으면 `_icon.html`에 누락된 아이콘을 추가하거나(다른 곳에서 동일 svg path 발견 가능) 대체 아이콘 사용.

- [ ] **Step 3: Commit**

```bash
git add app/templates/components/_write_fab.html
git commit -m "feat(ui): _write_fab — 우하단 floating + 쓰기 FAB

Alpine.js dropdown 4 entry (후기/Journey/질문/계획). 거주자 인증 안 된
사용자는 후기/Journey 클릭 시 /me/badge로 안내(라우트 가드 그대로).
Esc·바깥 클릭으로 닫기, aria-expanded·aria-label 접근성 처리.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: `home.html` 로그인 블록 재작성 + `base.html` FAB include

**Files:**
- Modify: [app/templates/pages/home.html](../../app/templates/pages/home.html)
- Modify: [app/templates/base.html](../../app/templates/base.html)

- [ ] **Step 1: Replace logged-in block in home.html**

[app/templates/pages/home.html](../../app/templates/pages/home.html)의 `{% if current_user %}` 부터 `{% else %}` 직전까지 (line 6 - line 135) 전체를 다음으로 교체:

```html
{% if current_user %}
  <section class="space-y-8">
    {% include "components/_welcome_strip.html" %}

    {# 오늘의 발견 — mixed feed #}
    <section class="space-y-2">
      <h2 class="flex items-center gap-2 text-lg font-semibold text-stone-900">
        <span class="text-amber-600">{{ icon("sparkles", 20) }}</span>오늘의 발견
      </h2>
      {% if data.mixed_feed %}
        <div class="grid gap-2 sm:grid-cols-2 sm:gap-4 divide-y divide-stone-200 sm:divide-y-0">
          {% for post in data.mixed_feed %}
            {# TODO(P1.5 PostHog): home_feed_card_click {post_id: post.id, type: post.type.value} #}
            {% include "partials/post_card.html" %}
          {% endfor %}
        </div>
        <div class="pt-4 text-center">
          <a href="/discover" class="text-sm text-emerald-700 hover:underline">더 보기 →</a>
        </div>
      {% else %}
        <div class="rounded-lg border border-dashed border-stone-300 bg-white p-8 text-center space-y-3">
          <p class="text-stone-700">아직 추천할 콘텐츠가 없어요.</p>
          <div class="flex flex-col sm:flex-row justify-center gap-2">
            <a href="/match/wizard"
               class="inline-block rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700">
              5문항 매칭으로 시군 찾기 →
            </a>
            <a href="/discover"
               class="inline-block rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-700 hover:border-stone-400">
              Journey 탐색하기 →
            </a>
          </div>
        </div>
      {% endif %}
    </section>

    {# 매칭 슬림 CTA #}
    <section>
      <a href="/match/wizard"
         class="flex items-center gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 hover:border-emerald-300 transition">
        <span class="text-emerald-600">{{ icon("target", 20) }}</span>
        <div class="min-w-0 flex-1">
          <p class="text-sm font-semibold text-stone-900">나에게 맞는 시군 찾기</p>
          <p class="text-xs text-stone-600">5문항으로 Top 3 추천</p>
        </div>
        <span class="text-sm font-medium text-emerald-700">시작 →</span>
      </a>
    </section>

    {# 내 관심 시군 / 추천 시군 — RegionActivity card #}
    {% if data.region_activity %}
    <section class="space-y-4 border-t border-stone-200 pt-8">
      <h2 class="flex items-center gap-2 text-lg font-semibold text-stone-900">
        <span class="text-emerald-600">{{ icon("trees", 20) }}</span>
        {% if current_user.user_interest_regions if current_user.user_interest_regions is defined else False %}내 관심 시군{% else %}추천 시군{% endif %}
      </h2>
      <div class="grid gap-3 sm:grid-cols-2">
        {% for activity in data.region_activity %}
          {% include "partials/region_activity_card.html" %}
        {% endfor %}
      </div>
    </section>
    {% endif %}
  </section>
{% else %}
```

**중요**: `{% else %}` 라인 자체와 그 이후(비로그인 블록 line 137~370)는 1글자도 변경하지 말 것. 비로그인 마케팅 랜딩은 변경 범위 외.

또한 위 템플릿의 "내 관심 시군 / 추천 시군" H2의 동적 분기 — `current_user.user_interest_regions` 관계가 ORM에 정의돼 있지 않을 수 있음. 다음 step에서 확인하고 적용.

- [ ] **Step 2: Verify or simplify the H2 branch**

`User` 모델에 `user_interest_regions` relationship이 있는지 확인:

Run: `grep -E "relationship.*UserInterestRegion|user_interest_regions" app/models/user.py`

없으면 위 H2 라인을 단순화:

```html
        {# 시군 라벨 — 향후 UserInterestRegion 관계 추가 시 동적 분기 #}
        <span class="text-emerald-600">{{ icon("trees", 20) }}</span>추천 시군
```

(즉 동적 분기 제거하고 "추천 시군"만 노출. UserInterestRegion이 home_data에서 정렬에는 사용되지만 헤더 텍스트 분기까지는 보장 안 함.)

- [ ] **Step 3: Add FAB include to base.html**

[app/templates/base.html:42-47](../../app/templates/base.html#L42-L47) — `<main>` 직후, `<footer>` 직전에 FAB include를 추가하고 푸터 safe-area padding을 1줄:

```html
  <main class="mx-auto max-w-3xl px-5 sm:px-6 py-6 pb-24 sm:pb-16">
    {% block content %}{% endblock %}
  </main>
  {% if current_user %}{% include "components/_write_fab.html" %}{% endif %}
  <footer class="mt-8 py-4 text-center text-xs text-stone-500">
    © Nestory · 전원생활 정착의 여정
  </footer>
```

(즉 `<main>`의 클래스에 `pb-24 sm:pb-16`을 추가하고, `<main>` 닫는 태그 다음 줄에 conditional include를 추가.)

- [ ] **Step 4: Manual visual check (dev server)**

테스트 환경 또는 dev server 기동:

```powershell
docker compose -f docker-compose.local.yml up -d
uv run alembic upgrade head
uv run python -m scripts.seed_yangpyeong_demo
uv run uvicorn app.main:app --reload --port 8000
```

브라우저로 `http://localhost:8000`. `alice.yp@example.com` / `demo1234` 로그인. 다음 확인:
- 컴팩트 웰컴 strip 1행 노출.
- "오늘의 발견" 섹션이 mixed feed 카드 (이미지 있는 카드는 thumbnail, 없는 카드는 본문 line-clamp) 노출.
- journey ep 카드에 「title」ep N 메타 보임.
- 슬림 매칭 CTA 1행.
- 추천 시군 카드에 "이번 주 새 후기 N" 같은 카운터 보임 (양평/가평 시드).
- 우하단 FAB 클릭 → 4 entry dropdown.
- Esc 또는 바깥 클릭 → dropdown 닫힘.

문제 있으면 Step 1~3을 수정. 모두 OK면 다음 step으로.

- [ ] **Step 5: Commit**

```bash
git add app/templates/pages/home.html app/templates/base.html
git commit -m "feat(ui): 로그인 홈 \"커뮤니티 펄스\" 재구성

- 5개 평면 섹션 → 4섹션 + FAB로 위계 재편
- 기존 \"쓰기\" 4-카드 / 별도 \"팔로우 Journey\" 섹션 제거
- 오늘의 발견 mixed feed(HomeData.mixed_feed)가 1차 시각 자산
- 시군 카드는 region_activity_card 사용 — 주간 카운터 노출
- base.html: 로그인 시 FAB include, main에 pb-24 sm:pb-16 safe area
- 비로그인 marketing landing은 1줄도 변경 X

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: 통합 페이지 테스트 5개 추가

**Files:**
- Modify: [app/tests/integration/test_home_dynamic.py](../../app/tests/integration/test_home_dynamic.py)

- [ ] **Step 1: Write the failing tests**

[app/tests/integration/test_home_dynamic.py](../../app/tests/integration/test_home_dynamic.py) 파일 끝에 추가:

```python
from datetime import timedelta

from app.tests.factories import QuestionPostFactory


def test_home_logged_in_shows_mixed_feed_section(
    client: TestClient, db: Session, login
) -> None:
    """로그인 + 시드 → '오늘의 발견' 섹션 + 카드 노출."""
    user = ResidentUserFactory()
    region = RegionFactory(slug="hd-mf")
    ReviewPostFactory(
        region=region, status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC), title="펄스피드후기카드",
    )
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200
    assert "오늘의 발견" in r.text
    assert "펄스피드후기카드" in r.text


def test_home_logged_in_empty_state_when_no_content(
    client: TestClient, db: Session, login
) -> None:
    """후보 0개 → empty state CTA 노출."""
    user = ResidentUserFactory()
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200
    assert "아직 추천할 콘텐츠가 없어요" in r.text


def test_home_logged_in_renders_fab(
    client: TestClient, db: Session, login
) -> None:
    """FAB 버튼 + 4 entry link 노출."""
    user = ResidentUserFactory()
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200
    assert 'aria-label="쓰기 메뉴 열기"' in r.text
    assert "/write/review" in r.text
    assert "/write/journey" in r.text
    assert "/write/question" in r.text
    assert "/write/plan" in r.text


def test_home_anonymous_no_fab(client: TestClient, db: Session) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert 'aria-label="쓰기 메뉴 열기"' not in r.text


def test_home_region_activity_card_shows_counters(
    client: TestClient, db: Session, login
) -> None:
    """시군 카드에 주간 카운터 라벨이 보인다."""
    user = ResidentUserFactory()
    region = PilotRegionFactory(slug="hd-ra", sigungu="활동시군")
    ReviewPostFactory(
        region=region, status=PostStatus.PUBLISHED,
        published_at=datetime.now(UTC) - timedelta(days=1), title="활동시군주간",
    )
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200
    assert "활동시군" in r.text
    assert "이번 주" in r.text
    assert "새 후기 1" in r.text
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest app/tests/integration/test_home_dynamic.py -v`

Expected: 5 신규 테스트 모두 PASS. 기존 테스트도 회귀 없음.

(만약 신규 테스트 중 일부 FAIL 시: Task 8의 템플릿을 보정. 가장 흔한 원인은 H2 텍스트, CTA 문구, aria-label 등 spec과 다르게 작성한 경우.)

- [ ] **Step 3: Run full test suite for regression**

Run: `uv run pytest app/tests/ -q`

Expected: 전체 PASS. 새 testcase 12개(feed 7 + home 5) 추가됐어야 함.

- [ ] **Step 4: Commit**

```bash
git add app/tests/integration/test_home_dynamic.py
git commit -m "test(home): 로그인 홈 \"커뮤니티 펄스\" 통합 테스트 5개

오늘의 발견 mixed feed 노출 / empty state CTA / FAB 4 entry /
비로그인엔 FAB 없음 / 시군 카드 주간 카운터.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: `analytics.py` — EventName 4개 추가

**Files:**
- Modify: [app/services/analytics.py](../../app/services/analytics.py)

- [ ] **Step 1: Add new EventName values**

[app/services/analytics.py:20-48](../../app/services/analytics.py#L20-L48) `EventName` enum 끝(`NOTIFICATION_OPENED` 다음 줄)에 추가:

```python
    # P1.5b — home community pulse
    HOME_FEED_CARD_CLICK = "home_feed_card_click"
    HOME_FAB_OPEN = "home_fab_open"
    HOME_FAB_ACTION = "home_fab_action"
    HOME_REGION_ACTIVITY_CLICK = "home_region_activity_click"
```

- [ ] **Step 2: Sanity test that enum imports**

Run: `uv run python -c "from app.services.analytics import EventName; print(EventName.HOME_FEED_CARD_CLICK.value)"`

Expected: `home_feed_card_click` 출력.

- [ ] **Step 3: Run lint**

Run: `uv run ruff check app/services/analytics.py`

Expected: clean (no errors).

- [ ] **Step 4: Commit**

```bash
git add app/services/analytics.py
git commit -m "feat(analytics): home community pulse 4 EventName 추가

home_feed_card_click / home_fab_open / home_fab_action /
home_region_activity_click. 실제 emit은 P1.5 PostHog 통합 시점에
템플릿 TODO 주석 위치에서 호출.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: 수동 확인 체크리스트 + 정리

**Files:** 변경 없음. 수동 검증만.

- [ ] **Step 1: Run full lint**

Run: `uv run ruff check app/`

Expected: clean. 문제 있으면 `uv run ruff check --fix app/`로 자동 정리 후 잔여 issue 수동 해결.

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest app/tests/ -q`

Expected: 전체 PASS.

- [ ] **Step 3: Manual browser check (spec §8 체크리스트)**

`alice.yp@example.com` 로그인:
- 컴팩트 웰컴 strip · 거주자 인증 칩 보임.
- 오늘의 발견 mixed feed 카드 6~8개 노출. 이미지 있는 카드는 thumbnail, journey ep는 「title」 ep N 메타.
- 슬림 매칭 CTA 1행.
- 시군 카드 2~4개 — 활동 있는 시군엔 "이번 주 새 후기 N" 노출.
- FAB 클릭 → 4 entry dropdown.

`dave.yp@example.com` (REGION_VERIFIED) 로그인:
- FAB 후기/Journey 옆 🔒 표시.
- 후기/Journey 클릭 시 `/me/badge`로 이동.

비로그인 방문:
- 기존 marketing landing 1줄도 변경 없음 (hero·4 Pillar·페르소나 카드 등).
- 우하단 FAB 없음.

모바일 viewport(375px):
- 1-col grid.
- FAB이 본문 마지막 카드 가리지 않음 — `pb-24` 덕분에 푸터까지 스크롤하면 FAB과 안 겹침.

- [ ] **Step 4: Branch summary commit (optional)**

변경 사항이 없다면 step skip. spec과 plan 모두 커밋된 상태인지만 확인:

```bash
git status
git log --oneline -15
```

P1.5b "home community pulse" 관련 commit들이 순차적으로 보여야 함 (Task 1~10 각 commit).

---

## 변경 요약 (전체 작업 완료 시점)

- 데이터 모델 변경 **0**, 마이그레이션 **0**.
- 백엔드: `feed.py` 확장 + `analytics.py` enum 4개.
- 프론트엔드: 신규 컴포넌트 3개 + partial 1개, home.html `{% if current_user %}` 블록 재작성, base.html 2줄 변경.
- 테스트: 서비스 7 + 페이지 5 = **신규 12 테스트**.
- 비로그인 마케팅 랜딩 변경 **0**.
- 권한·인증 라우트 변경 **0** (기존 가드 그대로).

PostHog 실제 emit, 매칭 wizard 진행률 UI, FAB safe-area inset 변수 사용은 본 plan **범위 외** — P1.5 통합 작업에서 처리.
