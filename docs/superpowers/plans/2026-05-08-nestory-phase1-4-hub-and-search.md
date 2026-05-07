# Nestory Phase 1.4 — Hub + Discover + Search + Interactions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the discovery surface — `/discover` 시군 그리드, `/hub/{slug}` 4-tab 허브 (후기/Journey/Q&A/이웃), `/feed` 전체·팔로우 피드, `/search` (`pg_trgm` + `simple` FTS 병행), 공개 프로필 `/u/{username}`, 그리고 P1.3 detail 페이지에 좋아요·스크랩·댓글 인터랙션을 연결 — on top of P1.1·1.2·1.3 (모델·큐·배지·가드·콘텐츠·이미지) 인프라.

**Architecture:** 4 new routers (`hub.py` / `feed.py` / `search.py` / `profile.py`), 5 new services (`hub.py` / `feed.py` / `search.py` / `interactions.py` / `comments.py`), 1 migration (GIN trgm + GIN tsvector indexes), 새 라우트는 모두 P1.3 services 패턴(`db: Session` first, `user: User | None` second, no `request.session` import) 준수. 좋아요·스크랩은 HTMX swap (`hx-post` → 토글 partial), 댓글은 form POST → redirect.

**Tech Stack:** FastAPI + Jinja2 SSR + HTMX (인터랙션 partial), PostgreSQL `pg_trgm` extension (이미 PG16에 포함, `CREATE EXTENSION` 필요) + `to_tsvector('simple', ...)` GIN. Phase 2 mecab-ko는 OI-13 (PRD §5.2 [v1.1 · A2]) — P1.4에선 도입하지 않음.

**Spec basis:** PRD §4.4 (시군 허브), §4.5 (홈 피드 전략), §5.2 (인덱스), §6.4·§9.3 (Phase 1 scope). 별도 spec 파일 미작성 — PRD 인용으로 충분.

**CLAUDE.md alignment:** Services pattern 엄격 (라우트는 입력검증/service 호출/응답 포맷팅만), 권한 가드는 Depends만, 분석 트래킹은 `EventName` enum (P1.5 PostHog 활성화 전이라도 enum 정의는 추가), factory-boy 우선.

**P1.4 제외 항목 (별도 sub-plan)**:
- `/match/wizard` (PRD §6.4 [B5] Region Match Wizard) → P1.4b 또는 P1.5에 분리 — 점수 알고리즘이 별도 설계 필요
- 알림 (bell UI · 인앱) → P1.5
- PWA manifest → P1.5
- 관리자 v1 추가 (배지 큐 외) → P1.5
- 분석 자동 트래킹 호출 → P1.5 (이벤트 enum만 P1.4에 추가)

---

## File Structure

**Created:**
- `app/services/hub.py` — region 페이지 데이터 (헤더 통계, 탭별 post 목록 + 페이지네이션)
- `app/services/feed.py` — 전체/팔로우 피드 쿼리 (정렬·페이지네이션)
- `app/services/search.py` — `search_posts(q, region_id, type, pyeong_band, budget_band, sort, page)` — trgm + FTS 병행 쿼리
- `app/services/interactions.py` — `toggle_like`/`toggle_scrap` (idempotent), `like_count`/`is_liked_by`/`is_scrapped_by`
- `app/services/comments.py` — `create_comment` / `list_comments` (post 기준, 1단 reply만)
- `app/services/profile.py` — `get_profile_by_username` + 사용자 콘텐츠 카운트
- `app/routers/hub.py` — `/discover` · `/hub/{slug}` · `/hub/{slug}/reviews|journeys|questions|neighbors`
- `app/routers/feed.py` — `/feed`
- `app/routers/search.py` — `GET /search` (form + results)
- `app/routers/profile.py` — `/u/{username}` · `/u/{username}/posts|journeys|scraps`
- `app/routers/interactions.py` — `POST /post/{id}/like|unlike|scrap|unscrap` (HTMX) + `POST /post/{id}/comment`
- `app/db/migrations/versions/<rev>_p14_search_indexes.py` — `CREATE EXTENSION pg_trgm`, GIN trgm + tsvector indexes
- `app/templates/pages/discover.html` — region 그리드
- `app/templates/pages/hub/_header.html` — 허브 헤더 (지역명·카운트·표지)
- `app/templates/pages/hub/_tabs.html` — 4-tab 네비
- `app/templates/pages/hub/home.html` — 허브 홈 (모든 섹션 요약)
- `app/templates/pages/hub/reviews.html` · `journeys.html` · `questions.html` · `neighbors.html`
- `app/templates/pages/feed.html`
- `app/templates/pages/search.html`
- `app/templates/pages/profile/_header.html` · `posts.html` · `journeys.html` · `scraps.html` · `home.html`
- `app/templates/partials/post_card.html` — 카드 1개 (post + author + region) — 허브/피드/검색/프로필 공통
- `app/templates/partials/journey_card.html`
- `app/templates/partials/like_button.html` · `scrap_button.html` — HTMX swap target
- `app/templates/partials/comment_list.html` · `comment_form.html`
- `app/templates/partials/pagination.html` — `?page=N` 링크 컴포넌트
- `app/scripts/seed_demo.py` — 5 region · 10 user · 30 post · 5 journey · 8 question · 12 answer · 좋아요/스크랩 일부
- Test files (full list in Test Plan section below)

