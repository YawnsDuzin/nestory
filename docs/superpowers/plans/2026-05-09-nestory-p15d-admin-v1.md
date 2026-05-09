# P1.5d Admin v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** PRD §9.3 P1 종료 기준 "관리자 v1 (배지 승인 · 콘텐츠 숨김 · 사용자 조회)" 중 미완료 2영역(콘텐츠 숨김 + 사용자 조회) + 보너스 신고 큐 GET-only.

**Architecture:** `admin_moderation` 서비스 (hide_post/unhide_post + 3 list helpers) · 5 라우트 (`/admin/content` GET/POST hide/POST unhide · `/admin/users` GET · `/admin/reports` GET) · 3 템플릿 · nav admin dropdown 3 링크 · `Post.status=HIDDEN` + `AuditLog(CONTENT_HIDDEN)` 패턴.

**Tech Stack:** FastAPI + SQLAlchemy 2.x + Jinja2 SSR + Tailwind. 마이그레이션 0건.

**Spec reference:** `docs/superpowers/specs/2026-05-09-nestory-p15d-admin-v1-design.md`

---

## File Structure

| Path | Role | Status |
|---|---|---|
| `app/services/admin_moderation.py` | hide/unhide_post + 3 list helpers + 3 result dataclasses | Create |
| `app/routers/admin.py` | 5 신규 라우트 추가 (기존 `/admin/badge-queue` 유지) | Modify |
| `app/templates/pages/admin_content.html` | 콘텐츠 목록 + hide/unhide form | Create |
| `app/templates/pages/admin_users.html` | 사용자 검색 · 필터 · 목록 | Create |
| `app/templates/pages/admin_reports.html` | 신고 큐 GET (pending only) | Create |
| `app/templates/components/nav.html` | admin dropdown 3 링크 추가 | Modify |
| `app/tests/integration/test_admin_moderation_service.py` | service 단위 | Create |
| `app/tests/integration/test_admin_content_route.py` | content 라우트 | Create |
| `app/tests/integration/test_admin_users_route.py` | users 라우트 | Create |
| `app/tests/integration/test_admin_reports_route.py` | reports 라우트 | Create |

---

## Task 1: `admin_moderation` service + 단위 테스트

**Files:**
- Create: `app/services/admin_moderation.py`
- Create: `app/tests/integration/test_admin_moderation_service.py`

- [ ] **Step 1: Write service**

```python
"""Admin moderation service — content hide/unhide + listings.

PRD §9.3 P1 관리자 v1. 신고 resolve는 P2.
"""
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Post, Report, User
from app.models._enums import (
    AuditAction,
    PostStatus,
    ReportStatus,
)
from app.models.user import BadgeLevel

PAGE_SIZE = 30


@dataclass(frozen=True)
class PostListResult:
    posts: list[Post]
    total: int


@dataclass(frozen=True)
class UserListResult:
    users: list[User]
    total: int


@dataclass(frozen=True)
class ReportListResult:
    reports: list[Report]
    total: int


def hide_post(
    db: Session, admin: User, post: Post, reason: str | None = None
) -> Post:
    """Set post.status = HIDDEN + write AuditLog. Idempotent."""
    if post.status != PostStatus.HIDDEN:
        post.status = PostStatus.HIDDEN
    db.add(AuditLog(
        actor_id=admin.id,
        action=AuditAction.CONTENT_HIDDEN,
        target_type="post",
        target_id=post.id,
        note=reason,
    ))
    db.flush()
    return post


def unhide_post(
    db: Session, admin: User, post: Post, reason: str | None = None
) -> Post:
    """Restore post.status = PUBLISHED + write AuditLog."""
    post.status = PostStatus.PUBLISHED
    db.add(AuditLog(
        actor_id=admin.id,
        action=AuditAction.CONTENT_HIDDEN,
        target_type="post",
        target_id=post.id,
        note=f"unhide: {reason}" if reason else "unhide",
    ))
    db.flush()
    return post


def list_posts(
    db: Session,
    *,
    status_filter: Literal["all", "published", "hidden"] = "all",
    page: int = 1,
) -> PostListResult:
    base = select(Post).where(Post.deleted_at.is_(None))
    if status_filter == "published":
        base = base.where(Post.status == PostStatus.PUBLISHED)
    elif status_filter == "hidden":
        base = base.where(Post.status == PostStatus.HIDDEN)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(
            base.order_by(Post.created_at.desc())
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        ).all()
    )
    return PostListResult(posts=rows, total=total)


def list_users(
    db: Session,
    *,
    q: str | None = None,
    badge_level: BadgeLevel | None = None,
    page: int = 1,
) -> UserListResult:
    base = select(User).where(User.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        base = base.where(or_(User.username.ilike(like), User.email.ilike(like)))
    if badge_level is not None:
        base = base.where(User.badge_level == badge_level)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(
            base.order_by(User.created_at.desc())
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        ).all()
    )
    return UserListResult(users=rows, total=total)


def list_pending_reports(db: Session, *, page: int = 1) -> ReportListResult:
    base = select(Report).where(Report.status == ReportStatus.PENDING)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(
            base.order_by(Report.created_at.desc())
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        ).all()
    )
    return ReportListResult(reports=rows, total=total)


__all__ = [
    "PAGE_SIZE",
    "PostListResult",
    "ReportListResult",
    "UserListResult",
    "hide_post",
    "list_pending_reports",
    "list_posts",
    "list_users",
    "unhide_post",
]
```

