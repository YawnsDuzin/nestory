# Nestory — P1.5d 관리자 v1 (콘텐츠 숨김 · 사용자 조회 · 신고 큐) 설계

**작성일**: 2026-05-09
**대상 단계**: P1.5d (P1.5 4 sub-plan 중 마지막)
**관련 PRD**: §9.3 Phase 1 — "관리자 v1 (배지 승인 · 콘텐츠 숨김 · 사용자 조회)" · §3.3 Flow C 모더레이션 · §6.4 [B5]
**기존 인프라**: P1.1 `Report` · `AuditLog` · `Announcement` 모델 + `AuditAction` enum (CONTENT_HIDDEN · REPORT_RESOLVED 포함) + `Post.status=HIDDEN` enum + P1.2 `/admin/badge-queue` 라우트 패턴

## 0. 핵심 결정 요약 (자율 결정)

| 항목 | 결정 |
|---|---|
| 범위 (P1.5d) | 콘텐츠 숨김(`/admin/content`) + 사용자 조회(`/admin/users`) + 신고 큐 GET-only(`/admin/reports`). 신고 resolve/reject 액션은 P2 (관리자 v2) |
| 콘텐츠 숨김 패턴 | `Post.status = HIDDEN` 토글 (deleted_at 사용 X — soft-delete는 다른 의미) + `AuditLog(CONTENT_HIDDEN)` 기록 |
| 신고 제출 | P1.5d **미포함** — 모델은 있지만 user-facing 신고 라우트는 P2. P1.5d는 관리자가 미리 만들어둔 신고 row(또는 P1.4 cross-validation 자동 큐잉)를 *조회*만 |
| 사용자 조회 필터 | 검색 (username/email partial) + badge_level 필터 + 페이지네이션 30/page. 비활성화·차단 액션은 P2 |
| 권한 | 모두 `Depends(require_admin)` |
| AuditLog 필수 | 콘텐츠 hide/show 액션 시 매번 기록 (actor_id, action=CONTENT_HIDDEN, target_type=post, target_id, note=optional reason) |
| 마이그레이션 | 0건 — 기존 모델 그대로 |

## 1. 배경 및 동기

PRD §9.3 P1 종료 기준 "관리자 v1" 3영역 중 배지 승인은 P1.2에 완료. 이번 sub-plan으로 나머지 2영역(콘텐츠 숨김 + 사용자 조회) + 보너스 1영역(신고 큐 조회)을 마무리한다.

**핵심 가치**:
1. **운영 사고 대응** — 광고성 후기·욕설 댓글 발견 시 즉시 숨김 처리. 시군 허브 신뢰도 보호.
2. **사용자 진단** — 배지 분쟁 시 관리자가 사용자 활동 이력 빠르게 확인 (배지 신청·작성 글 수).
3. **신고 큐 가시성** — P2 cross-validation 분쟁 자동 큐잉이 들어오면 관리자가 즉시 인지 (P1.5d는 빈 큐 화면이지만 surface 준비).

## 2. 범위

### 2.1 In-scope

- `app/services/admin_moderation.py` 신규 — `hide_post(db, admin, post, reason=None)` · `unhide_post(db, admin, post, reason=None)` · `list_posts(db, *, status=None, page=1)` · `list_users(db, *, q=None, badge_level=None, page=1)` · `list_pending_reports(db, page=1)`
- `app/routers/admin.py` 확장 — 5 라우트:
  - `GET /admin/content` (포스트 목록, 필터: all/hidden/published, 페이지네이션)
  - `POST /admin/content/{post_id}/hide` (status=HIDDEN + AuditLog)
  - `POST /admin/content/{post_id}/unhide` (status=PUBLISHED + AuditLog)
  - `GET /admin/users` (사용자 목록, 검색 + 필터 + 페이지네이션)
  - `GET /admin/reports` (신고 큐 — pending만, GET 전용)
- 3 템플릿:
  - `app/templates/pages/admin_content.html`
  - `app/templates/pages/admin_users.html`
  - `app/templates/pages/admin_reports.html`
- `app/templates/components/nav.html` — 관리자 dropdown에 "콘텐츠"·"사용자"·"신고" 메뉴 추가
- 4 테스트 파일:
  - `test_admin_moderation_service.py` — service 단위
  - `test_admin_content_route.py` — content list + hide/unhide round-trip
  - `test_admin_users_route.py` — search · 필터 · 페이지네이션
  - `test_admin_reports_route.py` — pending 목록 + 빈 큐 표시