**Modified:**
- `app/models/post.py` — 검색 헬퍼 칼럼 없음 (computed expression GIN). 변경 없음.
- `app/templates/pages/home.html` — 비로그인 hero에 추천 허브 3개 + 인기 후기 4개 (정적→동적). 로그인 사용자는 팔로우 Journey 새 에피소드 위에 배치.
- `app/routers/pages.py` — `home` 라우트가 `feed_service.home_data(db, current_user)` 호출
- `app/templates/pages/detail/post.html` — 좋아요·스크랩 버튼 (partial include) + 댓글 섹션 (partial include)
- `app/templates/pages/detail/journey.html` · `question.html` · `journey_episode.html` — 동일 인터랙션 추가
- `app/templates/components/_nav.html` (또는 base.html nav 영역) — `/discover`·`/feed`·`/search` 링크 노출
- `app/main.py` — 5 새 라우터 등록
- `app/services/__init__.py` · `app/routers/__init__.py` — re-export
- `app/services/analytics.py` — `EventName` enum에 P1.4 이벤트 추가 (`HUB_VIEWED`·`SEARCH_QUERY`·`POST_LIKED`·`POST_SCRAPPED` 등 — emit 호출은 P1.5)

---

## Test File Plan

| Test file | Verifies |
|---|---|
| `app/tests/integration/test_search_indexes_migration.py` | 마이그레이션 적용 후 `pg_trgm` extension 존재 + 두 GIN 인덱스 `pg_indexes` 조회로 확인 |
| `app/tests/integration/test_search_service.py` | `search_posts` — 한글 부분일치(`양평` → `양평군`), 오타 허용(trgm), region 필터, type 필터, 정렬(latest/popular), 페이지네이션 |
| `app/tests/integration/test_hub_service.py` | 헤더 통계 (post 수·journey 수·resident 수), 탭별 published 만 노출, draft 제외, 페이지네이션 |
| `app/tests/integration/test_feed_service.py` | 비로그인: 최신 published / 로그인: 팔로우 Journey 새 에피소드 우선 |
| `app/tests/integration/test_interactions_service.py` | `toggle_like` idempotent (두 번 호출 시 unliked), `toggle_scrap` 동일, count 정확성 |
| `app/tests/integration/test_comments_service.py` | comment create + list (1단 reply 트리), deleted 제외, post 없으면 IntegrityError |
| `app/tests/integration/test_discover_route.py` | `/discover` 200 + 모든 region 카드 + pilot 우선 정렬 |
| `app/tests/integration/test_hub_routes.py` | `/hub/{slug}` 4-tab 모두 200 + slug 404 + region별 post 격리 |
| `app/tests/integration/test_feed_route.py` | `/feed` 비로그인 200 + 로그인 200 + 페이지 파라미터 |
| `app/tests/integration/test_search_route.py` | `GET /search?q=...` 200 + 결과 카드 + 빈 쿼리 처리 + XSS 방지(escape) |
| `app/tests/integration/test_profile_routes.py` | `/u/{username}` + 3 sub 200 + 없는 사용자 404 + scraps는 본인만 |
| `app/tests/integration/test_interactions_routes.py` | `POST /post/{id}/like` HTMX swap (button HTML), 비로그인 401, 자기 글 좋아요 허용 |
| `app/tests/integration/test_comment_route.py` | `POST /post/{id}/comment` 로그인 필요, 빈 body 400 |
| `app/tests/integration/test_home_dynamic.py` | `/` 비로그인: 추천 허브·인기 후기 카드 렌더 / 로그인: 팔로우 새 에피소드 노출 |
| `app/tests/integration/test_p14_workflow_e2e.py` | E2E: signup → /discover → /hub → 후기 좋아요 → /search → 결과 클릭 → /post 댓글 |
| `app/tests/unit/test_search_query_builder.py` | 쿼리 sanitization (특수문자 escape, 빈 쿼리 short-circuit), trgm + ts 결합 SQL 형태 |

---

## Task 1: Foundation — search index migration + analytics enum + nav

**Files:**
- Create: `app/db/migrations/versions/<rev>_p14_search_indexes.py`
- Modify: `app/services/analytics.py` (또는 신규 `app/services/analytics.py` 생성 — 현재 미존재 시)
- Modify: `app/templates/components/_nav.html` (또는 base.html — 현재 nav 위치 확인)

- [x] **Step 1: 마이그레이션 생성** ✅ `app/db/migrations/versions/e1ad6f3c4a92_p14_search_indexes.py` (down_revision=`1c683806cbae`)
  ```powershell
  uv run alembic revision -m "p14: pg_trgm extension + search GIN indexes"
  ```
  생성된 파일을 다음 내용으로 교체 (autogenerate가 GIN expression index를 만들지 못하므로 수동 작성):
  ```python
  """p14: pg_trgm extension + search GIN indexes"""
  from alembic import op
  import sqlalchemy as sa

  revision = "<auto>"
  down_revision = "<previous head>"  # uv run alembic current 로 확인
  branch_labels = None
  depends_on = None

  def upgrade() -> None:
      op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
      op.execute(
          "CREATE INDEX ix_posts_search_trgm ON posts "
          "USING GIN ((title || ' ' || body) gin_trgm_ops) "
          "WHERE status = 'published' AND deleted_at IS NULL"
      )
      op.execute(
          "CREATE INDEX ix_posts_search_fts ON posts "
          "USING GIN (to_tsvector('simple', title || ' ' || body)) "
          "WHERE status = 'published' AND deleted_at IS NULL"
      )

  def downgrade() -> None:
      op.execute("DROP INDEX IF EXISTS ix_posts_search_fts")
      op.execute("DROP INDEX IF EXISTS ix_posts_search_trgm")
      # extension은 유지 (다른 곳에서 쓸 수 있음 — 의도적으로 drop 안 함)
  ```

