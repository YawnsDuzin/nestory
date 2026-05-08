# Sample Content Seeding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** P1.4 종료 후 dogfood 가치 회복 — `seed_demo.py`에 PLAN type 4개 + Picsum 1-3장 이미지(review/journey ep) + 댓글 시딩 추가, `--reset`이 `media/images/` 폴더 청소.

**Architecture:** 새 모듈 `app/scripts/seed_assets/picsum.py`가 httpx 기반 Picsum 다운로드 + 기존 `app.services.images.{strip_exif, store_original}` 재사용 + 워커 핸들러 `handle_image_resize`를 dispatch 우회 sync 호출 + body markdown 자동 삽입. `seed_demo.py`는 PLAN/댓글/이미지 첨부를 호출만.

**Tech Stack:** httpx (이미 kakao OAuth로 의존성), Pillow (이미 image pipeline), factory-boy (PlanPostFactory·CommentFactory 이미 존재).

**Spec basis:** `docs/superpowers/specs/2026-05-08-nestory-sample-content-seeding-design.md`.

**CLAUDE.md alignment:** seed_demo는 services 레이어 직접 호출 (라우트 우회 OK — script). factory-boy 우선 (모든 글/댓글은 Factory). 일관성 — 기존 seed_demo 패턴 유지.

**Test 전략:** 이 작업은 script utility라 unit test 비용 대비 가치가 낮음. 대신 **smoke test (T7)** — 실제 `seed_demo --reset` 실행하여 exit 0 + DB 카운트 검증 + media 폴더 파일 존재 검증으로 DoD 달성. pytest baseline (현재 403 pass)에는 영향 없어야 함 (모듈 import 변경 X).

**Spec 정정:** spec에서 "var/uploads" → 실제 경로는 `settings.image_base_path = "./media"` (== `./media/images/<id>/...`). plan은 정확한 경로 사용.

---

## File Structure

**Created:**
- `app/scripts/seed_assets/__init__.py` — 빈 패키지 마커
- `app/scripts/seed_assets/picsum.py` — `download_and_attach(db, post, count, base_seed, failure_counter)` + 내부 helper

**Modified:**
- `app/scripts/seed_demo.py`:
  - `--reset` 시 `media/images/` 폴더 청소
  - PLAN type 4개 추가 (interested 작성, 0-1 이미지)
  - review·journey ep 루프에서 `download_and_attach` 호출 (1-3 이미지)
  - 댓글 시딩 (review·journey ep 각각 0-3 top + 30% 1 reply)
  - 마지막 SUMMARY에 comments·images 카운트 추가

---

## Task 1: seed_assets 패키지 + Picsum 단일 fetch helper

**Files:**
- Create: `app/scripts/seed_assets/__init__.py`
- Create: `app/scripts/seed_assets/picsum.py`

- [ ] **Step 1: 빈 패키지 마커 생성**

```bash
# Create empty __init__.py
```

`app/scripts/seed_assets/__init__.py`:

```python
"""Seed asset helpers — Picsum image fetch + pipeline integration."""
```

- [ ] **Step 2: picsum.py 초기 골격 + `_fetch_picsum`**

`app/scripts/seed_assets/picsum.py`:

```python
"""Picsum random-image download + image pipeline integration for demo seeding."""
from __future__ import annotations

import warnings
from io import BytesIO
from typing import Final

import httpx
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.models import Image, Post, User
from app.services import images as image_service
from app.workers.handlers.image_resize import handle_image_resize

PICSUM_BASE: Final = "https://picsum.photos"
DEFAULT_W: Final = 1280
DEFAULT_H: Final = 720
TIMEOUT_S: Final = 5.0
MAX_FAILURES: Final = 10


class SeedAbort(RuntimeError):
    """Raised when accumulated Picsum failures exceed MAX_FAILURES."""


def _fetch_picsum(seed: int, *, w: int = DEFAULT_W, h: int = DEFAULT_H) -> bytes | None:
    """Download one image. Returns JPEG bytes, or None on any failure."""
    url = f"{PICSUM_BASE}/{w}/{h}?random={seed}"
    try:
        resp = httpx.get(url, timeout=TIMEOUT_S, follow_redirects=True)
        resp.raise_for_status()
        return resp.content
    except httpx.HTTPError as e:
        warnings.warn(f"Picsum fetch failed (seed={seed}): {e}", stacklevel=2)
        return None
```

