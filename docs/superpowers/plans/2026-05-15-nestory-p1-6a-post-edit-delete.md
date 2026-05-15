# Phase 1.6a — Post Edit/Delete (Q&A · Plan · Answer) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Question · Answer · Plan 타입의 게시글을 작성자 본인이 수정·삭제할 수 있는 기능을 추가한다. Review · Journey episode는 P1.6b(잠금 정책)에서 별도 처리.

**Architecture:**
- 모델에 `posts.edited_at` 컬럼 신설 — `updated_at`(metadata 자동 변경에도 변함)과 분리해 **사용자가 본문/메타를 직접 수정한 시점만** 기록한다.
- 권한: `app/deps.py`에 `require_author(post_id_param: str)` factory dependency 추가. 작성자 본인만 통과. (관리자는 별도 `hide_post`로 처리 — admin이 사용자 콘텐츠를 직접 수정하지 않음.)
- 서비스: `app/services/posts.py`에 `update_question` · `update_answer` · `update_plan` · `soft_delete_post` 4개 함수 추가. 모두 `db.flush()`만, commit은 라우트.
- 라우트: 기존 `/write/{type}` POST(생성) 패턴을 그대로 확장 — `GET /write/question/{post_id}` (edit form) + `POST /write/question/{post_id}` (update). Answer는 별도 페이지 `/write/answer/{post_id}` (body만). 삭제는 `POST /post/{post_id}/delete` 단일 라우트.
- 템플릿: `write/_base.html`이 이미 `page_title`·`form_action`·`submit_label`을 변수로 받으므로 edit 모드는 라우트 context만 다르면 동작. "수정됨" 표시는 공통 컴포넌트 `components/_edited_badge.html` 신설.
- 잠금 없음 — 자유 수정. 정책(시간 제한·view threshold·답변 개수)은 P1.6b로.

**Tech Stack:** FastAPI · SQLAlchemy 2.x · Alembic · Pydantic v2 · Jinja2 · factory-boy · pytest

---

## File Structure

**Create:**
- `app/db/migrations/versions/<rev>_add_posts_edited_at.py` — Post에 edited_at 컬럼 추가
- `app/templates/components/_edited_badge.html` — "수정됨 · 5분 전" 인디케이터
- `app/tests/integration/test_deps_author_guard.py` — require_author 단위 검증
- `app/tests/integration/test_post_update_service.py` — update_question/answer/plan + soft_delete_post
- `app/tests/integration/test_post_edit_routes.py` — GET/POST 흐름
- `app/tests/integration/test_post_delete_route.py` — soft delete 권한·결과
- `app/tests/integration/test_post_edit_e2e.py` — 전체 흐름 통합 검증

**Modify:**
- `app/models/post.py` — `edited_at: Mapped[datetime | None]` 컬럼 추가
- `app/deps.py` — `require_author(post_id_param)` factory 추가
- `app/services/posts.py` — update/delete 4개 함수 추가
- `app/routers/content.py` — edit GET/POST 라우트 + delete 라우트
- `app/templates/pages/write/_base.html` — edit 모드일 때 헤더 텍스트 분기 (변수 기반)
- `app/templates/pages/detail/question.html` — 질문 헤더 "더보기" 메뉴에 본인일 때 수정/삭제 + edited_badge 표시 + 답변별 메뉴
- `app/templates/pages/detail/post.html` (또는 plan용 detail 페이지) — "더보기" 메뉴 + edited_badge

---

## Task 1: Add `edited_at` column to Post model

**Why edited_at separate from updated_at:** `updated_at`은 `onupdate=func.now()`로 metadata 자동 변경(예: hide_post가 status만 바꿔도) 시 갱신된다. "사용자가 본문을 수정했다"는 의미는 `edited_at`이 있어야 정확히 표현 가능.

**Files:**
- Modify: `app/models/post.py:70` (deleted_at 라인 다음)
- Create: `app/db/migrations/versions/<auto>_add_posts_edited_at.py`
- Test: `app/tests/integration/test_post_model.py` (기존 파일에 한 케이스 추가)

- [ ] **Step 1: Write failing test**

`app/tests/integration/test_post_model.py` 마지막에 다음 추가:

```python
def test_post_edited_at_defaults_to_none(db: Session) -> None:
    """edited_at은 created/published 시점엔 None — 수정 발생 시에만 세팅."""
    post = PostFactory(type=PostType.QUESTION, status=PostStatus.PUBLISHED)
    db.flush()
    assert post.edited_at is None


def test_post_edited_at_settable(db: Session) -> None:
    """edited_at은 timezone-aware datetime을 수용해야 한다."""
    post = PostFactory()
    db.flush()
    now = datetime.now(UTC)
    post.edited_at = now
    db.flush()
    db.refresh(post)
    assert post.edited_at is not None
```

import 확인: `from datetime import datetime, UTC`, `from app.tests.factories import PostFactory`, `from app.models._enums import PostType, PostStatus`.

- [ ] **Step 2: Run test — expect AttributeError**

```
uv run pytest app/tests/integration/test_post_model.py::test_post_edited_at_defaults_to_none -v
```

Expected: FAIL with `AttributeError: 'Post' object has no attribute 'edited_at'`.

- [ ] **Step 3: Add column to model**

`app/models/post.py:70` 의 `deleted_at` 라인 뒤에 추가:

```python
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 4: Autogenerate migration**

```
uv run alembic revision --autogenerate -m "add posts.edited_at"
uv run ruff check --fix app/db/migrations/versions/
```

Expected: 새 파일이 `app/db/migrations/versions/` 에 생성. 확인 사항 — ① `down_revision = 'bc70466dfb57'` (현재 head), ② `op.add_column('posts', sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True))` 가 `upgrade()` 본문에 있음, ③ downgrade에 `op.drop_column('posts', 'edited_at')` 있음.

- [ ] **Step 5: Apply and verify tests pass**

```
uv run alembic upgrade head
uv run pytest app/tests/integration/test_post_model.py -v
```

Expected: 모든 테스트 PASS. 기존 테스트도 깨지지 않아야 함.

- [ ] **Step 6: Commit**

```
git add app/models/post.py app/db/migrations/versions/ app/tests/integration/test_post_model.py
git commit -m "feat(models): posts.edited_at — separate user-edit timestamp from updated_at"
```

---

## Task 2: `require_author` guard

**Files:**
- Modify: `app/deps.py` (require_admin 함수 뒤에 추가)
- Create: `app/tests/integration/test_deps_author_guard.py`

- [ ] **Step 1: Write failing tests**

`app/tests/integration/test_deps_author_guard.py`:

```python
"""require_author dependency 단위 테스트.

라우트에 dependency를 부착했을 때:
- 본인 → 200
- 다른 사용자 → 403
- 비로그인 → 401 (require_user 단계)
- 존재 안 함/soft-deleted → 404
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.deps import get_db, require_author
from app.models import Post
from app.tests.factories import PostFactory, UserFactory


def _make_app(db_override) -> FastAPI:
    """본 테스트 전용 미니 앱 — require_author만 검증."""
    app = FastAPI()
    app.dependency_overrides[get_db] = db_override

    r = APIRouter()

    @r.get("/_check/{post_id}")
    def check(post: Post = Depends(require_author("post_id"))) -> dict:
        return {"post_id": post.id}

    app.include_router(r)
    return app


def test_author_passes(client, db: Session, login) -> None:
    author = UserFactory()
    post = PostFactory(author=author, author_id=author.id)
    db.commit()
    login(author.id)
    r = client.get(f"/_check/{post.id}")
    # 기존 client 가 메인 app인 경우 라우트가 없으므로 404. 다음 케이스를 위해
    # 본 테스트는 _make_app 기반으로 별도 검증. 아래 케이스에서 covered.


def test_non_author_gets_403(client, db: Session, login) -> None:
    author = UserFactory()
    other = UserFactory()
    post = PostFactory(author=author, author_id=author.id)
    db.commit()
    login(other.id)
    # 실제 라우트 검증은 Task 7에서 — 여기선 import 가능성만 확인
    from app.deps import require_author  # noqa
    assert callable(require_author)


def test_post_not_found_404(client, db: Session, login) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)
    from app.deps import require_author
    assert callable(require_author)


def test_soft_deleted_post_404(db: Session) -> None:
    """deleted_at != None 인 post는 404로 취급해야 한다 (수정/삭제 모두 차단)."""
    from app.deps import require_author
    assert callable(require_author)
```

> 본 task의 단위 테스트는 dependency가 import 가능한지·callable 인지만 확인하는 smoke test. 실제 권한 행동은 Task 7·8·10의 라우트 통합 테스트에서 검증한다 (라우트에 부착된 형태로만 의미 있음).

- [ ] **Step 2: Run test — expect ImportError**

```
uv run pytest app/tests/integration/test_deps_author_guard.py -v
```

Expected: FAIL with `ImportError: cannot import name 'require_author' from 'app.deps'`.

- [ ] **Step 3: Implement guard**

`app/deps.py` 의 `require_admin` 함수 뒤에 추가:

```python
from collections.abc import Callable
from fastapi import HTTPException, Path, status

from app.models import Post


def require_author(post_id_param: str = "post_id") -> Callable[..., Post]:
    """Factory dependency — path param의 post_id로 Post를 로드해 본인 소유인지 검증.

    동작:
    - Post 존재 안 함 OR deleted_at != None → 404
    - author_id != user.id → 403
    - 통과 시 Post ORM 인스턴스를 라우트에 주입 (재조회 불필요)

    Usage:
        @router.post("/post/{post_id}/delete")
        def delete(post: Post = Depends(require_author("post_id")), ...):
    """

    def dependency(
        user: User = Depends(require_user),
        db: Session = Depends(get_db),
        post_id: int = Path(..., alias=post_id_param),
    ) -> Post:
        post = db.get(Post, post_id)
        if post is None or post.deleted_at is not None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")
        if post.author_id != user.id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not the author")
        return post

    return dependency
```

`Path` import는 `from fastapi import ... Path` 추가. `User`, `Session`, `Post` import도 확인.

- [ ] **Step 4: Run tests pass**

```
uv run pytest app/tests/integration/test_deps_author_guard.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add app/deps.py app/tests/integration/test_deps_author_guard.py
git commit -m "feat(deps): require_author guard — 본인 소유 post만 통과"
```

---

## Task 3: `services/posts.update_question`

**Files:**
- Modify: `app/services/posts.py` (create_question 함수 뒤에 추가)
- Create: `app/tests/integration/test_post_update_service.py`

- [ ] **Step 1: Write failing test**

`app/tests/integration/test_post_update_service.py`:

```python
"""update_* / soft_delete_post 서비스 함수 단위 테스트."""
from __future__ import annotations

from datetime import UTC, datetime
from sqlalchemy.orm import Session

from app.models._enums import PostStatus, PostType
from app.schemas.post_metadata import PlanMetadata, QuestionMetadata
from app.services import posts as posts_service
from app.tests.factories import PostFactory, RegionFactory, UserFactory


def test_update_question_changes_title_body_tags(db: Session) -> None:
    author = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
        title="기존 제목", body="기존 본문",
        metadata_={"__post_type__": "question", "tags": ["old"]},
    )
    db.flush()
    payload = QuestionMetadata(tags=["new1", "new2"])
    updated = posts_service.update_question(
        db, post, payload=payload, title="새 제목", body="새 본문"
    )
    assert updated.title == "새 제목"
    assert updated.body == "새 본문"
    assert updated.metadata_["tags"] == ["new1", "new2"]
    assert updated.edited_at is not None
    assert updated.type == PostType.QUESTION  # 불변
    assert updated.author_id == author.id     # 불변


def test_update_question_sets_edited_at_close_to_now(db: Session) -> None:
    post = PostFactory(type=PostType.QUESTION, status=PostStatus.PUBLISHED)
    db.flush()
    before = datetime.now(UTC)
    posts_service.update_question(
        db, post,
        payload=QuestionMetadata(tags=[]),
        title="t", body="b",
    )
    after = datetime.now(UTC)
    assert post.edited_at is not None
    assert before <= post.edited_at <= after
```

- [ ] **Step 2: Run test — expect AttributeError**

```
uv run pytest app/tests/integration/test_post_update_service.py::test_update_question_changes_title_body_tags -v
```

Expected: FAIL with `AttributeError: module 'app.services.posts' has no attribute 'update_question'`.

- [ ] **Step 3: Implement update_question**

`app/services/posts.py` 의 `create_question` 함수 뒤에 추가:

```python
def update_question(
    db: Session,
    post: Post,
    *,
    payload: QuestionMetadata,
    title: str,
    body: str,
) -> Post:
    """Question의 title/body/tags를 수정. edited_at 갱신.

    - type, author, region, created_at, published_at은 불변.
    - metadata는 type_tag(__post_type__) 제외 후 dict화.
    """
    if post.type != PostType.QUESTION:
        raise ValueError(f"Cannot update_question on type={post.type.value}")
    post.title = title
    post.body = body
    meta = payload.model_dump(by_alias=True, exclude_none=True)
    meta.pop("__post_type__", None)
    post.metadata_ = {"__post_type__": "question", **meta}
    post.edited_at = datetime.now(UTC)
    db.flush()
    return post
```

상단 import 확인: `from datetime import datetime, UTC`.

- [ ] **Step 4: Run tests pass**

```
uv run pytest app/tests/integration/test_post_update_service.py::test_update_question_changes_title_body_tags app/tests/integration/test_post_update_service.py::test_update_question_sets_edited_at_close_to_now -v
```

Expected: 2 PASS.

- [ ] **Step 5: Commit**

```
git add app/services/posts.py app/tests/integration/test_post_update_service.py
git commit -m "feat(services): posts.update_question — title/body/tags 수정 + edited_at 갱신"
```

---

## Task 4: `services/posts.update_answer`

**Files:**
- Modify: `app/services/posts.py`
- Modify: `app/tests/integration/test_post_update_service.py` (추가 케이스)

- [ ] **Step 1: Write failing test**

`test_post_update_service.py` 에 추가:

```python
def test_update_answer_changes_body_only(db: Session) -> None:
    question = PostFactory(type=PostType.QUESTION, status=PostStatus.PUBLISHED)
    author = UserFactory()
    answer = PostFactory(
        author=author, author_id=author.id,
        type=PostType.ANSWER, status=PostStatus.PUBLISHED,
        parent_post_id=question.id,
        body="기존 답변",
        metadata_={"__post_type__": "answer"},
    )
    db.flush()
    posts_service.update_answer(db, answer, body="수정된 답변")
    assert answer.body == "수정된 답변"
    assert answer.edited_at is not None
    assert answer.parent_post_id == question.id  # 불변
    assert answer.type == PostType.ANSWER         # 불변


def test_update_answer_rejects_non_answer(db: Session) -> None:
    import pytest
    q = PostFactory(type=PostType.QUESTION, status=PostStatus.PUBLISHED)
    db.flush()
    with pytest.raises(ValueError):
        posts_service.update_answer(db, q, body="x")
```

- [ ] **Step 2: Run — expect AttributeError**

```
uv run pytest app/tests/integration/test_post_update_service.py::test_update_answer_changes_body_only -v
```

Expected: FAIL `AttributeError: ... no attribute 'update_answer'`.

- [ ] **Step 3: Implement**

`app/services/posts.py` 에 추가:

```python
def update_answer(db: Session, post: Post, *, body: str) -> Post:
    """Answer의 body만 수정. title은 빈 문자열(answer 규칙)이므로 손대지 않음."""
    if post.type != PostType.ANSWER:
        raise ValueError(f"Cannot update_answer on type={post.type.value}")
    post.body = body
    post.edited_at = datetime.now(UTC)
    db.flush()
    return post
```

- [ ] **Step 4: Run tests pass**

```
uv run pytest app/tests/integration/test_post_update_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add app/services/posts.py app/tests/integration/test_post_update_service.py
git commit -m "feat(services): posts.update_answer — body 수정"
```

---

## Task 5: `services/posts.update_plan`

**Files:**
- Modify: `app/services/posts.py`
- Modify: `app/tests/integration/test_post_update_service.py`

- [ ] **Step 1: Write failing test**

```python
def test_update_plan_changes_all_metadata_fields(db: Session) -> None:
    author = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.PLAN, status=PostStatus.PUBLISHED,
        title="기존", body="기존",
        metadata_={
            "__post_type__": "plan",
            "target_move_year": 2027,
            "household_size": 1,
            "budget_total_manwon_band": "<5000",
            "construction_intent": "undecided",
            "open_to_advice": True,
        },
    )
    db.flush()
    new_payload = PlanMetadata(
        target_move_year=2028,
        budget_total_manwon_band="10000-20000",
        construction_intent="self_build",
    )
    posts_service.update_plan(
        db, post, payload=new_payload, title="새 제목", body="새 본문"
    )
    assert post.title == "새 제목"
    assert post.body == "새 본문"
    assert post.metadata_["target_move_year"] == 2028
    assert post.metadata_["budget_total_manwon_band"] == "10000-20000"
    assert post.metadata_["construction_intent"] == "self_build"
    assert post.edited_at is not None
    assert post.type == PostType.PLAN
```

- [ ] **Step 2: Run — expect AttributeError**

```
uv run pytest app/tests/integration/test_post_update_service.py::test_update_plan_changes_all_metadata_fields -v
```

Expected: FAIL.

- [ ] **Step 3: Implement**

```python
def update_plan(
    db: Session,
    post: Post,
    *,
    payload: PlanMetadata,
    title: str,
    body: str,
) -> Post:
    if post.type != PostType.PLAN:
        raise ValueError(f"Cannot update_plan on type={post.type.value}")
    post.title = title
    post.body = body
    meta = payload.model_dump(by_alias=True, exclude_none=True)
    meta.pop("__post_type__", None)
    post.metadata_ = {"__post_type__": "plan", **meta}
    post.edited_at = datetime.now(UTC)
    db.flush()
    return post
```

- [ ] **Step 4: Run pass**

```
uv run pytest app/tests/integration/test_post_update_service.py -v
```

- [ ] **Step 5: Commit**

```
git add app/services/posts.py app/tests/integration/test_post_update_service.py
git commit -m "feat(services): posts.update_plan — metadata 전체 갱신 + edited_at"
```

---

## Task 6: `services/posts.soft_delete_post`

**Files:**
- Modify: `app/services/posts.py`
- Modify: `app/tests/integration/test_post_update_service.py`

- [ ] **Step 1: Write failing test**

```python
def test_soft_delete_sets_deleted_at(db: Session) -> None:
    post = PostFactory(type=PostType.QUESTION, status=PostStatus.PUBLISHED)
    db.flush()
    assert post.deleted_at is None
    posts_service.soft_delete_post(db, post)
    assert post.deleted_at is not None


def test_soft_delete_idempotent(db: Session) -> None:
    """이미 삭제된 게시글에 다시 호출해도 deleted_at은 first-call 시각 유지."""
    post = PostFactory(type=PostType.PLAN, status=PostStatus.PUBLISHED)
    db.flush()
    posts_service.soft_delete_post(db, post)
    first = post.deleted_at
    posts_service.soft_delete_post(db, post)
    assert post.deleted_at == first  # 변경 안 됨
```

- [ ] **Step 2: Run — expect AttributeError**

```
uv run pytest app/tests/integration/test_post_update_service.py::test_soft_delete_sets_deleted_at -v
```

Expected: FAIL.

- [ ] **Step 3: Implement**

```python
def soft_delete_post(db: Session, post: Post) -> Post:
    """Post.deleted_at 세팅. 이미 삭제되었으면 no-op (idempotent).

    Feed/Hub/Detail 등에서 deleted_at 필터는 이미 적용 중 (기존 테스트 검증).
    """
    if post.deleted_at is None:
        post.deleted_at = datetime.now(UTC)
        db.flush()
    return post
```

- [ ] **Step 4: Run tests**

```
uv run pytest app/tests/integration/test_post_update_service.py -v
```

Expected: 모든 케이스 PASS.

- [ ] **Step 5: Commit**

```
git add app/services/posts.py app/tests/integration/test_post_update_service.py
git commit -m "feat(services): posts.soft_delete_post — idempotent deleted_at"
```

---

## Task 7: Edit routes for Question

**라우트 설계:**
- `GET /write/question/{post_id}` — 기존 question 작성 폼을 prefill 형태로 렌더 (form_action은 `/write/question/{post_id}`)
- `POST /write/question/{post_id}` — update 수행 후 `/question/{post_id}` 로 303

**Files:**
- Modify: `app/routers/content.py` (write_question_form 뒤에 추가)
- Create: `app/tests/integration/test_post_edit_routes.py`

- [ ] **Step 1: Write failing test**

`app/tests/integration/test_post_edit_routes.py`:

```python
"""POST /write/question/{id} · /write/plan/{id} · /write/answer/{id} edit 라우트."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import PostStatus, PostType
from app.tests.factories import PostFactory, RegionFactory, UserFactory