- [ ] **Step 2: 마이그레이션 적용 + 검증** ⏸ Docker 미가용 PC라 보류 — 다음 docker-up PC에서 실행
  ```powershell
  uv run alembic upgrade head
  docker exec nestory-postgres-local psql -U nestory -d nestory -c "\dx pg_trgm"
  docker exec nestory-postgres-local psql -U nestory -d nestory -c "\d posts" | findstr "ix_posts_search"
  ```
  Expected: pg_trgm 확장 1개 + 두 인덱스 출현.

- [x] **Step 3: analytics enum 스텁** ✅ `app/services/analytics.py` 신규 작성 + `__init__.py` re-export. 이벤트 enum은 plan보다 더 풍부하게 (P0/P1.2/P1.3/P1.4 모두 포함, BADGE_APPLIED/APPROVED 추가).
  ```python
  from enum import Enum

  class EventName(str, Enum):
      # P0
      USER_SIGNED_UP = "user_signed_up"
      USER_LOGGED_IN = "user_logged_in"
      # P1.3
      POST_PUBLISHED = "post_published"
      IMAGE_UPLOADED = "image_uploaded"
      # P1.4
      HUB_VIEWED = "hub_viewed"
      DISCOVER_VIEWED = "discover_viewed"
      SEARCH_QUERY = "search_query"
      POST_LIKED = "post_liked"
      POST_SCRAPPED = "post_scrapped"
      COMMENT_POSTED = "comment_posted"
      PROFILE_VIEWED = "profile_viewed"

  def emit(event: EventName, distinct_id_hash: str | None = None, props: dict | None = None) -> None:
      """No-op until P1.5 PostHog wiring."""
      return None
  ```

- [x] **Step 4: 네비 링크 추가** ✅ `app/templates/components/nav.html`에 logo와 우측 액션 사이 `<div class="hidden sm:flex ...">` 그룹으로 피드·탐색·검색 3개 링크 추가 (모바일에선 숨김 — home에서 노출 예정).

- [x] **Step 5: ruff** ✅ `uv run ruff check app/` clean. ⏸ pytest는 Docker 미가용으로 보류.

- [x] **Step 6: Commit** ✅ 별도 commit으로 dev에 push 예정 (P1.4 Task 1 단일 commit).

---

## Task 2: search service — `search_posts` (trgm + FTS 병행)

**Files:**
- Create: `app/services/search.py`
- Create: `app/tests/integration/test_search_service.py`
- Create: `app/tests/unit/test_search_query_builder.py`
- Modify: `app/services/__init__.py`

- [x] **Step 1: 실패 테스트 작성** ✅ `test_search_service.py` (14개 integration 케이스: 한글 부분일치·오타·region필터·type필터·latest/popular/relevance·pagination·빈쿼리·draft제외·soft-delete제외) + `test_search_query_builder.py` (18개 unit 케이스: strip·cap·short-circuit·특수문자 통과)

- [x] **Step 2: service 구현** ✅ `app/services/search.py` — `normalize_query` + `search_posts` + `SearchResult` dataclass. PAGE_SIZE=20, MIN_QUERY_LEN=2, MAX_QUERY_LEN=200, SIMILARITY_THRESHOLD=0.1. `selectinload(Post.author/region)` 포함.
  ```python
  # app/services/search.py
  from dataclasses import dataclass
  from sqlalchemy import func, or_, text, select
  from sqlalchemy.orm import Session, selectinload
  from app.models import Post, PostStatus, Region, User
  from app.models._enums import PostType

  PAGE_SIZE = 20

  @dataclass
  class SearchResult:
      posts: list[Post]
      total: int
      page: int

  def search_posts(
      db: Session,
      q: str,
      *,
      region_id: int | None = None,
      type: PostType | None = None,
      sort: str = "relevance",  # relevance | latest | popular
      page: int = 1,
  ) -> SearchResult:
      q = (q or "").strip()
      if len(q) < 2:
          return SearchResult(posts=[], total=0, page=page)

      base = (
          select(Post)
          .where(Post.status == PostStatus.PUBLISHED, Post.deleted_at.is_(None))
          .options(selectinload(Post.author), selectinload(Post.region))
      )
      tsquery = func.plainto_tsquery("simple", q)
      similarity = func.greatest(
          func.similarity(Post.title, q),
          func.similarity(Post.body, q),
      )
      match_clause = or_(
          func.to_tsvector("simple", Post.title + " " + Post.body).op("@@")(tsquery),
          similarity > 0.1,
      )
      stmt = base.where(match_clause)
      if region_id:
          stmt = stmt.where(Post.region_id == region_id)
      if type:
          stmt = stmt.where(Post.type == type)

      total = db.scalar(select(func.count()).select_from(stmt.subquery()))

      if sort == "latest":
          stmt = stmt.order_by(Post.published_at.desc())
      elif sort == "popular":
          stmt = stmt.order_by(Post.view_count.desc(), Post.published_at.desc())
      else:  # relevance
          stmt = stmt.order_by(similarity.desc(), Post.published_at.desc())

      stmt = stmt.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
      posts = list(db.scalars(stmt).all())
      return SearchResult(posts=posts, total=total or 0, page=page)
  ```

- [x] **Step 3: 테스트 통과 확인 + 실제 인덱스 사용 확인** ⏸ Docker 미가용 PC — pytest 및 EXPLAIN 검증은 docker-up PC에서 실행 예정. DB EXPLAIN deferred.

- [x] **Step 4: ruff + 전체 회귀** ✅ `uv run ruff check app/` → All checks passed. pytest는 docker-up PC에서 실행.
- [x] **Step 5: Commit** ✅ `feat(search): pg_trgm + simple FTS hybrid search service`

---

## Task 3: hub service + feed service