- [ ] **Step 3: import 검증**

Run: `uv run python -c "from app.scripts.seed_assets.picsum import _fetch_picsum, SeedAbort; print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add app/scripts/seed_assets/__init__.py app/scripts/seed_assets/picsum.py
git commit -m "feat(seed): scaffold seed_assets package + Picsum fetch helper"
```

---

## Task 2: `attach_image` + `download_and_attach`

**Files:**
- Modify: `app/scripts/seed_assets/picsum.py`

- [ ] **Step 1: `attach_image` 추가**

`app/scripts/seed_assets/picsum.py` 끝에 append:

```python
def attach_image(db: Session, owner: User, raw: bytes) -> Image | None:
    """Push raw bytes through the image pipeline.

    Re-uses `app.services.images.strip_exif` + `store_original`, then invokes
    `handle_image_resize` synchronously (bypassing the queue) so the resulting
    Image row reaches `status=READY` before this function returns.

    The worker handler opens its own SessionLocal — we MUST commit the new
    Image row first so the handler can SELECT it. Returns the refreshed Image
    or None on failure.
    """
    try:
        with PILImage.open(BytesIO(raw)) as src:
            width, height = src.size
        mime = "image/jpeg"  # Picsum delivers JPEG
        cleaned = image_service.strip_exif(raw, mime)
        img = image_service.store_original(db, owner, cleaned, "jpg", width, height)
        db.commit()  # so worker handler's session can read this row
        handle_image_resize({"image_id": img.id})
        db.refresh(img)  # pick up status=READY + thumb/medium paths
        return img
    except Exception as e:  # noqa: BLE001  — best-effort seeder
        warnings.warn(f"attach_image failed: {e}", stacklevel=2)
        return None
```

- [ ] **Step 2: `download_and_attach` 추가**

`app/scripts/seed_assets/picsum.py` 끝에 append:

```python
def download_and_attach(
    db: Session,
    post: Post,
    count: int,
    *,
    base_seed: int,
    failure_counter: list[int],
) -> int:
    """Fetch `count` images, attach to post, append `![](/img/<id>/orig)` to body.

    `failure_counter` is a single-element list used as a mutable int across calls
    (callers reuse one counter across the whole seed run). Raises SeedAbort if
    cumulative failures reach MAX_FAILURES. Returns count of successfully
    attached images.
    """
    refs: list[str] = []
    for i in range(count):
        if failure_counter[0] >= MAX_FAILURES:
            raise SeedAbort(
                f"Picsum 누적 실패 ≥ {MAX_FAILURES}회. 네트워크/방화벽/프록시 점검."
            )
        raw = _fetch_picsum(base_seed + i)
        if raw is None:
            failure_counter[0] += 1
            continue
        img = attach_image(db, post.author, raw)
        if img is None:
            failure_counter[0] += 1
            continue
        refs.append(f"![](/img/{img.id}/orig)")
    if refs:
        post.body = (post.body or "") + "\n\n" + "\n\n".join(refs)
        db.flush()
    return len(refs)
```

- [ ] **Step 3: import 검증 + 정적 분석**

Run: `uv run python -c "from app.scripts.seed_assets.picsum import attach_image, download_and_attach; print('ok')"`
Expected: `ok`

Run: `uv run ruff check app/scripts/seed_assets/`
Expected: `All checks passed!`

- [ ] **Step 4: Commit**

```bash
git add app/scripts/seed_assets/picsum.py
git commit -m "feat(seed): attach_image + download_and_attach (sync image pipeline)"
```

---

## Task 3: `--reset` 시 `media/images/` 청소

**Files:**
- Modify: `app/scripts/seed_demo.py:57-66` (`_truncate_all`)

- [ ] **Step 1: 헬퍼 추가 + `_truncate_all` 호출 직후에 작동**

`app/scripts/seed_demo.py` import 영역에 추가:

```python
import shutil
from pathlib import Path
```

그리고 `_truncate_all` 함수 직후에 새 함수 추가:

```python
def _clean_media(image_base_path: str) -> None:
    """Wipe `<image_base_path>/images/` so re-seeded image rows have no orphan files."""
    images_dir = Path(image_base_path) / "images"
    if images_dir.exists():
        shutil.rmtree(images_dir)
    images_dir.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 2: `seed(reset=True)` 흐름에 호출 삽입**

기존 `seed(...)` 함수의 reset 분기:

```python
if reset:
    _truncate_all(session)
    print("Truncated all tables.")
```

를 다음으로 교체:

```python
if reset:
    _truncate_all(session)
    print("Truncated all tables.")
    from app.config import get_settings
    _clean_media(get_settings().image_base_path)
    print(f"Cleaned media directory: {get_settings().image_base_path}/images/")
```

- [ ] **Step 3: 동작 검증**

Run: `mkdir -p media/images/dummy && touch media/images/dummy/test.jpg && ls media/images/dummy/`
Expected: `test.jpg`

Run: `uv run python -m app.scripts.seed_demo --reset 2>&1 | head -5`
Expected: 첫 줄에 `Truncated all tables.`, 다음 줄에 `Cleaned media directory: ./media/images/`

Run: `ls media/images/`
Expected: 빈 디렉토리 (dummy 폴더 사라짐)

- [ ] **Step 4: Commit**

```bash
git add app/scripts/seed_demo.py
git commit -m "feat(seed): --reset wipes media/images/ for clean re-seed"
```

---

## Task 4: PLAN type 4개 추가

**Files:**
- Modify: `app/scripts/seed_demo.py` (factories import + 새 PLAN 블록)

- [ ] **Step 1: PlanPostFactory import 추가**

`app/scripts/seed_demo.py`의 factories import 블록을 다음으로 확장:

```python
from app.tests.factories import (
    AdminUserFactory,
    AnswerPostFactory,
    CommentFactory,
    JourneyEpisodePostFactory,
    JourneyFactory,
    PilotRegionFactory,
    PlanPostFactory,
    QuestionPostFactory,
    RegionVerifiedUserFactory,
    ResidentUserFactory,
    ReviewPostFactory,
    UserFactory,
    add_post_like,
    add_post_scrap,
)
```

- [ ] **Step 2: PLAN 4개 시드 블록 추가**

`# 4 questions + 7 answers` 블록 *직전*에 새 PLAN 블록 삽입:

```python
        # 4 PLAN posts — interested user reviewing options
        plan_data = [
            (
                "양평 동향 검토 — 3개 부지 비교 중",
                "가족 4인, 예산 5억. 2027년 봄 이주 검토. 동향 단지 3곳 후보, 일조량/접근성/단지내 학교 비교 중입니다.",
                regions["yangpyeong"],
            ),
            (
                "곡성 1년 이내 이주 계획",
                "은퇴 부부, 2026년 가을 입주 목표. 60평 단층, 텃밭 200평 포함. 시공사 추천 받고 있습니다.",
                regions["gokseong"],
            ),
            (
                "홍천 vs 영월, 어디로 할까?",
                "둘 다 강원도, 둘 다 자연 좋습니다. 인터넷·의료·접근성 비교 의견 부탁드려요.",
                regions["hongcheon"],
            ),
            (
                "은퇴 5년 후, 단독 vs 듀플렉스",
                "자녀 가구 합산 가능성 검토. 단독 1동(60평) vs 듀플렉스(40평+30평) 어느 쪽이 현실적일지.",
                regions["yeongwol"],
            ),
        ]
        plans = []
        for title, body, region in plan_data:
            plans.append(
                PlanPostFactory(
                    author=interested,
                    region=region,
                    title=title,
                    body=body,
                    status=PostStatus.PUBLISHED,
                    published_at=_now() - timedelta(days=random.randint(1, 30)),
                    view_count=random.randint(5, 80),
                )
            )
```

- [ ] **Step 3: 마지막 SUMMARY에 PLAN 카운트 추가**

기존 SUMMARY:

```python
        print(f"  ↳ Reviews: {_count(Post.type == PostType.REVIEW)}")
        print(f"  ↳ Journey episodes: {_count(Post.type == PostType.JOURNEY_EPISODE)}")
        print(f"  ↳ Questions: {_count(Post.type == PostType.QUESTION)}")
        print(f"  ↳ Answers: {_count(Post.type == PostType.ANSWER)}")
```

다음 줄을 추가:

```python
        print(f"  ↳ Plans: {_count(Post.type == PostType.PLAN)}")
```

- [ ] **Step 4: 동작 검증**

Run: `uv run python -m app.scripts.seed_demo --reset 2>&1 | tail -10`
Expected: SUMMARY 출력에 `↳ Plans: 4` 포함

- [ ] **Step 5: Commit**

```bash
git add app/scripts/seed_demo.py
git commit -m "feat(seed): add 4 PLAN posts (interested user) + summary line"
```

---

## Task 5: 댓글 시딩 (review·journey ep)

**Files:**
- Modify: `app/scripts/seed_demo.py` — Likes/scraps 블록 직전에 댓글 블록 추가

- [ ] **Step 1: 댓글 블록 추가**

기존 `# Likes + scraps — random sprinkle` 블록 *직전*에 다음 블록 삽입:

```python
        # Comments — 0-3 top-level + ~30% 1-level reply per review/journey ep
        commenter_pool = [resident_a, resident_b, rv_a, rv_b]
        ep_posts = [
            p for p in session.query(Post).filter(
                Post.type == PostType.JOURNEY_EPISODE,
                Post.status == PostStatus.PUBLISHED,
            ).all()
        ]
        commentable = list(reviews) + ep_posts
        for post in commentable:
            top_count = random.randint(0, 3)
            for _ in range(top_count):
                top = CommentFactory(
                    post=post,
                    author=random.choice(commenter_pool),
                )
                if random.random() < 0.30:
                    CommentFactory(
                        post=post,
                        author=random.choice(commenter_pool),
                        parent=top,
                    )
```

또한 import 영역에 `Post`가 이미 있는지 확인 — SUMMARY 블록에서 `from app.models import Post, Region, User`로 늦게 import 됨. 댓글 블록은 그 import보다 위에 있으므로, **댓글 블록 시작 직전에** 다음 import를 추가:

```python
        from app.models import Post  # for the JOURNEY_EPISODE query above
```

(또는 파일 상단으로 끌어올리고 SUMMARY 블록의 중복 import 라인은 제거 — 후자를 권장).

권장 cleanup: 파일 상단 import 그룹에 추가:

```python
from app.models import Post
```

그리고 SUMMARY 블록의 `from app.models import Post, Region, User`을 `from app.models import Region, User`로 축소.

- [ ] **Step 2: SUMMARY에 comments 카운트 추가**

기존 SUMMARY:

```python
        print(f"  ↳ Plans: {_count(Post.type == PostType.PLAN)}")
```

직후에 추가:

```python
        from app.models import Comment
        comment_total = session.scalar(select(func.count(Comment.id)))
        print(f"  Comments: {comment_total}")
```

- [ ] **Step 3: 동작 검증**

Run: `uv run python -m app.scripts.seed_demo --reset 2>&1 | tail -10`
Expected: SUMMARY 출력에 `Comments: <0~70 사이 정수>` 포함 (12 review + 5 journey ep × 0-3 + 30% reply)

- [ ] **Step 4: Commit**

```bash
git add app/scripts/seed_demo.py
git commit -m "feat(seed): seed 0-3 comments per review/journey ep + 30% 1-level reply"
```

---

## Task 6: review · journey ep 이미지 첨부

**Files:**
- Modify: `app/scripts/seed_demo.py` — review 루프 + journey ep 루프 + PLAN 루프 + SUMMARY

- [ ] **Step 1: 이미지 시딩 import + failure counter 초기화**

파일 상단 import 영역에 추가:

```python
from app.scripts.seed_assets.picsum import download_and_attach
```

`seed(...)` 함수 시작 부근 (`session = SessionLocal()` 직후, `_bind_session(session)` 직후) 에 다음 추가:

```python
    failure_counter = [0]  # mutable cumulative failure counter for download_and_attach
    base_seed_counter = [1000]  # increments per attach call
```

- [ ] **Step 2: review 루프에 첨부 호출 추가**

**Important note:** `download_and_attach` signature was amended in commit `301799d` to accept explicit `owner: User`. New positional signature: `(db, post, owner, count, *, base_seed, failure_counter)`. The caller MUST pass the same user variable used to create the post — `post.author` would raise `InvalidRequestError` (lazy='raise').

기존 review 생성 루프 (review_data 사용 + 패딩 generic 둘 다):

```python
for i, (title, body) in enumerate(review_data):
    author = resident_a if i % 2 == 0 else resident_b
    ...
    reviews.append(ReviewPostFactory(author=author, ...))

# Pad to 12 with shorter generic reviews
for _ in range(12 - len(reviews)):
    author = random.choice([resident_a, resident_b])
    ...
    reviews.append(ReviewPostFactory(author=author, ...))
```

각 ReviewPostFactory 직후에 다음 한 블록 추가 (양쪽 루프 모두) — `author` 변수가 이미 scope에 있으니 그대로 전달:

```python
        review = reviews[-1]
        n = random.randint(1, 3)
        download_and_attach(
            session, review, author, n,
            base_seed=base_seed_counter[0],
            failure_counter=failure_counter,
        )
        base_seed_counter[0] += 10
```

- [ ] **Step 3: journey episode 루프에 첨부 호출 추가**

기존 journey_yp 에피소드 루프 + journey_hc 에피소드 루프 모두에서, 각 `JourneyEpisodePostFactory(...)` 호출을 변수로 받아 `download_and_attach` 호출.

journey_yp 루프 변경:

```python
        for ep_no, title in enumerate(
            ["1화 — 부지 매입과 토목 견적", "2화 — 설계 기간 6개월", "3화 — 시공 시작 1개월"],
            start=1,
        ):
            ep = JourneyEpisodePostFactory(
                journey=journey_yp,
                author=resident_a,
                region=regions["yangpyeong"],
                episode_no=ep_no,
                title=title,
                status=PostStatus.PUBLISHED,
                published_at=_now() - timedelta(days=random.randint(60, 200)),
            )
            n = random.randint(1, 3)
            download_and_attach(
                session, ep, resident_a, n,
                base_seed=base_seed_counter[0],
                failure_counter=failure_counter,
            )
            base_seed_counter[0] += 10
```

journey_hc 루프 동일 패턴 적용 (`owner=resident_b`).

- [ ] **Step 4: PLAN 루프에 0-1장 첨부 호출 추가 (T4 블록 수정)**

T4에서 추가한 PLAN 루프의 PlanPostFactory 호출 직후에 추가 (`interested` 변수가 작성자):

```python
            n = random.randint(0, 1)
            if n:
                download_and_attach(
                    session, plans[-1], interested, n,
                    base_seed=base_seed_counter[0],
                    failure_counter=failure_counter,
                )
                base_seed_counter[0] += 10
```

- [ ] **Step 5: SUMMARY에 images 카운트 + warnings 추가**

`from app.models import Comment` 직후에 추가:

```python
        from app.models import Image
        image_total = session.scalar(select(func.count(Image.id)))
        print(f"  Images: {image_total}")
        if failure_counter[0]:
            print(f"  ⚠ Picsum 누적 실패: {failure_counter[0]}회")
```

- [ ] **Step 6: 동작 검증 (네트워크 필요)**

Run: `uv run python -m app.scripts.seed_demo --reset 2>&1 | tail -15`
Expected: SUMMARY에 `Images: <약 25-50>` (12 review × 2 평균 + 5 journey ep × 2 평균 + PLAN 일부)

Run: `ls media/images/ | wc -l`
Expected: 위 Images 카운트와 일치

Run: `find media/images -name "thumb.jpg" | head -3`
Expected: 3개 thumb 파일 경로 (worker handler가 sync로 생성됨을 입증)

- [ ] **Step 7: Commit**