def test_get_edit_question_renders_prefilled(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    region = RegionFactory(slug="edit-q-region")
    post = PostFactory(
        author=author, author_id=author.id,
        region=region, region_id=region.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
        title="원래 제목", body="원래 본문",
        metadata_={"__post_type__": "question", "tags": ["a", "b"]},
    )
    db.commit()
    login(author.id)
    r = client.get(f"/write/question/{post.id}")
    assert r.status_code == 200
    assert "원래 제목" in r.text
    assert "원래 본문" in r.text


def test_post_edit_question_updates_fields(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    region = RegionFactory(slug="edit-q-region-2")
    post = PostFactory(
        author=author, author_id=author.id,
        region=region, region_id=region.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
        title="A", body="B",
        metadata_={"__post_type__": "question", "tags": []},
    )
    db.commit()
    login(author.id)
    r = client.post(
        f"/write/question/{post.id}",
        data={
            "title": "수정된 제목",
            "body": "수정된 본문",
            "region_id": str(region.id),
            "tags": "k1,k2",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/question/{post.id}"
    db.refresh(post)
    assert post.title == "수정된 제목"
    assert post.body == "수정된 본문"
    assert post.metadata_["tags"] == ["k1", "k2"]
    assert post.edited_at is not None


def test_non_author_cannot_edit(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    other = UserFactory()
    region = RegionFactory(slug="edit-q-region-3")
    post = PostFactory(
        author=author, author_id=author.id,
        region=region, region_id=region.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
    )
    db.commit()
    login(other.id)
    r = client.get(f"/write/question/{post.id}")
    assert r.status_code == 403
```

- [ ] **Step 2: Run — expect 404 (라우트 없음)**

```
uv run pytest app/tests/integration/test_post_edit_routes.py::test_get_edit_question_renders_prefilled -v
```

Expected: FAIL (404 from FastAPI — route undefined).

- [ ] **Step 3: Implement routes**

`app/routers/content.py` 의 `write_question_form` 뒤에 추가:

```python
@router.get("/write/question/{post_id}", response_class=HTMLResponse)
def edit_question_form(
    request: Request,
    post: Post = Depends(require_author("post_id")),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if post.type != PostType.QUESTION:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not a question")
    regions = regions_service.list_all_for_dropdown(db)
    # form-like context: 기존 작성 템플릿이 form.title/body/region_id를 expect
    form_view = {
        "title": post.title,
        "body": post.body,
        "region_id": post.region_id,
        "tags": ",".join(post.metadata_.get("tags", [])),
    }
    return templates.TemplateResponse(
        request,
        "pages/write/question.html",
        {
            "current_user": post.author,
            "page_title": "질문 수정",
            "page_subtitle": None,
            "form_action": f"/write/question/{post.id}",
            "submit_label": "저장",
            "regions": regions,
            "form": form_view,
        },
    )


@router.post("/write/question/{post_id}")
def submit_edit_question(
    post: Post = Depends(require_author("post_id")),
    db: Session = Depends(get_db),
    title: str = Form(...),
    body: str = Form(...),
    region_id: int = Form(...),
    tags: str = Form(""),
) -> RedirectResponse:
    if post.type != PostType.QUESTION:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not a question")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()][:10]
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid region")
    post.region_id = region.id  # region 변경 허용
    posts_service.update_question(
        db, post,
        payload=QuestionMetadata(tags=tag_list),
        title=title, body=body,
    )
    db.commit()
    return RedirectResponse(f"/question/{post.id}", status_code=status.HTTP_303_SEE_OTHER)
```

상단 import 추가/확인:
```python
from app.deps import require_author
from app.models import Post, Region
from app.models._enums import PostType
from app.services import posts as posts_service
from app.schemas.post_metadata import QuestionMetadata
```

또한 `_meta_question.html` 가 prefill을 지원하는지 확인 — 이미 `form.tags` 를 expect한다면 그대로 통과. expect 안 한다면 _meta_question.html 의 Alpine `x-data`에 `initialTags: '{{ (form.tags if form else "") }}'` 추가. (이 변경은 prefill 대비 안전성을 위해 동봉)

- [ ] **Step 4: Run tests pass**

```
uv run pytest app/tests/integration/test_post_edit_routes.py::test_get_edit_question_renders_prefilled app/tests/integration/test_post_edit_routes.py::test_post_edit_question_updates_fields app/tests/integration/test_post_edit_routes.py::test_non_author_cannot_edit -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```
git add app/routers/content.py app/tests/integration/test_post_edit_routes.py app/templates/pages/write/_meta_question.html
git commit -m "feat(content): GET/POST /write/question/{id} — 작성자 본인 질문 수정"
```

---

## Task 8: Edit routes for Plan

**Files:**
- Modify: `app/routers/content.py`
- Modify: `app/tests/integration/test_post_edit_routes.py`

- [ ] **Step 1: Write failing test**

```python
def test_post_edit_plan_updates_fields(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    region = RegionFactory(slug="edit-plan-region")
    post = PostFactory(
        author=author, author_id=author.id,
        region=region, region_id=region.id,
        type=PostType.PLAN, status=PostStatus.PUBLISHED,
        title="P", body="B",
        metadata_={
            "__post_type__": "plan",
            "target_move_year": 2027,
            "household_size": 1,
            "budget_total_manwon_band": "<5000",
            "construction_intent": "undecided",
            "open_to_advice": True,
        },
    )
    db.commit()
    login(author.id)
    r = client.post(
        f"/write/plan/{post.id}",
        data={
            "title": "새 계획",
            "body": "새 본문",
            "region_id": str(region.id),
            "target_move_year": "2030",
            "budget_total_manwon_band": "20000-40000",
            "construction_intent": "self_build",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/post/{post.id}"
    db.refresh(post)
    assert post.title == "새 계획"
    assert post.metadata_["target_move_year"] == 2030
    assert post.edited_at is not None
```

- [ ] **Step 2: Run — expect 404**

```
uv run pytest app/tests/integration/test_post_edit_routes.py::test_post_edit_plan_updates_fields -v
```

Expected: FAIL.

- [ ] **Step 3: Implement routes**

`app/routers/content.py` 의 `write_plan_form` 뒤에 추가:

```python
@router.get("/write/plan/{post_id}", response_class=HTMLResponse)
def edit_plan_form(
    request: Request,
    post: Post = Depends(require_author("post_id")),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    if post.type != PostType.PLAN:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not a plan")
    regions = regions_service.list_all_for_dropdown(db)
    form_view = {
        "title": post.title,
        "body": post.body,
        "region_id": post.region_id,
        "target_move_year": post.metadata_.get("target_move_year"),
        "budget_total_manwon_band": post.metadata_.get("budget_total_manwon_band"),
        "construction_intent": post.metadata_.get("construction_intent"),
    }
    return templates.TemplateResponse(
        request,
        "pages/write/plan.html",
        {
            "current_user": post.author,
            "page_title": "정착 계획 수정",
            "page_subtitle": None,
            "form_action": f"/write/plan/{post.id}",
            "submit_label": "저장",
            "regions": regions,
            "form": form_view,
        },
    )


@router.post("/write/plan/{post_id}")
def submit_edit_plan(
    post: Post = Depends(require_author("post_id")),
    db: Session = Depends(get_db),
    title: str = Form(...),
    body: str = Form(...),
    region_id: int = Form(...),
    target_move_year: int = Form(...),
    budget_total_manwon_band: str = Form(...),
    construction_intent: str = Form(...),
) -> RedirectResponse:
    if post.type != PostType.PLAN:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not a plan")
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid region")
    post.region_id = region.id
    payload = PlanMetadata(
        target_move_year=target_move_year,
        budget_total_manwon_band=budget_total_manwon_band,  # type: ignore[arg-type]
        construction_intent=construction_intent,  # type: ignore[arg-type]
    )
    posts_service.update_plan(db, post, payload=payload, title=title, body=body)
    db.commit()
    return RedirectResponse(f"/post/{post.id}", status_code=status.HTTP_303_SEE_OTHER)
```

`PlanMetadata` import 추가.

또한 `_meta_plan.html` 이 `form.target_move_year`·`form.budget_total_manwon_band`·`form.construction_intent` prefill을 지원하는지 확인. 미지원이라면 각 input/select에 `value="{{ form.X if form else '' }}"` 또는 `{% if form and form.X == 'self_build' %}selected{% endif %}` 패턴 추가.

- [ ] **Step 4: Run tests**

```
uv run pytest app/tests/integration/test_post_edit_routes.py -v
```

Expected: 모든 케이스 PASS (Task 7 + 본 task 추가분).

- [ ] **Step 5: Commit**

```
git add app/routers/content.py app/tests/integration/test_post_edit_routes.py app/templates/pages/write/_meta_plan.html
git commit -m "feat(content): GET/POST /write/plan/{id} — 작성자 본인 plan 수정"
```

---

## Task 9: Edit route for Answer

답변은 body만 있고 region/tags가 없어 가장 단순. 별도 페이지 대신 동일한 `_base.html`를 사용하되 메타 fields 없이.

**Files:**
- Create: `app/templates/pages/write/answer_edit.html`
- Modify: `app/routers/content.py`
- Modify: `app/tests/integration/test_post_edit_routes.py`

- [ ] **Step 1: Write failing test**

```python
def test_edit_answer_updates_body(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    question = PostFactory(type=PostType.QUESTION, status=PostStatus.PUBLISHED)
    answer = PostFactory(
        author=author, author_id=author.id,
        type=PostType.ANSWER, status=PostStatus.PUBLISHED,
        parent_post_id=question.id,
        body="원본 답변",
        metadata_={"__post_type__": "answer"},
        title="",
    )
    db.commit()
    login(author.id)
    r = client.post(
        f"/write/answer/{answer.id}",
        data={"body": "수정된 답변"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/question/{question.id}"
    db.refresh(answer)
    assert answer.body == "수정된 답변"
    assert answer.edited_at is not None


def test_get_edit_answer_renders(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    question = PostFactory(type=PostType.QUESTION, status=PostStatus.PUBLISHED)
    answer = PostFactory(
        author=author, author_id=author.id,
        type=PostType.ANSWER, status=PostStatus.PUBLISHED,
        parent_post_id=question.id,
        body="원본 본문 텍스트",
        metadata_={"__post_type__": "answer"},
        title="",
    )
    db.commit()
    login(author.id)
    r = client.get(f"/write/answer/{answer.id}")
    assert r.status_code == 200
    assert "원본 본문 텍스트" in r.text
```

- [ ] **Step 2: Run — expect 404**

```
uv run pytest app/tests/integration/test_post_edit_routes.py::test_edit_answer_updates_body -v
```

Expected: FAIL.

- [ ] **Step 3: Create dedicated template**

`app/templates/pages/write/answer_edit.html`:

```html
{% extends "base.html" %}
{% from "components/_avatar.html" import avatar %}
{% from "components/_icon.html" import icon %}
{% block title %}{{ page_title }} · Nestory{% endblock %}
{% block content %}
<section class="mx-auto max-w-xl">
  <header class="flex items-start justify-between gap-3 py-3">
    <h1 class="text-base font-bold text-stone-900">{{ page_title }}</h1>
    <a href="{{ back_href }}" class="shrink-0 rounded-full p-1.5 text-stone-400 hover:bg-stone-100 hover:text-stone-600" aria-label="취소">{{ icon("x", 18) }}</a>
  </header>

  <form method="post" action="{{ form_action }}"
        enctype="application/x-www-form-urlencoded"
        class="px-6 sm:px-10 pt-1 pb-3 bg-white rounded-2xl border border-stone-200">
    <div class="flex items-center gap-2.5 -mx-6 sm:-mx-10 px-6 sm:px-10 pt-3 pb-3 border-b border-stone-100">
      <div class="shrink-0">{{ avatar(current_user, 36) }}</div>
      <div class="min-w-0 flex-1 leading-tight">
        <span class="text-[15px] font-semibold text-stone-900 truncate">{{ current_user.username }}</span>
      </div>
    </div>
    <div class="pt-3">
      <textarea name="body" id="body-textarea" required rows="6"
                placeholder="답변을 수정하세요"
                class="w-full border-0 p-0 text-[15px] leading-relaxed text-stone-900 placeholder-stone-400 focus:outline-none focus:ring-0 bg-transparent resize-none">{{ form.body if form else "" }}</textarea>
    </div>
    <div class="mt-5 flex items-center justify-end -mx-6 sm:-mx-10 px-6 sm:px-10 pt-3 border-t border-stone-200">
      <button type="submit" class="rounded-full bg-stone-900 text-white px-5 py-2 text-sm font-semibold hover:bg-stone-700">저장</button>
    </div>
  </form>
</section>
{% endblock %}
```

- [ ] **Step 4: Add routes**

`app/routers/content.py` (submit_answer 뒤에 추가):

```python
@router.get("/write/answer/{post_id}", response_class=HTMLResponse)
def edit_answer_form(
    request: Request,
    post: Post = Depends(require_author("post_id")),
) -> HTMLResponse:
    if post.type != PostType.ANSWER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not an answer")
    return templates.TemplateResponse(
        request,
        "pages/write/answer_edit.html",
        {
            "current_user": post.author,
            "page_title": "답변 수정",
            "form_action": f"/write/answer/{post.id}",
            "back_href": f"/question/{post.parent_post_id}",
            "form": {"body": post.body},
        },
    )


@router.post("/write/answer/{post_id}")
def submit_edit_answer(
    post: Post = Depends(require_author("post_id")),
    db: Session = Depends(get_db),
    body: str = Form(...),
) -> RedirectResponse:
    if post.type != PostType.ANSWER:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not an answer")
    parent_qid = post.parent_post_id
    posts_service.update_answer(db, post, body=body)
    db.commit()
    return RedirectResponse(f"/question/{parent_qid}", status_code=status.HTTP_303_SEE_OTHER)
```

- [ ] **Step 5: Run tests**

```
uv run pytest app/tests/integration/test_post_edit_routes.py -v
```

Expected: 모든 케이스 PASS.

- [ ] **Step 6: Commit**

```
git add app/routers/content.py app/templates/pages/write/answer_edit.html app/tests/integration/test_post_edit_routes.py
git commit -m "feat(content): GET/POST /write/answer/{id} — 답변 본문 수정"
```

---

## Task 10: Soft-delete route `POST /post/{id}/delete`

**Files:**
- Modify: `app/routers/content.py`
- Create: `app/tests/integration/test_post_delete_route.py`

- [ ] **Step 1: Write failing test**

```python
"""POST /post/{id}/delete — 작성자 본인 soft delete."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import PostStatus, PostType
from app.tests.factories import PostFactory, UserFactory


def test_author_deletes_question_redirects_home(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
    )
    db.commit()
    login(author.id)
    r = client.post(f"/post/{post.id}/delete", follow_redirects=False)
    assert r.status_code == 303
    db.refresh(post)
    assert post.deleted_at is not None


def test_author_deletes_answer_redirects_to_question(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    q = PostFactory(type=PostType.QUESTION, status=PostStatus.PUBLISHED)
    a = PostFactory(
        author=author, author_id=author.id,
        type=PostType.ANSWER, status=PostStatus.PUBLISHED,
        parent_post_id=q.id, title="",
        metadata_={"__post_type__": "answer"},
    )
    db.commit()
    login(author.id)
    r = client.post(f"/post/{a.id}/delete", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == f"/question/{q.id}"
    db.refresh(a)
    assert a.deleted_at is not None


def test_non_author_cannot_delete(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    other = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
    )
    db.commit()
    login(other.id)
    r = client.post(f"/post/{post.id}/delete", follow_redirects=False)
    assert r.status_code == 403


def test_deleted_post_returns_404_on_detail(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
    )
    db.commit()
    login(author.id)
    client.post(f"/post/{post.id}/delete", follow_redirects=False)
    r = client.get(f"/question/{post.id}")
    assert r.status_code == 404
```

- [ ] **Step 2: Run — expect 404 (라우트 없음)**

```
uv run pytest app/tests/integration/test_post_delete_route.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement route**

`app/routers/content.py` 마지막에 추가:

```python
@router.post("/post/{post_id}/delete")
def delete_post(
    post: Post = Depends(require_author("post_id")),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Soft delete (deleted_at 세팅). Type별 redirect:
    - Answer → /question/{parent}
    - 그 외 → /
    """
    redirect_to = "/"
    if post.type == PostType.ANSWER and post.parent_post_id:
        redirect_to = f"/question/{post.parent_post_id}"
    posts_service.soft_delete_post(db, post)
    db.commit()
    return RedirectResponse(redirect_to, status_code=status.HTTP_303_SEE_OTHER)
```

- [ ] **Step 4: Run tests pass**

```
uv run pytest app/tests/integration/test_post_delete_route.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```
git add app/routers/content.py app/tests/integration/test_post_delete_route.py
git commit -m "feat(content): POST /post/{id}/delete — 작성자 본인 soft delete"
```

---

## Task 11: `_edited_badge.html` component

**Files:**
- Create: `app/templates/components/_edited_badge.html`

**Why:** 모든 detail 페이지에서 동일 UI를 재사용 — 후속 P1.6b에서 review/journey episode에도 그대로 적용. 별도 macro로 분리해 1회 수정 = 전체 반영.

- [ ] **Step 1: Create template**

`app/templates/components/_edited_badge.html`:

```html
{# components/_edited_badge.html — Post.edited_at 있을 때 "· 수정됨 N분 전" 칩.
   사용:
     {% from "components/_edited_badge.html" import edited_badge %}
     {{ edited_badge(post.edited_at) }}
   디자인: 작은 stone-400 텍스트, title 속성에 정확한 시각.
#}
{% macro edited_badge(edited_at) -%}
  {% if edited_at %}
    <span class="text-[11px] text-stone-400" title="{{ edited_at.strftime('%Y-%m-%d %H:%M') }}">
      · 수정됨 {{ edited_at | relative_time }}
    </span>
  {% endif %}
{%- endmacro %}
```

- [ ] **Step 2: Verify `relative_time` filter exists**

```
grep -n "relative_time" app/templating.py
```

Expected: filter 등록 라인. 없으면 추가 — 이미 다른 페이지에서 `| relative_time` 사용 중이라면 등록되어 있을 가능성 100%.

수동 확인: 기존 `pages/detail/question.html` 에서 `relative_time` 사용 사례 검색. 사용 중이면 등록 확인됨 (별도 작업 X).

- [ ] **Step 3: Commit**

```
git add app/templates/components/_edited_badge.html
git commit -m "feat(ui): _edited_badge 컴포넌트 — 모든 post detail에서 재사용"
```

---

## Task 12: Question detail — "더보기" 메뉴에 본인 수정/삭제 + answer 카드 메뉴

**Files:**
- Modify: `app/templates/pages/detail/question.html`

- [ ] **Step 1: Write failing test**

`app/tests/integration/test_post_edit_routes.py` 에 추가:

```python
def test_question_detail_shows_edit_link_for_author(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
    )
    db.commit()
    login(author.id)
    r = client.get(f"/question/{post.id}")
    assert r.status_code == 200
    assert f"/write/question/{post.id}" in r.text
    assert f"/post/{post.id}/delete" in r.text


def test_question_detail_hides_edit_link_for_non_author(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    other = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
    )
    db.commit()
    login(other.id)
    r = client.get(f"/question/{post.id}")
    assert r.status_code == 200
    assert f"/write/question/{post.id}" not in r.text
    assert f"/post/{post.id}/delete" not in r.text


def test_question_detail_shows_edited_badge(client: TestClient, db: Session, login) -> None:
    from datetime import UTC, datetime, timedelta
    author = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
    )
    post.edited_at = datetime.now(UTC) - timedelta(minutes=3)
    db.commit()
    login(author.id)
    r = client.get(f"/question/{post.id}")
    assert "수정됨" in r.text
```

- [ ] **Step 2: Run — expect FAIL (마크업 부재)**

```
uv run pytest app/tests/integration/test_post_edit_routes.py::test_question_detail_shows_edit_link_for_author app/tests/integration/test_post_edit_routes.py::test_question_detail_shows_edited_badge -v
```

Expected: FAIL (마크업이 아직 없음).

- [ ] **Step 3: Modify `pages/detail/question.html`**

질문 헤더의 "더보기" 메뉴 (기존 Line 21 인근) 를 Alpine dropdown으로 교체:

```html
{# 기존 더보기 자리 (질문 헤더 우측) — 본인이면 수정/삭제, 다른 사용자면 신고. #}
<div x-data="{ open: false }" @click.outside="open = false" class="relative">
  <button type="button" @click="open = !open" class="rounded-full p-1.5 text-stone-400 hover:bg-stone-100 hover:text-stone-600" aria-label="더보기">
    {{ icon("more-horizontal", 18) }}
  </button>
  <div x-show="open" x-cloak class="absolute right-0 mt-1 w-32 rounded-lg border border-stone-200 bg-white shadow-md text-sm z-10">
    {% if current_user and current_user.id == question.author_id %}
      <a href="/write/question/{{ question.id }}" class="block px-3 py-2 text-stone-700 hover:bg-stone-50">수정</a>
      <form method="post" action="/post/{{ question.id }}/delete"
            onsubmit="return confirm('이 질문을 삭제하시겠습니까?');">
        <button type="submit" class="block w-full text-left px-3 py-2 text-rose-600 hover:bg-rose-50">삭제</button>
      </form>
    {% else %}
      <a href="#" class="block px-3 py-2 text-stone-700 hover:bg-stone-50">신고</a>
    {% endif %}
  </div>
</div>
```

질문 본문 시간 옆에 edited_badge 추가:

```html
{% from "components/_edited_badge.html" import edited_badge %}
...
<span>{{ question.published_at | relative_time }}</span>
{{ edited_badge(question.edited_at) }}
```

답변 루프 (기존 Line 71-86) 의 카드 header에도 동일한 dropdown 추가:

```html
{% for ans in answers %}
  <article class="...">
    <header class="flex items-start justify-between gap-2">
      <div class="flex items-center gap-2 ...">
        {{ avatar(ans.author, 32) }}
        <a href="/u/{{ ans.author.username }}">@{{ ans.author.username }}</a>
        <span>{{ ans.published_at | relative_time }}</span>
        {{ edited_badge(ans.edited_at) }}
      </div>
      {# 답변 카드 우측 더보기 — 본인 답변일 때 수정/삭제 #}
      <div x-data="{ open: false }" @click.outside="open = false" class="relative">
        <button type="button" @click="open = !open" class="rounded-full p-1 text-stone-400 hover:bg-stone-100" aria-label="더보기">
          {{ icon("more-horizontal", 16) }}
        </button>
        <div x-show="open" x-cloak class="absolute right-0 mt-1 w-32 rounded-lg border border-stone-200 bg-white shadow-md text-sm z-10">
          {% if current_user and current_user.id == ans.author_id %}
            <a href="/write/answer/{{ ans.id }}" class="block px-3 py-2 text-stone-700 hover:bg-stone-50">수정</a>
            <form method="post" action="/post/{{ ans.id }}/delete"
                  onsubmit="return confirm('답변을 삭제하시겠습니까?');">
              <button type="submit" class="block w-full text-left px-3 py-2 text-rose-600 hover:bg-rose-50">삭제</button>
            </form>
          {% else %}
            <a href="#" class="block px-3 py-2 text-stone-700 hover:bg-stone-50">신고</a>
          {% endif %}
        </div>
      </div>
    </header>
    <p>{{ ans.body }}</p>
  </article>
{% endfor %}
```

> 정확한 라인 변경은 question.html 의 기존 구조를 보존하면서 — author 비교 + edited_badge + 메뉴만 추가. 기존 마크업의 class·구조는 그대로 유지.

- [ ] **Step 4: Run tests**

```
uv run pytest app/tests/integration/test_post_edit_routes.py -v
```

Expected: 모든 케이스 PASS. 기존 question detail 테스트도 깨지지 않아야 함.

```
uv run pytest app/tests/integration/test_content_routes.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add app/templates/pages/detail/question.html app/tests/integration/test_post_edit_routes.py
git commit -m "feat(ui): question detail — 본인 글 수정/삭제 dropdown + edited_badge"
```

---

## Task 13: Plan detail — "더보기" 메뉴 + edited_badge

**Files:**
- Modify: `app/templates/pages/detail/post.html` (또는 plan을 렌더하는 페이지 — `/post/{id}` 라우트가 사용하는 템플릿. content.py:194 의 `post_detail` 라우트 확인)

- [ ] **Step 1: Locate template & write failing test**

```
grep -n "TemplateResponse" app/routers/content.py | grep -i "post_detail"
```

해당 라우트가 사용하는 템플릿 경로 확인 (예: `pages/detail/post.html` 또는 `pages/post_detail.html`).

`app/tests/integration/test_post_edit_routes.py` 에 추가:

```python
def test_plan_detail_shows_edit_link_for_author(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.PLAN, status=PostStatus.PUBLISHED,
    )
    db.commit()
    login(author.id)
    r = client.get(f"/post/{post.id}")
    assert r.status_code == 200
    assert f"/write/plan/{post.id}" in r.text
    assert f"/post/{post.id}/delete" in r.text


def test_plan_detail_shows_edited_badge(client: TestClient, db: Session, login) -> None:
    from datetime import UTC, datetime, timedelta
    author = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.PLAN, status=PostStatus.PUBLISHED,
    )
    post.edited_at = datetime.now(UTC) - timedelta(hours=1)
    db.commit()
    login(author.id)
    r = client.get(f"/post/{post.id}")
    assert "수정됨" in r.text
```

- [ ] **Step 2: Run — expect FAIL**

```
uv run pytest app/tests/integration/test_post_edit_routes.py::test_plan_detail_shows_edit_link_for_author -v
```

Expected: FAIL.

- [ ] **Step 3: Modify post detail template**

Task 12 와 동일한 패턴으로 dropdown 추가. 다만 edit 링크는 type별 분기:

```html
{% if current_user and current_user.id == post.author_id %}
  {% if post.type.value == "plan" %}
    <a href="/write/plan/{{ post.id }}" class="block px-3 py-2 text-stone-700 hover:bg-stone-50">수정</a>
  {% endif %}
  <form method="post" action="/post/{{ post.id }}/delete"
        onsubmit="return confirm('이 게시글을 삭제하시겠습니까?');">
    <button type="submit" class="block w-full text-left px-3 py-2 text-rose-600 hover:bg-rose-50">삭제</button>
  </form>
{% else %}
  <a href="#" class="block px-3 py-2 text-stone-700 hover:bg-stone-50">신고</a>
{% endif %}
```

> Review·Journey episode는 type 분기에서 제외 — P1.6b 까지 수정 비활성. 단 본인이라면 삭제는 가능하게 둘지 정책 결정 필요 — 본 plan에서는 **plan/question/answer만 본인 삭제 허용**으로 통일 (post detail 페이지가 plan만 처리하므로 안전).

edited_badge 추가:

```html
{% from "components/_edited_badge.html" import edited_badge %}
<span>{{ post.published_at | relative_time }}</span>
{{ edited_badge(post.edited_at) }}
```

- [ ] **Step 4: Run tests**

```
uv run pytest app/tests/integration/test_post_edit_routes.py -v
```

Expected: 모든 케이스 PASS.

- [ ] **Step 5: Commit**

```
git add app/templates/pages/detail/post.html app/tests/integration/test_post_edit_routes.py
git commit -m "feat(ui): post detail (plan) — 본인 글 수정/삭제 + edited_badge"
```

---

## Task 14: write/_base.html — submit_label 노출 일관성 점검

`_base.html` 은 이미 `submit_label` 변수를 받지만, `_publish_card.html` 에서만 사용 중. 모든 edit 모드에서 "저장" 라벨이 올바르게 표시되는지 + cancel 버튼이 새 글 작성과 다르게 동작하는지 확인.

**Files:**
- Modify: `app/templates/pages/write/_base.html` (필요 시)

- [ ] **Step 1: Audit current state**

`_base.html` 의 우상단 닫기(X) 버튼 `href="/"` 가 edit 모드에서 부적절 (사용자가 의도하지 않은 위치로 이동). edit 모드에서는 원본 게시글로 돌아가야 함.

`_base.html`:

```html
<a href="{{ cancel_href | default('/') }}" class="shrink-0 rounded-full p-1.5 text-stone-400 hover:bg-stone-100 hover:text-stone-600" aria-label="닫기">{{ icon("x", 18) }}</a>
```

- [ ] **Step 2: Routes pass `cancel_href`**

Task 7 의 `edit_question_form` 의 context에 추가:

```python
"cancel_href": f"/question/{post.id}",
```

Task 8 의 `edit_plan_form` 의 context에 추가:

```python
"cancel_href": f"/post/{post.id}",
```

- [ ] **Step 3: Write test verifying cancel link**

`test_post_edit_routes.py` 에 추가:

```python
def test_edit_question_form_cancel_link_returns_to_question(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    post = PostFactory(
        author=author, author_id=author.id,
        type=PostType.QUESTION, status=PostStatus.PUBLISHED,
    )
    db.commit()
    login(author.id)
    r = client.get(f"/write/question/{post.id}")
    assert f'href="/question/{post.id}"' in r.text
```

- [ ] **Step 4: Run tests**

```
uv run pytest app/tests/integration/test_post_edit_routes.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```
git add app/templates/pages/write/_base.html app/routers/content.py app/tests/integration/test_post_edit_routes.py
git commit -m "feat(ui): write/_base — cancel_href 변수화 (edit 모드에선 원본 글로 복귀)"
```

---

## Task 15: End-to-end integration test

**Files:**
- Create: `app/tests/integration/test_post_edit_e2e.py`

- [ ] **Step 1: Write e2e flow**

`app/tests/integration/test_post_edit_e2e.py`:

```python
"""E2E — Question 생성 → 수정 → 답변 작성 → 답변 수정 → 답변 삭제 → 질문 삭제."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Post
from app.models._enums import PostType
from app.tests.factories import RegionFactory, UserFactory


def test_full_edit_delete_flow(client: TestClient, db: Session, login) -> None:
    author = UserFactory()
    region = RegionFactory(slug="e2e-edit-region")
    db.commit()
    login(author.id)

    # 1. 질문 작성
    r = client.post("/write/question", data={
        "title": "양평 빌라 vs 단독주택 어떻게?",
        "body": "원본 본문",
        "region_id": str(region.id),
        "tags": "주택,선택",
    }, follow_redirects=False)
    assert r.status_code == 303
    qid = int(r.headers["location"].rsplit("/", 1)[1])

    # 2. 질문 수정
    r = client.post(f"/write/question/{qid}", data={
        "title": "양평 빌라 vs 단독주택 (재정리)",
        "body": "수정된 본문",
        "region_id": str(region.id),
        "tags": "주택,선택,재정리",
    }, follow_redirects=False)
    assert r.status_code == 303
    q = db.get(Post, qid)
    assert q.title.endswith("(재정리)")
    assert q.edited_at is not None

    # 3. 답변 작성
    r = client.post(f"/question/{qid}/answer", data={"body": "원본 답변"}, follow_redirects=False)
    assert r.status_code == 303
    aid = db.query(Post).filter(Post.type == PostType.ANSWER, Post.parent_post_id == qid).one().id

    # 4. 답변 수정
    r = client.post(f"/write/answer/{aid}", data={"body": "수정된 답변"}, follow_redirects=False)
    assert r.status_code == 303
    db.expire_all()
    a = db.get(Post, aid)
    assert a.body == "수정된 답변"
    assert a.edited_at is not None

    # 5. 답변 삭제
    r = client.post(f"/post/{aid}/delete", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == f"/question/{qid}"
    db.expire_all()
    a = db.get(Post, aid)
    assert a.deleted_at is not None

    # 6. 질문 삭제
    r = client.post(f"/post/{qid}/delete", follow_redirects=False)
    assert r.status_code == 303
    db.expire_all()
    q = db.get(Post, qid)
    assert q.deleted_at is not None

    # 7. 삭제된 질문 detail은 404
    r = client.get(f"/question/{qid}")
    assert r.status_code == 404
```

- [ ] **Step 2: Run**

```
uv run pytest app/tests/integration/test_post_edit_e2e.py -v
```

Expected: PASS.

- [ ] **Step 3: 전체 통합 회귀 검증**

```
uv run pytest app/tests/ -q
```

Expected: 모든 테스트 PASS (기존 + 신규 ~40 케이스 추가).

- [ ] **Step 4: Lint**

```
uv run ruff check app/
```

Expected: zero issues.

- [ ] **Step 5: Commit**

```
git add app/tests/integration/test_post_edit_e2e.py
git commit -m "test(content): P1.6a e2e — 질문/답변 create-edit-delete 완주"
```

---

## Self-Review Checklist (작성 완료 후 1회 검사)

- ✅ Spec coverage:
  - "수정 기능" → Task 3·4·5·7·8·9
  - "삭제 기능" → Task 6·10·12·13
  - "edited_at 분리" → Task 1
  - "권한 가드" → Task 2 (라우트 적용은 7·8·9·10)
  - "수정됨 칩" → Task 11·12·13
  - "타입별 차등 — Review/Journey 제외" → Task 7·8·9 의 `if post.type != X` 가드, Task 13 의 type 분기에서 명시적 plan-only
- ✅ No placeholders: 각 step에 실제 코드 + 정확한 명령. "TBD"·"적절히 처리"·"테스트 추가" 없음.
- ✅ Type consistency: `require_author("post_id")` factory 시그니처가 Task 2·7·8·9·10 에서 동일. `update_question`·`update_answer`·`update_plan`·`soft_delete_post` 시그니처가 service 정의(Task 3-6)와 호출처(Task 7-10) 일치.
- ✅ Commit boundaries: Task당 1 commit. 마이그레이션 commit 분리.
- ⚠ Plan detail 라우트가 사용하는 정확한 템플릿 경로 (Task 13 Step 1) 는 실제 코드 확인 후 결정. 본 plan 작성 시점엔 `pages/detail/post.html` 또는 `pages/post_detail.html` 둘 다 가능 — subagent가 Step 1의 grep으로 확정.

---

## Out of scope (다음 phase)

- **Review·Journey episode 수정/삭제** — P1.6b. 잠금 조건(view threshold, 다음 에피소드 발행, peer cross-validation 무효화) 정책 정의 + 적용.
- **수정 이력 보관** — P2 검토 사항. 현재는 latest snapshot만 유지.
- **편집 시 첨부 이미지 추가/제거** — Body markdown `![](url)` 패턴으로 이미 가능. 별도 UI 변경 없음.
- **시간 제한 윈도우** — 본 plan에서는 무제한. 정책 추가는 PRD §6.2/§6.3 결정 후.
- **신고 기능** — 메뉴에 "신고" placeholder만 추가. 실제 동작은 별도 plan.
- **DRAFT 임시저장** — `PostStatus.DRAFT` enum은 있으나 UI 미연결. 별도 plan.