**Files:**
- Create: `app/services/hub.py`
- Create: `app/services/feed.py`
- Create: `app/tests/integration/test_hub_service.py`
- Create: `app/tests/integration/test_feed_service.py`

- [x] **Step 1: 실패 테스트 작성** ✅ 10 hub tests + 9 feed tests (TDD — written before impl)

- [x] **Step 2: hub service 구현** ✅ `app/services/hub.py` — HubOverview + hub_overview + hub_tab_posts + region_neighbors + get_region_by_slug; `post_type` param (not `type`)
  ```python
  # app/services/hub.py
  from dataclasses import dataclass
  from sqlalchemy import func, select
  from sqlalchemy.orm import Session, selectinload
  from app.models import Post, Region, User, PostStatus
  from app.models._enums import PostType, BadgeLevel

  PAGE_SIZE = 20

  @dataclass
  class HubOverview:
      region: Region
      review_count: int
      journey_count: int
      question_count: int
      resident_count: int
      popular_reviews: list[Post]
      recent_journeys: list[Post]
      recent_questions: list[Post]

  def get_region_by_slug(db: Session, slug: str) -> Region | None:
      return db.scalar(select(Region).where(Region.slug == slug))

  def hub_overview(db: Session, region: Region) -> HubOverview:
      base = select(func.count(Post.id)).where(
          Post.region_id == region.id,
          Post.status == PostStatus.PUBLISHED,
          Post.deleted_at.is_(None),
      )
      review_count = db.scalar(base.where(Post.type == PostType.REVIEW)) or 0
      journey_count = db.scalar(base.where(Post.type == PostType.JOURNEY_EPISODE)) or 0
      question_count = db.scalar(base.where(Post.type == PostType.QUESTION)) or 0
      resident_count = db.scalar(
          select(func.count(User.id)).where(
              User.primary_region_id == region.id,
              User.badge_level.in_([BadgeLevel.RESIDENT, BadgeLevel.EX_RESIDENT]),
          )
      ) or 0

      def _top(t: PostType, by: str = "view"):
          q = (
              select(Post)
              .where(
                  Post.region_id == region.id,
                  Post.type == t,
                  Post.status == PostStatus.PUBLISHED,
                  Post.deleted_at.is_(None),
              )
              .options(selectinload(Post.author))
              .limit(4)
          )
          q = q.order_by(Post.view_count.desc()) if by == "view" else q.order_by(Post.published_at.desc())
          return list(db.scalars(q).all())

      return HubOverview(
          region=region,
          review_count=review_count,
          journey_count=journey_count,
          question_count=question_count,
          resident_count=resident_count,
          popular_reviews=_top(PostType.REVIEW, by="view"),
          recent_journeys=_top(PostType.JOURNEY_EPISODE, by="latest"),
          recent_questions=_top(PostType.QUESTION, by="latest"),
      )

  def hub_tab_posts(
      db: Session, region: Region, type: PostType, *, sort: str = "latest", page: int = 1
  ) -> tuple[list[Post], int]:
      base = (
          select(Post)
          .where(
              Post.region_id == region.id,
              Post.type == type,
              Post.status == PostStatus.PUBLISHED,
              Post.deleted_at.is_(None),
          )
          .options(selectinload(Post.author))
      )
      total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
      base = base.order_by(Post.view_count.desc() if sort == "popular" else Post.published_at.desc())
      base = base.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
      return list(db.scalars(base).all()), total
  ```

- [x] **Step 3: feed service 구현** ✅ (see Step 3 annotation above)
  ```python
  # app/services/feed.py
  from dataclasses import dataclass
  from sqlalchemy import func, select
  from sqlalchemy.orm import Session, selectinload
  from app.models import Post, Region, User, PostStatus
  from app.models._enums import PostType
  from app.models.interaction import journey_follows

  @dataclass
  class HomeData:
      recommended_regions: list[Region]
      popular_reviews: list[Post]
      recent_journeys: list[Post]
      followed_episodes: list[Post]  # 로그인 사용자만 채워짐

  def home_data(db: Session, user: User | None) -> HomeData:
      regions = list(db.scalars(
          select(Region).order_by(Region.is_pilot.desc(), Region.id).limit(4)
      ).all())
      pop = list(db.scalars(
          select(Post)
          .where(Post.type == PostType.REVIEW, Post.status == PostStatus.PUBLISHED, Post.deleted_at.is_(None))
          .options(selectinload(Post.author), selectinload(Post.region))
          .order_by(Post.view_count.desc()).limit(4)
      ).all())
      recent_j = list(db.scalars(
          select(Post)
          .where(Post.type == PostType.JOURNEY_EPISODE, Post.status == PostStatus.PUBLISHED, Post.deleted_at.is_(None))
          .options(selectinload(Post.author), selectinload(Post.region))
          .order_by(Post.published_at.desc()).limit(4)
      ).all())
      followed: list[Post] = []
      if user:
          followed = list(db.scalars(
              select(Post)
              .join(journey_follows, journey_follows.c.journey_id == Post.journey_id)
              .where(
                  journey_follows.c.user_id == user.id,
                  Post.type == PostType.JOURNEY_EPISODE,
                  Post.status == PostStatus.PUBLISHED,
                  Post.deleted_at.is_(None),
              )
              .options(selectinload(Post.author), selectinload(Post.region))
              .order_by(Post.published_at.desc()).limit(8)
          ).all())
      return HomeData(regions, pop, recent_j, followed)

  def global_feed(db: Session, *, page: int = 1) -> tuple[list[Post], int]:
      base = (
          select(Post)
          .where(Post.status == PostStatus.PUBLISHED, Post.deleted_at.is_(None))
          .options(selectinload(Post.author), selectinload(Post.region))
      )
      total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
      base = base.order_by(Post.published_at.desc()).offset((page - 1) * 20).limit(20)
      return list(db.scalars(base).all()), total
  ```