- [ ] **Step 2: Write service unit tests**

```python
"""Tests for admin_moderation service.

NOTE: Requires running Postgres.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog
from app.models._enums import AuditAction, PostStatus, ReportStatus
from app.models.user import BadgeLevel
from app.services import admin_moderation as ams
from app.tests.factories import (
    AdminUserFactory,
    ReportFactory,
    ResidentUserFactory,
    ReviewPostFactory,
    UserFactory,
)


def test_hide_post_sets_status_and_audits(db: Session) -> None:
    admin = AdminUserFactory()
    author = ResidentUserFactory()
    post = ReviewPostFactory(author=author, status=PostStatus.PUBLISHED)
    db.flush()

    ams.hide_post(db, admin, post, reason="ad spam")
    assert post.status == PostStatus.HIDDEN
    audits = list(
        db.scalars(
            select(AuditLog).where(
                AuditLog.target_id == post.id,
                AuditLog.action == AuditAction.CONTENT_HIDDEN,
            )
        ).all()
    )
    assert len(audits) == 1
    assert audits[0].actor_id == admin.id
    assert audits[0].note == "ad spam"


def test_hide_post_idempotent(db: Session) -> None:
    admin = AdminUserFactory()
    author = ResidentUserFactory()
    post = ReviewPostFactory(author=author, status=PostStatus.HIDDEN)
    db.flush()
    ams.hide_post(db, admin, post)
    assert post.status == PostStatus.HIDDEN  # still hidden, no error


def test_unhide_post_restores_status(db: Session) -> None:
    admin = AdminUserFactory()
    author = ResidentUserFactory()
    post = ReviewPostFactory(author=author, status=PostStatus.HIDDEN)
    db.flush()
    ams.unhide_post(db, admin, post, reason="false positive")
    assert post.status == PostStatus.PUBLISHED
    audits = list(
        db.scalars(
            select(AuditLog).where(
                AuditLog.target_id == post.id,
                AuditLog.action == AuditAction.CONTENT_HIDDEN,
            )
        ).all()
    )
    assert any("unhide" in (a.note or "") for a in audits)


def test_list_posts_filters_by_status(db: Session) -> None:
    author = ResidentUserFactory()
    p_pub = ReviewPostFactory(author=author, status=PostStatus.PUBLISHED)
    p_hidden = ReviewPostFactory(author=author, status=PostStatus.HIDDEN)
    db.flush()

    res_all = ams.list_posts(db, status_filter="all")
    assert res_all.total == 2
    res_pub = ams.list_posts(db, status_filter="published")
    assert res_pub.total == 1
    assert res_pub.posts[0].id == p_pub.id
    res_hidden = ams.list_posts(db, status_filter="hidden")
    assert res_hidden.total == 1
    assert res_hidden.posts[0].id == p_hidden.id


def test_list_users_searches_username(db: Session) -> None:
    UserFactory(username="alice123", email="a@x.com")
    UserFactory(username="bob456", email="b@x.com")
    db.flush()
    res = ams.list_users(db, q="alice")
    assert res.total == 1
    assert res.users[0].username == "alice123"


def test_list_users_filters_by_badge_level(db: Session) -> None:
    UserFactory(badge_level=BadgeLevel.INTERESTED)
    ResidentUserFactory()
    db.flush()
    res = ams.list_users(db, badge_level=BadgeLevel.RESIDENT)
    assert res.total == 1
    assert res.users[0].badge_level == BadgeLevel.RESIDENT


def test_list_pending_reports(db: Session) -> None:
    reporter = UserFactory()
    ReportFactory(reporter=reporter, status=ReportStatus.PENDING)
    ReportFactory(reporter=reporter, status=ReportStatus.RESOLVED)
    db.flush()
    res = ams.list_pending_reports(db)
    assert res.total == 1
    assert res.reports[0].status == ReportStatus.PENDING
```