- 마이그레이션 0건

### 2.2 Out of scope

- **신고 resolve/reject 액션** — P2 (관리자 v2)
- **사용자 본인 신고 제출 라우트** (`POST /post/{id}/report`) — P2
- **사용자 차단·비활성화 액션** — P2
- **관리자 KPI 대시보드** — P2 (PRD §9.4 명시)
- **공지사항 발행** — P2 (Announcement 모델은 있지만 UI는 P2)
- **콘텐츠 영구 삭제** (DB row delete) — soft-hide만, 영구 삭제는 P2 별도 결정
- **이미지 모더레이션** — 별도 ticket
- **자동 분류** — 관리자 수동 검토만

## 3. Service 레이어

### 3.1 `app/services/admin_moderation.py`

```python
"""Admin moderation service — content hide/unhide + listings.

PRD §9.3 P1 관리자 v1. 신고 resolve는 P2.
"""
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import or_, func, select
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
        action=AuditAction.CONTENT_HIDDEN,  # restore도 동일 action — note로 구분
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

### 3.2 라우트 (확장 — `app/routers/admin.py`)

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

`admin.py` 상단 imports 보강:
```python
from typing import Literal
from app.models._enums import PostStatus
from app.models.user import BadgeLevel
from app.services import admin_moderation
```

## 4. 템플릿

### 4.1 `pages/admin_content.html` 구조

- 헤더: "관리자 · 콘텐츠"
- 필터 탭: all / published / hidden (query string `status_filter`)
- 테이블: 글 ID | type | title | author | region | status | created_at | hide/unhide 버튼
- hidden status면 빨간 배지, published는 초록
- 각 row의 hide/unhide POST form (reason input optional)
- 페이지네이션

### 4.2 `pages/admin_users.html` 구조

- 헤더: "관리자 · 사용자"
- 검색 폼: q (username/email) + badge_level select (4종 + "전체")
- 테이블: ID | username | email | badge | role | created_at | (`/u/{username}` 링크)
- 페이지네이션

### 4.3 `pages/admin_reports.html` 구조

- 헤더: "관리자 · 신고 큐 (Pending)"
- "P2에서 resolve/reject 액션 추가 예정" 안내 박스
- 테이블: ID | reporter | target | reason | detail | created_at
- 페이지네이션
- 빈 상태: "현재 처리 대기 중인 신고가 없습니다."

## 5. 사용자 메뉴 통합 (관리자 dropdown)

`app/templates/components/nav.html`의 관리자 그룹 (`{% if current_user.role.value == 'admin' %}`)에 추가:

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

기존 `/admin/badge-queue` 링크 다음에.

## 6. 테스트 전략

| Test file | Verifies |
|---|---|
| `test_admin_moderation_service.py` | hide_post / unhide_post status 전환 + AuditLog row 생성 · list_posts status_filter · list_users 검색 · list_pending_reports |
| `test_admin_content_route.py` | GET 인증·인가 (admin only) · POST hide → 303 + status HIDDEN + AuditLog row · unhide round-trip · 404 unknown post |
| `test_admin_users_route.py` | GET 인증·인가 · 검색 q · badge_level 필터 · 페이지네이션 |
| `test_admin_reports_route.py` | GET 인증·인가 · pending만 표시 · 빈 큐 메시지 |

## 7. DoD

- [ ] 5 라우트 모두 정상 동작 (GET 200 + POST 303 + 404 + 403 분기)
- [ ] 관리자 외 접근 시 403 (require_admin 가드)
- [ ] hide/unhide 액션마다 AuditLog row 생성
- [ ] 마이그레이션 0건 (Post.status enum + AuditLog 모델 그대로)
- [ ] 4 테스트 파일 모두 PASS (Docker 미가용 시 deferred)
- [ ] 기존 `/admin/badge-queue` 회귀 없음
- [ ] 사용자 메뉴 dropdown에 3 신규 링크 노출 (admin role only)

## 8. 구현 task 추정

8-9 task:

1. `app/services/admin_moderation.py` + service 단위 테스트
2. `/admin/content` 라우트 + hide/unhide POST 핸들러
3. `pages/admin_content.html` 템플릿
4. `/admin/users` 라우트 + `pages/admin_users.html`
5. `/admin/reports` 라우트 + `pages/admin_reports.html`
6. nav.html admin dropdown 3 링크 추가
7. 라우트 통합 테스트 3개
8. DoD + handoff 갱신