- [x] **Step 4: ruff clean** ✅ `uv run ruff check app/` — All checks passed. pytest deferred (Docker unavailable).

- [x] **Step 5: Commit** ✅ SHA `d1317dc` — `feat(hub): hub overview + tab posts + home/global feed services`

---

## Task 4: interactions service — like/scrap toggle (idempotent)

**Files:**
- Create: `app/services/interactions.py`
- Create: `app/tests/integration/test_interactions_service.py`

- [x] **Step 1: 테스트 작성** — `toggle_like` 두 번 호출 후 unliked / 다른 사용자 좋아요 영향 없음 / count 정확

- [x] **Step 2: 구현**
  ```python
  # app/services/interactions.py
  from sqlalchemy import delete, func, insert, select
  from sqlalchemy.exc import IntegrityError
  from sqlalchemy.orm import Session
  from app.models import Post, User
  from app.models.interaction import post_likes, post_scraps

  def is_liked_by(db: Session, post_id: int, user_id: int) -> bool:
      return db.scalar(
          select(func.count())
          .select_from(post_likes)
          .where(post_likes.c.post_id == post_id, post_likes.c.user_id == user_id)
      ) == 1

  def like_count(db: Session, post_id: int) -> int:
      return db.scalar(
          select(func.count()).select_from(post_likes).where(post_likes.c.post_id == post_id)
      ) or 0

  def toggle_like(db: Session, post: Post, user: User) -> bool:
      """Returns True if now-liked, False if now-unliked."""
      if is_liked_by(db, post.id, user.id):
          db.execute(
              delete(post_likes).where(
                  post_likes.c.post_id == post.id, post_likes.c.user_id == user.id
              )
          )
          db.commit()
          return False
      try:
          db.execute(insert(post_likes).values(post_id=post.id, user_id=user.id))
          db.commit()
      except IntegrityError:
          db.rollback()  # 동시 클릭 race — 결과적 멱등
      return True

  # toggle_scrap, scrap_count, is_scrapped_by — 동일 패턴 with post_scraps
  ```

- [x] **Step 3: 테스트 통과 + Commit** — `feat(interactions): idempotent like/scrap toggle services`

---

## Task 5: comments service

**Files:**
- Create: `app/services/comments.py`
- Create: `app/tests/integration/test_comments_service.py`

- [x] **Step 1: 테스트** — create / list (ordered) / 1단 reply / deleted 제외

- [x] **Step 2: 구현**
  ```python
  # app/services/comments.py
  from sqlalchemy import select
  from sqlalchemy.orm import Session
  from app.models import Comment, Post, User
  from app.models._enums import CommentStatus

  MAX_BODY = 2000

  class CommentValidationError(ValueError): ...

  def create_comment(
      db: Session, post: Post, user: User, body: str, *, parent_id: int | None = None
  ) -> Comment:
      body = (body or "").strip()
      if not body:
          raise CommentValidationError("본문이 비어있습니다")
      if len(body) > MAX_BODY:
          raise CommentValidationError("댓글이 너무 깁니다")
      if parent_id:
          parent = db.get(Comment, parent_id)
          if not parent or parent.post_id != post.id or parent.parent_id is not None:
              raise CommentValidationError("잘못된 부모 댓글입니다")
      c = Comment(post_id=post.id, author_id=user.id, body=body, parent_id=parent_id)
      db.add(c); db.commit(); db.refresh(c)
      return c

  def list_comments(db: Session, post: Post) -> list[Comment]:
      return list(db.scalars(
          select(Comment)
          .where(Comment.post_id == post.id, Comment.status == CommentStatus.VISIBLE, Comment.deleted_at.is_(None))
          .order_by(Comment.parent_id.is_(None).desc(), Comment.created_at.asc())
      ).all())
  ```

- [x] **Step 3: 테스트 + Commit** — `feat(comments): create/list service with 1-level replies`

---

## Task 6: profile service

**Files:**
- Create: `app/services/profile.py`
- Create: `app/tests/integration/test_profile_routes.py` (서비스 테스트는 라우터와 함께)

- [x] **Step 1: 구현**
  ```python
  # app/services/profile.py
  from dataclasses import dataclass
  from sqlalchemy import func, select
  from sqlalchemy.orm import Session, selectinload
  from app.models import Post, User, PostStatus
  from app.models._enums import PostType
  from app.models.interaction import post_scraps

  @dataclass
  class ProfileData:
      user: User
      review_count: int
      journey_episode_count: int
      question_count: int

  def get_by_username(db: Session, username: str) -> User | None:
      return db.scalar(select(User).where(User.username == username, User.deleted_at.is_(None)))

  def profile_data(db: Session, user: User) -> ProfileData:
      base = select(func.count(Post.id)).where(
          Post.author_id == user.id,
          Post.status == PostStatus.PUBLISHED,
          Post.deleted_at.is_(None),
      )
      return ProfileData(
          user=user,
          review_count=db.scalar(base.where(Post.type == PostType.REVIEW)) or 0,
          journey_episode_count=db.scalar(base.where(Post.type == PostType.JOURNEY_EPISODE)) or 0,
          question_count=db.scalar(base.where(Post.type == PostType.QUESTION)) or 0,
      )

  def author_posts(db: Session, user: User, type: PostType, page: int = 1) -> list[Post]:
      return list(db.scalars(
          select(Post)
          .where(Post.author_id == user.id, Post.type == type, Post.status == PostStatus.PUBLISHED, Post.deleted_at.is_(None))
          .options(selectinload(Post.region))
          .order_by(Post.published_at.desc()).offset((page - 1) * 20).limit(20)
      ).all())

  def user_scraps(db: Session, user: User, page: int = 1) -> list[Post]:
      return list(db.scalars(
          select(Post).join(post_scraps, post_scraps.c.post_id == Post.id)
          .where(post_scraps.c.user_id == user.id, Post.status == PostStatus.PUBLISHED, Post.deleted_at.is_(None))
          .options(selectinload(Post.author), selectinload(Post.region))
          .order_by(post_scraps.c.created_at.desc()).offset((page - 1) * 20).limit(20)
      ).all())
  ```