- [ ] **Step 3: Static + lint**

Run: `uv run python -c "from app.services.admin_moderation import hide_post, unhide_post, list_posts, list_users, list_pending_reports; print('ok')"` → `ok`
Run: `uv run ruff check app/services/admin_moderation.py app/tests/integration/test_admin_moderation_service.py` → clean

- [ ] **Step 4: Commit**

```bash
git add app/services/admin_moderation.py app/tests/integration/test_admin_moderation_service.py
git commit -m "feat(services): add admin_moderation (hide/unhide + 3 list helpers)

hide_post / unhide_post: Post.status 토글 + AuditLog(CONTENT_HIDDEN) 기록.
list_posts(status_filter) / list_users(q, badge_level) / list_pending_reports.
7 unit 테스트.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15d-admin-v1-design.md §3.1"
```

---

## Task 2: `/admin/content` 라우트 + hide/unhide 핸들러

**Files:**
- Modify: `app/routers/admin.py`

- [ ] **Step 1: Read current `app/routers/admin.py`**

Confirm imports + router prefix=/admin (already exists from P1.2).

- [ ] **Step 2: Add imports at top (with existing imports)**

```python
from typing import Literal

from app.models._enums import PostStatus  # noqa: F401  # used in service signature
from app.models import Post  # add Post if not already imported
from app.models.user import BadgeLevel
from app.services import admin_moderation
```