```bash
git add app/scripts/seed_demo.py
git commit -m "feat(seed): attach 1-3 Picsum images per review/journey ep + 0-1 for PLAN"
```

---

## Task 7: 베이스라인 회귀 검증 + 브라우저 manual QA + DoD 마무리

**Files:** (none — verification only)

- [ ] **Step 1: pytest baseline 회귀 없음 확인**

Run: `uv run pytest app/tests/ -q 2>&1 | tail -5`
Expected: `403 passed` (또는 그 이상). seed 모듈 변경은 import만이므로 회귀 없어야 함.

Run: `uv run ruff check app/ 2>&1 | tail -3`
Expected: `All checks passed!`

- [ ] **Step 2: 풀 시드 + DB 카운트 sanity check**

Run: `uv run python -m app.scripts.seed_demo --reset 2>&1 | tail -15`

Expected SUMMARY (대략):
```
Seeded:
  Regions: 4
  Users: 6
  Posts: 32
  ↳ Reviews: 12
  ↳ Journey episodes: 5
  ↳ Questions: 4
  ↳ Answers: <random 0-7>
  ↳ Plans: 4
  Comments: <0-70>
  Images: <25-50>
```

DB 직접 확인:

Run: `docker exec nestory-postgres-local psql -U nestory -d nestory -c "SELECT type, count(*) FROM posts GROUP BY type ORDER BY type;"`
Expected: REVIEW=12, JOURNEY_EPISODE=5, QUESTION=4, ANSWER=N, PLAN=4

Run: `docker exec nestory-postgres-local psql -U nestory -d nestory -c "SELECT count(*) AS ready, count(*) FILTER (WHERE status='processing') AS still_processing FROM images;"`
Expected: `ready=N, still_processing=0` (모든 이미지가 sync 처리됨)

- [ ] **Step 3: 브라우저 manual QA**

서버 시작:

Run: `uv run uvicorn app.main:app --port 8000`

브라우저에서 다음 URL을 차례로 열고 시각 검증:

| URL | 확인 항목 |
|---|---|
| `http://localhost:8000/` | 비로그인 hero 아래 추천 허브 + 인기 후기 카드 (이미지 썸네일 표시) |
| `http://localhost:8000/discover` | 4개 region 카드 |
| `http://localhost:8000/hub/yangpyeong` | 양평 헤더 + 후기/Journey/Q&A 탭 |
| `http://localhost:8000/hub/yangpyeong/reviews` | review 카드 + 썸네일 + pagination 미노출 (12개라 1페이지) |
| `http://localhost:8000/feed` | 최신 글 mixed feed |
| `http://localhost:8000/search?q=양평` | review·journey·question 결과 (한국어 trgm + FTS) |
| `http://localhost:8000/search?q=양펑` | typo도 결과 1+ (0.07 임계값 검증) |
| `http://localhost:8000/post/1` (또는 review id) | body markdown 이미지 inline 렌더 + 댓글 섹션 |
| `http://localhost:8000/u/yangpyeong-1` | resident_a 프로필 |

- [ ] **Step 4: DoD 통과 보고 + 최종 commit (만약 plan 보정 필요 시)**

해당 없음 — 검증만. 모든 step 통과하면 작업 완료.

문제 발견 시: bug fix를 별도 commit으로 추가 (`fix(seed): ...`).

---

## Self-Review Checklist (writer 자체 점검 — 실행자가 보지 않아도 됨)

- ✅ Spec coverage: 9 섹션 모두 task 매핑됨 (T1-2 = §3-4, T3 = §7, T4 = §5, T5 = §6, T6 = §3-4 wiring, T7 = §9 DoD).
- ✅ Placeholder scan: TBD/TODO 0건. 모든 step에 코드 또는 명령 포함.
- ✅ Type consistency: `download_and_attach` / `attach_image` 시그니처 T2에서 정의 후 T6에서 호출 — 일치.
- ✅ Out-of-scope 명시 — `--no-images` flag, ANSWER 첨부, 공지사항: spec §2.2 참조.
- ✅ 외부 네트워크 의존 명시 — T6 Step 6에 "네트워크 필요" + T7 Step 2 SUMMARY 출력에 누적 실패 카운트.