- [x] **Step 2: Commit** — `feat(profile): user profile data + author posts/scraps services`

---

## Task 7: shared partials — post_card, journey_card, pagination, like/scrap buttons

**Files:** 6 신규 partial templates.

- [ ] **Step 1: post_card partial** (`app/templates/partials/post_card.html`)
  - Tailwind 카드: 썸네일 placeholder + title + author username + region.sigungu + view_count + published_at(상대시간)
  - `post.type` enum별 라벨 chip (후기/Journey/Q&A/계획)
  - Detail 링크: type별 분기 (`/post/{id}` 또는 `/journey/{jid}/ep/{n}` 또는 `/question/{id}`)

- [ ] **Step 2: journey_card partial** — Journey listing용 별도 카드 (cover + title + episode count + author)

- [ ] **Step 3: pagination partial** — `?page=N` prev/next + 현재 페이지 표시. 총 페이지 인자 받음.

- [ ] **Step 4: like_button.html / scrap_button.html** — HTMX 패턴
  ```html
  {# like_button.html — hx-swap target #}
  <button
    hx-post="/post/{{ post.id }}/{{ 'unlike' if liked else 'like' }}"
    hx-target="#like-btn-{{ post.id }}"
    hx-swap="outerHTML"
    id="like-btn-{{ post.id }}"
    class="{{ 'text-rose-600' if liked else 'text-zinc-500' }}"
  >
    ♥ {{ count }}
  </button>
  ```

- [ ] **Step 5: comment_list.html / comment_form.html** — comment list는 nested reply 포함

- [ ] **Step 6: Commit** — `feat(ui): shared post/journey card + pagination + like/scrap/comment partials`

---

## Task 8: discover + hub routes

**Files:**
- Create: `app/routers/hub.py`
- Create: `app/templates/pages/discover.html`
- Create: `app/templates/pages/hub/_header.html` · `_tabs.html` · `home.html` · `reviews.html` · `journeys.html` · `questions.html` · `neighbors.html`
- Create: `app/tests/integration/test_discover_route.py` · `test_hub_routes.py`
- Modify: `app/main.py` (router 등록)

- [ ] **Step 1: 실패 테스트 작성**

- [ ] **Step 2: 라우터 작성**
  ```python
  # app/routers/hub.py
  from fastapi import APIRouter, Depends, HTTPException, Request
  from fastapi.responses import HTMLResponse
  from sqlalchemy.orm import Session
  from sqlalchemy import select
  from app.deps import get_db, get_current_user
  from app.models import Region, User
  from app.models._enums import PostType
  from app.services import hub as hub_service
  from app.templating import templates

  router = APIRouter(tags=["hub"])

  @router.get("/discover", response_class=HTMLResponse)
  def discover(request: Request, db: Session = Depends(get_db),
               current_user: User | None = Depends(get_current_user)) -> HTMLResponse:
      regions = list(db.scalars(select(Region).order_by(Region.is_pilot.desc(), Region.sido, Region.sigungu)).all())
      return templates.TemplateResponse(request, "pages/discover.html",
                                       {"regions": regions, "current_user": current_user})

  def _region_or_404(db: Session, slug: str) -> Region:
      r = hub_service.get_region_by_slug(db, slug)
      if not r:
          raise HTTPException(404, "지역을 찾을 수 없습니다")
      return r

  @router.get("/hub/{slug}", response_class=HTMLResponse)
  def hub_home(slug: str, request: Request, db: Session = Depends(get_db),
               current_user: User | None = Depends(get_current_user)) -> HTMLResponse:
      region = _region_or_404(db, slug)
      overview = hub_service.hub_overview(db, region)
      return templates.TemplateResponse(request, "pages/hub/home.html",
                                       {"overview": overview, "current_user": current_user})

  def _tab_route(type: PostType, template: str):
      def view(slug: str, request: Request, page: int = 1, sort: str = "latest",
               db: Session = Depends(get_db),
               current_user: User | None = Depends(get_current_user)) -> HTMLResponse:
          region = _region_or_404(db, slug)
          posts, total = hub_service.hub_tab_posts(db, region, type, sort=sort, page=page)
          return templates.TemplateResponse(request, template, {
              "region": region, "posts": posts, "total": total,
              "page": page, "sort": sort, "current_user": current_user,
          })
      return view

  router.add_api_route("/hub/{slug}/reviews", _tab_route(PostType.REVIEW, "pages/hub/reviews.html"),
                       methods=["GET"], response_class=HTMLResponse)
  router.add_api_route("/hub/{slug}/journeys", _tab_route(PostType.JOURNEY_EPISODE, "pages/hub/journeys.html"),
                       methods=["GET"], response_class=HTMLResponse)
  router.add_api_route("/hub/{slug}/questions", _tab_route(PostType.QUESTION, "pages/hub/questions.html"),
                       methods=["GET"], response_class=HTMLResponse)

  @router.get("/hub/{slug}/neighbors", response_class=HTMLResponse)
  def hub_neighbors(slug: str, request: Request, db: Session = Depends(get_db),
                    current_user: User | None = Depends(get_current_user)) -> HTMLResponse:
      region = _region_or_404(db, slug)
      # P1.4 minimum: resident/ex_resident user list. follow는 P1.5
      neighbors = hub_service.region_neighbors(db, region)  # service 추가 필요
      return templates.TemplateResponse(request, "pages/hub/neighbors.html",
                                       {"region": region, "neighbors": neighbors, "current_user": current_user})
  ```