(Verify which are already imported. Add only what's missing.)

- [ ] **Step 3: Append the 3 routes (content list, hide POST, unhide POST)**

```python
@router.get("/content", response_class=HTMLResponse)
def admin_content(
    request: Request,
    status_filter: Literal["all", "published", "hidden"] = "all",
    page: int = 1,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    result = admin_moderation.list_posts(
        db, status_filter=status_filter, page=page
    )
    return templates.TemplateResponse(
        request, "pages/admin_content.html",
        {
            "posts": result.posts, "total": result.total,
            "page": page, "page_size": admin_moderation.PAGE_SIZE,
            "status_filter": status_filter,
            "current_user": current_user,
        },
    )


@router.post("/content/{post_id}/hide", response_model=None)
def admin_content_hide(
    post_id: int,
    reason: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(404, "글을 찾을 수 없습니다")
    admin_moderation.hide_post(db, current_user, post, reason=reason or None)
    db.commit()
    return RedirectResponse("/admin/content?status_filter=hidden", status_code=303)


@router.post("/content/{post_id}/unhide", response_model=None)
def admin_content_unhide(
    post_id: int,
    reason: str = Form(""),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(404, "글을 찾을 수 없습니다")
    admin_moderation.unhide_post(db, current_user, post, reason=reason or None)
    db.commit()
    return RedirectResponse("/admin/content?status_filter=published", status_code=303)
```

- [ ] **Step 4: Static check + lint**

Run: `uv run python -c "
from app.main import app
admin_paths = sorted(p for p in (getattr(r, 'path', '') for r in app.routes) if '/admin/content' in p)
print('admin/content routes:', admin_paths)
"`
Expected: `['/admin/content', '/admin/content/{post_id}/hide', '/admin/content/{post_id}/unhide']`
Lint: `uv run ruff check app/routers/admin.py` → clean

- [ ] **Step 5: Commit**

```bash
git add app/routers/admin.py
git commit -m "feat(admin): add /admin/content list + hide/unhide POST routes

GET filter all/published/hidden + 페이지네이션.
POST /content/{id}/hide|unhide → 303 + service hide_post/unhide_post.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15d-admin-v1-design.md §3.2"
```

---

## Task 3: `pages/admin_content.html` 템플릿

**Files:**
- Create: `app/templates/pages/admin_content.html`

- [ ] **Step 1: Write template**

```html
{% extends "base.html" %}
{% block title %}관리자 · 콘텐츠 · Nestory{% endblock %}
{% block content %}
<section class="space-y-4">
  <header class="flex items-center justify-between">
    <h1 class="text-2xl font-bold text-slate-900">콘텐츠 모더레이션</h1>
    <span class="text-sm text-slate-500">총 {{ total }}건</span>
  </header>

  <nav class="flex gap-2 text-sm">
    {% for f, label in [('all', '전체'), ('published', '게시됨'), ('hidden', '숨김')] %}
      <a href="/admin/content?status_filter={{ f }}"
         class="rounded border px-3 py-1
                {% if status_filter == f %}bg-emerald-600 text-white border-emerald-600
                {% else %}bg-white text-slate-700 hover:bg-slate-50{% endif %}">
        {{ label }}
      </a>
    {% endfor %}
  </nav>

  {% if posts %}
    <table class="w-full text-sm bg-white border rounded">
      <thead class="bg-slate-50 text-slate-600">
        <tr>
          <th class="text-left px-3 py-2">ID</th>
          <th class="text-left px-3 py-2">type</th>
          <th class="text-left px-3 py-2">제목</th>
          <th class="text-left px-3 py-2">작성자</th>
          <th class="text-left px-3 py-2">상태</th>
          <th class="text-left px-3 py-2">작성일</th>
          <th class="text-left px-3 py-2">액션</th>
        </tr>
      </thead>
      <tbody>
        {% for post in posts %}
          <tr class="border-t {% if post.status.value == 'hidden' %}bg-rose-50{% endif %}">
            <td class="px-3 py-2 text-slate-500">{{ post.id }}</td>
            <td class="px-3 py-2 text-xs">{{ post.type.value }}</td>
            <td class="px-3 py-2">
              <a href="/post/{{ post.id }}" class="text-emerald-700 hover:underline">{{ post.title or '(제목 없음)' }}</a>
            </td>
            <td class="px-3 py-2 text-xs text-slate-600">user#{{ post.author_id }}</td>
            <td class="px-3 py-2">
              {% if post.status.value == 'hidden' %}
                <span class="rounded bg-rose-100 text-rose-700 px-2 py-0.5 text-xs">숨김</span>
              {% elif post.status.value == 'published' %}
                <span class="rounded bg-emerald-100 text-emerald-700 px-2 py-0.5 text-xs">게시</span>
              {% else %}
                <span class="rounded bg-slate-100 text-slate-700 px-2 py-0.5 text-xs">{{ post.status.value }}</span>
              {% endif %}
            </td>
            <td class="px-3 py-2 text-xs text-slate-500">
              {{ post.created_at.strftime('%Y-%m-%d') if post.created_at else '' }}
            </td>
            <td class="px-3 py-2">
              {% if post.status.value == 'hidden' %}
                <form method="post" action="/admin/content/{{ post.id }}/unhide" class="inline">
                  <button type="submit" class="rounded bg-emerald-600 px-2 py-1 text-xs text-white hover:bg-emerald-700">복원</button>
                </form>
              {% else %}
                <form method="post" action="/admin/content/{{ post.id }}/hide" class="inline">
                  <button type="submit" class="rounded bg-rose-600 px-2 py-1 text-xs text-white hover:bg-rose-700">숨김</button>
                </form>
              {% endif %}
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>

    {% with base_url='/admin/content', query_params={'status_filter': status_filter} %}
      {% include "partials/pagination.html" %}
    {% endwith %}
  {% else %}
    <div class="rounded border bg-white p-8 text-center text-slate-500">
      게시글이 없습니다.
    </div>
  {% endif %}
</section>
{% endblock %}
```

- [ ] **Step 2: Static**

Run: `uv run python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('app/templates'))
env.get_template('pages/admin_content.html')
print('ok')
"` → `ok`

- [ ] **Step 3: Commit**

```bash
git add app/templates/pages/admin_content.html
git commit -m "feat(admin): add /admin/content template

필터 탭 + 글 테이블 + hide/unhide form + 페이지네이션.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15d-admin-v1-design.md §4.1"
```

---

## Task 4: `/admin/users` 라우트 + 템플릿

**Files:**
- Modify: `app/routers/admin.py`
- Create: `app/templates/pages/admin_users.html`

- [ ] **Step 1: Add route to `app/routers/admin.py`** (append):

```python
@router.get("/users", response_class=HTMLResponse)
def admin_users(
    request: Request,
    q: str | None = None,
    badge_level: str | None = None,
    page: int = 1,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    bl_enum: BadgeLevel | None = None
    if badge_level:
        try:
            bl_enum = BadgeLevel(badge_level)
        except ValueError:
            bl_enum = None
    result = admin_moderation.list_users(
        db, q=q, badge_level=bl_enum, page=page,
    )
    return templates.TemplateResponse(
        request, "pages/admin_users.html",
        {
            "users": result.users, "total": result.total,
            "page": page, "page_size": admin_moderation.PAGE_SIZE,
            "q": q or "", "badge_level": badge_level or "",
            "current_user": current_user,
        },
    )
```

- [ ] **Step 2: Write template**

```html
{# app/templates/pages/admin_users.html #}
{% extends "base.html" %}
{% block title %}관리자 · 사용자 · Nestory{% endblock %}
{% block content %}
<section class="space-y-4">
  <header class="flex items-center justify-between">
    <h1 class="text-2xl font-bold text-slate-900">사용자 조회</h1>
    <span class="text-sm text-slate-500">총 {{ total }}명</span>
  </header>

  <form method="get" action="/admin/users" class="flex flex-wrap gap-2 items-end">
    <div>
      <label class="block text-xs text-slate-600">검색 (username/email)</label>
      <input type="text" name="q" value="{{ q }}"
             class="rounded border px-3 py-2 text-sm w-64">
    </div>
    <div>
      <label class="block text-xs text-slate-600">배지</label>
      <select name="badge_level" class="rounded border px-3 py-2 text-sm">
        <option value="" {% if not badge_level %}selected{% endif %}>전체</option>
        <option value="interested" {% if badge_level == 'interested' %}selected{% endif %}>관심자</option>
        <option value="region_verified" {% if badge_level == 'region_verified' %}selected{% endif %}>시군 인증</option>
        <option value="resident" {% if badge_level == 'resident' %}selected{% endif %}>거주자</option>
        <option value="ex_resident" {% if badge_level == 'ex_resident' %}selected{% endif %}>전 거주자</option>
      </select>
    </div>
    <button type="submit" class="rounded bg-emerald-600 px-3 py-2 text-white text-sm hover:bg-emerald-700">조회</button>
  </form>

  {% if users %}
    <table class="w-full text-sm bg-white border rounded">
      <thead class="bg-slate-50 text-slate-600">
        <tr>
          <th class="text-left px-3 py-2">ID</th>
          <th class="text-left px-3 py-2">username</th>
          <th class="text-left px-3 py-2">email</th>
          <th class="text-left px-3 py-2">배지</th>
          <th class="text-left px-3 py-2">role</th>
          <th class="text-left px-3 py-2">가입일</th>
        </tr>
      </thead>
      <tbody>
        {% for u in users %}
          <tr class="border-t hover:bg-slate-50">
            <td class="px-3 py-2 text-slate-500">{{ u.id }}</td>
            <td class="px-3 py-2">
              <a href="/u/{{ u.username }}" class="text-emerald-700 hover:underline">@{{ u.username }}</a>
            </td>
            <td class="px-3 py-2 text-xs text-slate-600">{{ u.email }}</td>
            <td class="px-3 py-2 text-xs">{{ u.badge_level.value }}</td>
            <td class="px-3 py-2 text-xs">{{ u.role.value }}</td>
            <td class="px-3 py-2 text-xs text-slate-500">
              {{ u.created_at.strftime('%Y-%m-%d') if u.created_at else '' }}
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>

    {% with base_url='/admin/users', query_params={'q': q, 'badge_level': badge_level} %}
      {% include "partials/pagination.html" %}
    {% endwith %}
  {% else %}
    <div class="rounded border bg-white p-8 text-center text-slate-500">
      조건에 맞는 사용자가 없습니다.
    </div>
  {% endif %}
</section>
{% endblock %}
```

- [ ] **Step 3: Static + lint**

Run: `uv run python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('app/templates'))
env.get_template('pages/admin_users.html')
from app.main import app
paths = [getattr(r, 'path', '') for r in app.routes]
assert '/admin/users' in paths
print('ok')
"` → `ok`

Lint: `uv run ruff check app/routers/admin.py` → clean

- [ ] **Step 4: Commit**

```bash
git add app/routers/admin.py app/templates/pages/admin_users.html
git commit -m "feat(admin): add /admin/users route + template

검색 (q username/email partial) + badge_level 필터 + 페이지네이션.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15d-admin-v1-design.md §3.2, §4.2"
```

---

## Task 5: `/admin/reports` 라우트 + 템플릿

**Files:**
- Modify: `app/routers/admin.py`
- Create: `app/templates/pages/admin_reports.html`

- [ ] **Step 1: Add route to `admin.py`**:

```python
@router.get("/reports", response_class=HTMLResponse)
def admin_reports(
    request: Request,
    page: int = 1,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    result = admin_moderation.list_pending_reports(db, page=page)
    return templates.TemplateResponse(
        request, "pages/admin_reports.html",
        {
            "reports": result.reports, "total": result.total,
            "page": page, "page_size": admin_moderation.PAGE_SIZE,
            "current_user": current_user,
        },
    )
```

- [ ] **Step 2: Write template**

```html
{# app/templates/pages/admin_reports.html #}
{% extends "base.html" %}
{% block title %}관리자 · 신고 큐 · Nestory{% endblock %}
{% block content %}
<section class="space-y-4">
  <header class="flex items-center justify-between">
    <h1 class="text-2xl font-bold text-slate-900">신고 큐 (Pending)</h1>
    <span class="text-sm text-slate-500">총 {{ total }}건</span>
  </header>

  <div class="rounded bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900">
    <p>resolve · reject 액션은 P2 (관리자 v2)에서 추가됩니다. 현재는 조회만 가능합니다.</p>
  </div>

  {% if reports %}
    <table class="w-full text-sm bg-white border rounded">
      <thead class="bg-slate-50 text-slate-600">
        <tr>
          <th class="text-left px-3 py-2">ID</th>
          <th class="text-left px-3 py-2">신고자</th>
          <th class="text-left px-3 py-2">대상</th>
          <th class="text-left px-3 py-2">사유</th>
          <th class="text-left px-3 py-2">상세</th>
          <th class="text-left px-3 py-2">신고일</th>
        </tr>
      </thead>
      <tbody>
        {% for r in reports %}
          <tr class="border-t hover:bg-slate-50">
            <td class="px-3 py-2 text-slate-500">{{ r.id }}</td>
            <td class="px-3 py-2 text-xs">user#{{ r.reporter_id }}</td>
            <td class="px-3 py-2 text-xs">{{ r.target_type }}#{{ r.target_id }}</td>
            <td class="px-3 py-2 text-xs">{{ r.reason.value }}</td>
            <td class="px-3 py-2 text-xs text-slate-600">{{ (r.detail or '')[:80] }}</td>
            <td class="px-3 py-2 text-xs text-slate-500">
              {{ r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else '' }}
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>

    {% with base_url='/admin/reports' %}
      {% include "partials/pagination.html" %}
    {% endwith %}
  {% else %}
    <div class="rounded border bg-white p-8 text-center text-slate-500">
      현재 처리 대기 중인 신고가 없습니다.
    </div>
  {% endif %}
</section>
{% endblock %}
```

- [ ] **Step 3: Static + lint**

Run: `uv run python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('app/templates'))
env.get_template('pages/admin_reports.html')
from app.main import app
paths = [getattr(r, 'path', '') for r in app.routes]
assert '/admin/reports' in paths
print('ok')
"` → `ok`
Lint: `uv run ruff check app/routers/admin.py` → clean

- [ ] **Step 4: Commit**

```bash
git add app/routers/admin.py app/templates/pages/admin_reports.html
git commit -m "feat(admin): add /admin/reports GET-only route + template

Pending 신고만 표시. resolve/reject 액션은 P2 (관리자 v2).

Refs: docs/superpowers/specs/2026-05-09-nestory-p15d-admin-v1-design.md §3.2, §4.3"
```

---

## Task 6: nav admin dropdown 3 링크 추가

**Files:**
- Modify: `app/templates/components/nav.html`

- [ ] **Step 1: Read current nav.html** — locate the admin group block:
```html
{% if current_user.role.value == 'admin' %}
  <div class="border-t border-slate-100 py-1">
    <a href="/admin/badge-queue" ...>...배지 큐</a>
    <a href="/docs" ...>...API Docs</a>
  </div>
{% endif %}
```

- [ ] **Step 2: Insert 3 new links between badge-queue and API Docs**

```html
                <a href="/admin/content" class="flex items-center gap-3 px-4 py-2 text-slate-700 hover:bg-slate-50">
                  <span class="w-5 text-center">📄</span>
                  <span>콘텐츠</span>
                </a>
                <a href="/admin/users" class="flex items-center gap-3 px-4 py-2 text-slate-700 hover:bg-slate-50">
                  <span class="w-5 text-center">👥</span>
                  <span>사용자</span>
                </a>
                <a href="/admin/reports" class="flex items-center gap-3 px-4 py-2 text-slate-700 hover:bg-slate-50">
                  <span class="w-5 text-center">🚨</span>
                  <span>신고 큐</span>
                </a>
```

(Place AFTER the badge-queue link, BEFORE the API Docs link.)

- [ ] **Step 3: Commit**

```bash
git add app/templates/components/nav.html
git commit -m "feat(ui): add admin dropdown links — content/users/reports

관리자 메뉴에 콘텐츠·사용자·신고 큐 진입 링크 3개 추가 (admin role only).

Refs: docs/superpowers/specs/2026-05-09-nestory-p15d-admin-v1-design.md §5"
```

---

## Task 7: Route integration tests

**Files:**
- Create: `app/tests/integration/test_admin_content_route.py`
- Create: `app/tests/integration/test_admin_users_route.py`
- Create: `app/tests/integration/test_admin_reports_route.py`

- [ ] **Step 1: Write `test_admin_content_route.py`**

```python
"""Integration tests for /admin/content routes.

NOTE: Requires running Postgres.
"""
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Post
from app.models._enums import AuditAction, PostStatus
from app.tests.factories import (
    AdminUserFactory,
    ResidentUserFactory,
    ReviewPostFactory,
    UserFactory,
)


def test_content_list_requires_admin(client: TestClient, db: Session, login) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.get("/admin/content")
    assert r.status_code == 403


def test_content_list_admin_renders(client: TestClient, db: Session, login) -> None:
    admin = AdminUserFactory()
    author = ResidentUserFactory()
    ReviewPostFactory(author=author, status=PostStatus.PUBLISHED)
    db.commit()
    login(admin.id)
    r = client.get("/admin/content")
    assert r.status_code == 200
    assert "콘텐츠" in r.text


def test_content_filter_hidden(client: TestClient, db: Session, login) -> None:
    admin = AdminUserFactory()
    author = ResidentUserFactory()
    p_pub = ReviewPostFactory(author=author, status=PostStatus.PUBLISHED, title="VISIBLE_POST")
    p_hidden = ReviewPostFactory(author=author, status=PostStatus.HIDDEN, title="HIDDEN_POST")
    db.commit()
    login(admin.id)
    r = client.get("/admin/content?status_filter=hidden")
    assert r.status_code == 200
    assert "HIDDEN_POST" in r.text
    assert "VISIBLE_POST" not in r.text


def test_hide_post_redirects_and_writes_audit(
    client: TestClient, db: Session, login
) -> None:
    admin = AdminUserFactory()
    author = ResidentUserFactory()
    post = ReviewPostFactory(author=author, status=PostStatus.PUBLISHED)
    db.commit()
    login(admin.id)
    r = client.post(
        f"/admin/content/{post.id}/hide",
        data={"reason": "test"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(post)
    assert post.status == PostStatus.HIDDEN
    audits = list(
        db.scalars(
            select(AuditLog).where(
                AuditLog.target_id == post.id,
                AuditLog.action == AuditAction.CONTENT_HIDDEN,
            )
        ).all()
    )
    assert len(audits) >= 1


def test_unhide_post_restores(client: TestClient, db: Session, login) -> None:
    admin = AdminUserFactory()
    author = ResidentUserFactory()
    post = ReviewPostFactory(author=author, status=PostStatus.HIDDEN)
    db.commit()
    login(admin.id)
    r = client.post(
        f"/admin/content/{post.id}/unhide", follow_redirects=False
    )
    assert r.status_code == 303
    db.refresh(post)
    assert post.status == PostStatus.PUBLISHED


def test_hide_unknown_post_returns_404(
    client: TestClient, db: Session, login
) -> None:
    admin = AdminUserFactory()
    db.commit()
    login(admin.id)
    r = client.post("/admin/content/99999/hide")
    assert r.status_code == 404
```

- [ ] **Step 2: Write `test_admin_users_route.py`**

```python
"""Integration tests for /admin/users route."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.tests.factories import (
    AdminUserFactory,
    ResidentUserFactory,
    UserFactory,
)


def test_users_list_requires_admin(client: TestClient, db: Session, login) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.get("/admin/users")
    assert r.status_code == 403


def test_users_list_renders(client: TestClient, db: Session, login) -> None:
    admin = AdminUserFactory()
    UserFactory(username="searchable_user")
    db.commit()
    login(admin.id)
    r = client.get("/admin/users")
    assert r.status_code == 200
    assert "사용자 조회" in r.text


def test_users_search_q_filters(client: TestClient, db: Session, login) -> None:
    admin = AdminUserFactory()
    UserFactory(username="alice_xyz", email="alice@x.com")
    UserFactory(username="bob_xyz", email="bob@x.com")
    db.commit()
    login(admin.id)
    r = client.get("/admin/users?q=alice")
    assert r.status_code == 200
    assert "alice_xyz" in r.text
    assert "bob_xyz" not in r.text


def test_users_filter_by_badge_level(client: TestClient, db: Session, login) -> None:
    admin = AdminUserFactory()
    UserFactory()  # interested
    ResidentUserFactory(username="resident_user")
    db.commit()
    login(admin.id)
    r = client.get("/admin/users?badge_level=resident")
    assert r.status_code == 200
    assert "resident_user" in r.text
```

- [ ] **Step 3: Write `test_admin_reports_route.py`**

```python
"""Integration tests for /admin/reports route."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import ReportStatus
from app.tests.factories import (
    AdminUserFactory,
    ReportFactory,
    UserFactory,
)


def test_reports_requires_admin(client: TestClient, db: Session, login) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.get("/admin/reports")
    assert r.status_code == 403


def test_reports_empty_queue_message(
    client: TestClient, db: Session, login
) -> None:
    admin = AdminUserFactory()
    db.commit()
    login(admin.id)
    r = client.get("/admin/reports")
    assert r.status_code == 200
    assert "현재 처리 대기 중인 신고가 없습니다" in r.text


def test_reports_pending_only(client: TestClient, db: Session, login) -> None:
    admin = AdminUserFactory()
    reporter = UserFactory()
    ReportFactory(reporter=reporter, status=ReportStatus.PENDING)
    ReportFactory(reporter=reporter, status=ReportStatus.RESOLVED)
    db.commit()
    login(admin.id)
    r = client.get("/admin/reports")
    assert r.status_code == 200
    # Total badge should reflect pending count = 1
    assert "총 1건" in r.text
```

- [ ] **Step 4: Lint**

Run: `uv run ruff check app/tests/integration/test_admin_content_route.py app/tests/integration/test_admin_users_route.py app/tests/integration/test_admin_reports_route.py` → clean

- [ ] **Step 5: Commit**

```bash
git add app/tests/integration/test_admin_content_route.py app/tests/integration/test_admin_users_route.py app/tests/integration/test_admin_reports_route.py
git commit -m "test: add admin v1 route integration tests (16 cases)

content (6) + users (4) + reports (3) + service unit (7 from Task 1) = 20 신규 테스트 누계.
require_admin 가드 · 검색·필터 · hide/unhide audit log.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15d-admin-v1-design.md §6"
```

---

## Task 8: Full sweep + DoD update

**Files:** none

- [ ] **Step 1: Full lint**

Run: `uv run ruff check app/`
Expected: no NEW errors. (Pre-existing me.py:82 E501 may persist — flag if more.)

- [ ] **Step 2: Static route registration check**

Run: `uv run python -c "
from app.main import app
admin_paths = sorted(p for p in (getattr(r, 'path', '') for r in app.routes) if p.startswith('/admin'))
print(admin_paths)
"`
Expected:
```
['/admin/badge-queue', '/admin/badge-queue/{application_id}',
 '/admin/badge-queue/{application_id}/approve',
 '/admin/badge-queue/{application_id}/reject',
 '/admin/content', '/admin/content/{post_id}/hide',
 '/admin/content/{post_id}/unhide',
 '/admin/reports', '/admin/users']
```
(Order may vary; ensure all 9 paths present. badge-queue paths from P1.2.)

- [ ] **Step 3: DoD checklist update**

Update plan DoD ⏸ → ✅ where appropriate.

- [ ] **Step 4: Commit DoD**

```bash
git add docs/superpowers/plans/2026-05-09-nestory-p15d-admin-v1.md
git commit -m "docs(plans): mark P1.5d Admin v1 DoD — code complete

5 라우트 등록 + 3 templates + 4 테스트 파일 (20 신규 테스트). 마이그레이션 0.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15d-admin-v1-design.md §7"
```

---

## DoD checklist

- [ ] 5 라우트 모두 등록 + GET 200 / POST 303 / 404 / 403 분기
- [ ] 관리자 외 접근 시 403
- [ ] hide/unhide 액션마다 AuditLog row 생성
- [ ] 마이그레이션 0건
- [ ] 4 테스트 파일 PASS (Docker 미가용 시 deferred)
- [ ] 기존 `/admin/badge-queue` 회귀 없음
- [ ] nav admin dropdown 3 신규 링크 노출