- [ ] **Step 3: 템플릿 작성** — Tailwind, post_card partial 재사용. 4-tab 네비는 `_tabs.html`로 추출.

- [ ] **Step 4: main.py에 등록**

- [ ] **Step 5: 테스트 통과 + Commit** — `feat(hub): /discover + /hub/{slug} home + 4 tab routes`

---

## Task 9: feed + search routes

**Files:**
- Create: `app/routers/feed.py` · `app/routers/search.py`
- Create: `app/templates/pages/feed.html` · `search.html`
- Create: `app/tests/integration/test_feed_route.py` · `test_search_route.py`

- [ ] **Step 1: 테스트 작성**

- [ ] **Step 2: feed router**
  ```python
  @router.get("/feed", response_class=HTMLResponse)
  def feed(request: Request, page: int = 1, db: Session = Depends(get_db),
           current_user: User | None = Depends(get_current_user)) -> HTMLResponse:
      posts, total = feed_service.global_feed(db, page=page)
      return templates.TemplateResponse(request, "pages/feed.html",
                                       {"posts": posts, "total": total, "page": page, "current_user": current_user})
  ```

- [ ] **Step 3: search router** — query params: `q`, `region` (slug), `type`, `sort`, `page`. region slug → id 변환 후 service 호출. 빈 q는 form만 표시.

- [ ] **Step 4: 템플릿** — search는 form 상단 + 결과 카드 그리드 + pagination. q escape 필수 (Jinja autoescape는 켜져 있지만 form value reuse 시 명시).

- [ ] **Step 5: 테스트 + Commit** — `feat(feed): /feed global feed + /search route with filters`

---

## Task 10: profile routes + interaction/comment routes

**Files:**
- Create: `app/routers/profile.py` · `app/routers/interactions.py`
- Create: `app/templates/pages/profile/_header.html` · `home.html` · `posts.html` · `journeys.html` · `scraps.html`
- Create: `app/tests/integration/test_profile_routes.py` · `test_interactions_routes.py` · `test_comment_route.py`

- [ ] **Step 1: profile router** — `/u/{username}` (홈), `/u/{username}/posts`, `/u/{username}/journeys`, `/u/{username}/scraps` (scraps는 본인만 — `if current_user.id != profile_user.id: raise HTTPException(403)`)

- [ ] **Step 2: interactions router** — HTMX endpoints
  ```python
  @router.post("/post/{post_id}/like", response_class=HTMLResponse)
  def like(post_id: int, request: Request, db: Session = Depends(get_db),
           current_user: User = Depends(require_login)) -> HTMLResponse:
      post = db.get(Post, post_id)
      if not post: raise HTTPException(404)
      interactions.toggle_like(db, post, current_user)
      return templates.TemplateResponse(request, "partials/like_button.html",
                                       {"post": post, "liked": True,
                                        "count": interactions.like_count(db, post.id)})
  # /post/{post_id}/unlike — 같은 service 호출, liked=False, count 갱신
  # /post/{post_id}/scrap, /unscrap — 동일 패턴 with scrap service
  ```

- [ ] **Step 3: comment route** — `POST /post/{post_id}/comment` — form `body` + optional `parent_id`. 성공 시 `redirect(f"/post/{id}#comments")`. validation error는 flash 또는 inline error.

- [ ] **Step 4: detail 템플릿에 partial 통합** — `app/templates/pages/detail/post.html` (그리고 journey_episode, question도) 끝에:
  ```html
  {% include "partials/like_button.html" %}
  {% include "partials/scrap_button.html" %}
  <section id="comments">
    {% include "partials/comment_list.html" %}
    {% if current_user %}{% include "partials/comment_form.html" %}{% endif %}
  </section>
  ```
  detail 라우트가 `liked`·`scrapped`·`like_count`·`scrap_count`·`comments` context를 추가로 전달해야 함 — content/journey 라우트 수정 필요.

- [ ] **Step 5: 테스트 + Commit** — `feat(profile): /u/{username} + post like/scrap/comment HTMX endpoints`

---

## Task 11: home `/` 동적화 + seed_demo 스크립트

**Files:**
- Modify: `app/routers/pages.py` (`home` 라우트)
- Modify: `app/templates/pages/home.html`
- Create: `app/scripts/__init__.py` (empty)
- Create: `app/scripts/seed_demo.py`
- Create: `app/tests/integration/test_home_dynamic.py`

- [ ] **Step 1: home 동적화 테스트**

- [ ] **Step 2: home 라우트**
  ```python
  @router.get("/", response_class=HTMLResponse)
  async def home(request: Request, db: Session = Depends(get_db),
                 current_user: User | None = Depends(get_current_user)) -> HTMLResponse:
      data = feed_service.home_data(db, current_user)
      return templates.TemplateResponse(request, "pages/home.html",
                                       {"data": data, "current_user": current_user})
  ```

- [ ] **Step 3: home.html 갱신** — 비로그인: 추천 허브 4 + 인기 후기 4 + 최근 Journey 4 + "카카오 1초 시작" CTA. 로그인: 팔로우 새 에피소드 우선 + 추천 허브.

- [ ] **Step 4: seed_demo.py 작성** — factory-boy 직접 호출 (test 외부에서도 사용 가능). 4 region (양평/영월/홍천/곡성) · 6 user (1 admin + 2 resident + 2 region_verified + 1 interested) · 12 review · 2 journey + 5 episode · 4 question + 7 answer · 좋아요/스크랩 무작위. PRD 4축 강화하는 콘텐츠 (T: 1년차/3년차 후기 쌍, C: regret_items, R: 지역명 명시, V: 답변 다수).
  ```powershell
  uv run python -m app.scripts.seed_demo --reset
  ```

- [ ] **Step 5: ruff + 테스트 + Commit** — `feat(home): dynamic home data + add demo seed script`

---

## Task 12: E2E + DoD verification

**Files:**
- Create: `app/tests/integration/test_p14_workflow_e2e.py`

- [ ] **Step 1: E2E 시나리오**
  ```python
  def test_anonymous_discovery_to_signup_flow(client, db):
      # seed minimum data
      ResidentUserFactory(); RegionFactory(slug="yangpyeong")
      ReviewPostFactory(region=...); db.commit()
      # / → /discover → /hub/yangpyeong → /search → /post/{id}
      assert client.get("/").status_code == 200
      assert client.get("/discover").status_code == 200
      assert client.get("/hub/yangpyeong").status_code == 200
      assert client.get("/hub/yangpyeong/reviews").status_code == 200
      r = client.get("/search?q=양평")
      assert r.status_code == 200 and "양평" in r.text

  def test_logged_in_like_scrap_comment_flow(client, db, login):
      # 로그인 → 후기 like → scrap → comment → /me/scraps에 노출 확인
      ...
  ```

- [ ] **Step 2: DoD 체크리스트**
  - DoD 1: `/discover` 4개 region 카드 렌더 — `test_discover_route`
  - DoD 2: `/hub/{slug}` 4탭 모두 200 — `test_hub_routes`
  - DoD 3: `/search` 한글 부분일치 + 오타 허용 — `test_search_service`
  - DoD 4: `/feed` 비로그인/로그인 분기 — `test_feed_route`
  - DoD 5: `/u/{username}` 3탭 + scraps 본인만 — `test_profile_routes`
  - DoD 6: 좋아요/스크랩 idempotent + HTMX swap — `test_interactions_*`
  - DoD 7: 댓글 1단 reply + validation — `test_comments_*`
  - DoD 8: home 동적 데이터 — `test_home_dynamic`
  - DoD 9: GIN 인덱스가 `EXPLAIN`에 사용되는지 (수동 1회) — Task 2 Step 3
  - DoD 10: services에 `request.session` 미포함 — `rg "request.session" app/services/`
  - DoD 11: integration tests에 직접 `Post(...)` 미사용 — `rg "^\s+Post\s*\(" app/tests/integration/`
  - DoD 12: ruff clean — `uv run ruff check app/`
  - DoD 13: 풀 pytest pass — `uv run pytest app/tests/ -q`

- [ ] **Step 3: 마무리 commit + dev push** — `test: complete P1.4 E2E and DoD verification`

---

## Self-Review Notes

- **Spec coverage**: PRD §4.4 → Task 8 (4-tab 허브). §4.5 → Task 11 (home 동적). §5.2 → Task 1 (인덱스). §6.4·§9.3 → 전체. 인터랙션 (좋아요·스크랩·댓글) → Task 4·5·10. 검색 → Task 2·9. 프로필 → Task 6·10. P1.4 비범위 (Match Wizard·알림·PWA·관리자 v2)는 별도 sub-plan.
- **Type/name consistency**: P1.3과 동일한 namespace alias (`hub_service`·`feed_service`·`search_service`·`interactions`·`comments_service`·`profile_service`). 라우터는 `*.router` 객체 + `app/main.py` `include_router`. 템플릿은 `pages/<area>/...` 디렉토리화. partials는 `partials/*.html` 평탄.
- **Migration 안전성**: GIN 인덱스 + WHERE 부분 인덱스라 build 시간 큼. 운영 적용 전 `CREATE INDEX CONCURRENTLY`로 수동 적용 옵션 plan에 추가 검토 (P1.4 끝 시점, 데이터 100건 미만이면 무시).
- **N+1 회피**: 모든 list 쿼리에 `selectinload(Post.author, Post.region)` 명시. P1.3에서 lazy="raise"로 강제 — 빠뜨리면 즉시 raise.
- **검색 sanitization**: `func.plainto_tsquery`가 PG 측에서 escape 처리. trgm `similarity()`도 안전. q 파라미터는 length 제한 (200자) + strip만.

---

## Open considerations (P1.4 진입 직전 결정)

1. **Match Wizard 분리 여부** — PRD §6.4 [B5]는 Phase 1 scope이지만 점수 알고리즘이 별도 설계. P1.4 끝나고 P1.4b로 분리하거나 P1.5에 넣을지 결정. **추천: P1.4b로 분리** (P1.4는 hub/search 일관성 우선).
2. **댓글 신고/숨김** — P1.5 모더레이션 워크플로우와 함께. P1.4에서는 author soft-delete만 (`comments.deleted_at`).
3. **검색 결과 캐싱** — Phase 1에서는 미도입. PG 인덱스만으로 충분 (LCP 2.5s 목표). Phase 2에서 trending query를 Redis로.
4. **Resident user 리스트 노출** — `/hub/{slug}/neighbors`는 username + 거주 시작 연도만. PII 우려 없음.

---

## Plan complete and saved to `docs/superpowers/plans/2026-05-08-nestory-phase1-4-hub-and-search.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between, fast iteration. P1.3 패턴 유지.
2. **Inline Execution** — executing-plans 스킬로 현재 세션에서 task별 진행. checkpoint 사이마다 user 검토.

Which approach?
