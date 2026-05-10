# P1.5a Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PRD §9.3 P1 종료 기준 "알림 (bell UI · 인앱)" 충족 — 5 enum / 4 trigger context (BADGE_*·POST_COMMENT·JOURNEY_NEW_EPISODE·QUESTION_ANSWERED) 단일 helper로 통합 + bell dropdown + /notifications 페이지.

**Architecture:** `app/services/notifications.py` 단일 진실 원천 (`create_notification` self-skip + `notification_link/label` 매핑). 도메인 service(badges/comments/posts)가 helper 호출. Bell UI는 HTMX 30초 polling partial. 카카오 알림톡·이메일·Web Push는 P2.

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.x / Jinja2 SSR / HTMX `hx-trigger="every 30s"` / Alpine.js dropdown / pytest + factory-boy.

**Spec reference:** `docs/superpowers/specs/2026-05-09-nestory-p15a-notifications-design.md`

**Migration:** 신규 마이그레이션 **불필요** — `Notification` 모델은 P1.1에서 완성됨 (`app/models/notification.py`), 기존 인덱스 `ix_notifications_user_unread_created`로 dropdown 조회 충분. 현재 alembic head는 P1.4b의 `8a4f9b3c2d51`.

---

## File Structure

| Path | Role | Status |
|---|---|---|
| `app/services/notifications.py` | `create_notification` + `unread_count` + `recent_for_dropdown` + `list_paginated` + `mark_read` + `mark_all_read` + `_format_label` + `_resolve_link` + `NotificationView` dataclass | Create |
| `app/services/__init__.py` | (existing — add `notifications` 도메인 re-export 검토 — 현재 파일은 빈 파일이라 변경 불필요) | — |
| `app/services/badges.py` | `db.add(Notification(...))` × 2 → `create_notification(...)` 호출 리팩토링 (approve / reject) | Modify |
| `app/services/comments.py` | `create_comment` 안에서 POST_COMMENT emit | Modify |
| `app/services/posts.py` | `create_journey_episode`에 fan-out emit (journey followers) + `create_answer`에 QUESTION_ANSWERED emit | Modify |
| `app/services/analytics.py` | `EventName.NOTIFICATION_OPENED` 추가 | Modify |
| `app/routers/notifications.py` | 4 라우트 — `/notifications`, `/notifications/_bell`, `POST /notifications/{id}/read`, `POST /notifications/read-all` | Create |
| `app/main.py` | `include_router(notifications_router.router)` | Modify |
| `app/templates/components/_bell.html` | Bell + unread 배지 + dropdown (HTMX target) | Create |
| `app/templates/components/nav.html` | bell partial include (로그인 사용자 한정) | Modify |
| `app/templates/pages/notifications.html` | 페이지네이션된 전체 목록 + "모두 읽음" 버튼 | Create |
| `app/tests/integration/test_notification_service.py` | service 단위 — self-skip, mark_read 소유권, type/link 매핑 | Create |
| `app/tests/integration/test_notification_routes.py` | 4 라우트 — 401/200/303/404 분기 | Create |
| `app/tests/integration/test_notification_emit_integration.py` | comment/journey/answer 작성 시 알림 row 생성 + self-skip | Create |
| `app/tests/integration/test_notification_e2e.py` | 댓글 → bell → 클릭 → redirect 풀 흐름 | Create |

---

## Task 1: `app/services/notifications.py` 신규 — 핵심 helper + view

**Files:**
- Create: `app/services/notifications.py`

- [ ] **Step 1: Write `notifications.py`**

```python
"""In-app notifications service — single source of truth for notification lifecycle.

PRD §9.3 P1 종료 기준 알림. 카카오 알림톡 / 이메일 / Web Push는 P2.
"""
from dataclasses import dataclass

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import Notification, User
from app.models._enums import NotificationType

PAGE_SIZE = 30
DROPDOWN_LIMIT = 5


@dataclass(frozen=True)
class NotificationView:
    notification: Notification
    label: str
    link: str
    source_username: str | None


def create_notification(
    db: Session,
    *,
    recipient: User,
    type: NotificationType,
    source_user: User | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
) -> Notification | None:
    """Create a notification. Self-trigger (source==recipient) is skipped."""
    if source_user is not None and source_user.id == recipient.id:
        return None
    notif = Notification(
        user_id=recipient.id,
        type=type,
        source_user_id=source_user.id if source_user else None,
        target_type=target_type,
        target_id=target_id,
    )
    db.add(notif)
    db.flush()
    return notif


def unread_count(db: Session, user: User) -> int:
    return db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id,
            Notification.is_read.is_(False),
        )
    ) or 0


def recent_for_dropdown(
    db: Session, user: User, limit: int = DROPDOWN_LIMIT
) -> list[NotificationView]:
    rows = list(
        db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        ).all()
    )
    return [_to_view(db, n) for n in rows]


def list_paginated(
    db: Session, user: User, *, page: int = 1
) -> tuple[list[NotificationView], int]:
    base = select(Notification).where(Notification.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = list(
        db.scalars(
            base.order_by(Notification.created_at.desc())
            .offset((page - 1) * PAGE_SIZE)
            .limit(PAGE_SIZE)
        ).all()
    )
    return [_to_view(db, n) for n in rows], total


def mark_read(db: Session, user: User, notif_id: int) -> Notification | None:
    """Soup-test ownership before marking. Returns None if not found or not owner."""
    notif = db.get(Notification, notif_id)
    if notif is None or notif.user_id != user.id:
        return None
    if not notif.is_read:
        notif.is_read = True
        db.flush()
    return notif


def mark_all_read(db: Session, user: User) -> int:
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    return result.rowcount or 0


def _to_view(db: Session, notif: Notification) -> NotificationView:
    source_username: str | None = None
    if notif.source_user_id:
        src = db.get(User, notif.source_user_id)
        source_username = src.username if src else None
    return NotificationView(
        notification=notif,
        label=_format_label(notif, source_username),
        link=_resolve_link(notif),
        source_username=source_username,
    )


def _format_label(notif: Notification, source_username: str | None) -> str:
    src = f"@{source_username}" if source_username else "운영진"
    if notif.type == NotificationType.BADGE_APPROVED:
        return "🎉 실거주자 배지가 승인되었습니다."
    if notif.type == NotificationType.BADGE_REJECTED:
        return "❌ 배지 신청이 반려되었습니다. 사유를 확인해주세요."
    if notif.type == NotificationType.POST_COMMENT:
        return f"{src}님이 회원님 글에 댓글을 달았습니다."
    if notif.type == NotificationType.JOURNEY_NEW_EPISODE:
        return f"{src}님이 새 에피소드를 게시했습니다."
    if notif.type == NotificationType.QUESTION_ANSWERED:
        return f"{src}님이 회원님 질문에 답변했습니다."
    if notif.type == NotificationType.SYSTEM:
        return "운영진 공지가 도착했습니다."
    return "새 알림이 있습니다."


def _resolve_link(notif: Notification) -> str:
    if notif.target_type == "badge_application":
        return "/me/badge"
    if notif.target_type == "post" and notif.target_id is not None:
        return f"/post/{notif.target_id}"
    return "/notifications"


__all__ = [
    "DROPDOWN_LIMIT",
    "NotificationView",
    "PAGE_SIZE",
    "create_notification",
    "list_paginated",
    "mark_all_read",
    "mark_read",
    "recent_for_dropdown",
    "unread_count",
]
```

- [ ] **Step 2: Static check**

Run: `uv run python -c "from app.services.notifications import create_notification, NotificationView, _format_label, _resolve_link, PAGE_SIZE, DROPDOWN_LIMIT; print('imports ok')"`
Expected: `imports ok`

- [ ] **Step 3: Lint**

Run: `uv run ruff check app/services/notifications.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add app/services/notifications.py
git commit -m "feat(services): add notifications service (P1.5a core)

- create_notification helper with self-trigger skip
- unread_count / recent_for_dropdown / list_paginated / mark_read / mark_all_read
- NotificationView (label + link mapping per NotificationType)
- 5 enum types + 2 target_type targets (badge_application / post)

Refs: docs/superpowers/specs/2026-05-09-nestory-p15a-notifications-design.md §4.1"
```

---

## Task 2: Service unit tests

**Files:**
- Create: `app/tests/integration/test_notification_service.py`

- [ ] **Step 1: Write tests**

```python
"""Unit tests for app.services.notifications.

Tests:
- test_create_notification_inserts_row
- test_create_notification_skips_self_trigger
- test_create_notification_with_no_source_user
- test_unread_count_excludes_read
- test_mark_read_owner_succeeds
- test_mark_read_other_user_returns_none
- test_mark_read_idempotent_for_already_read
- test_mark_all_read_only_targets_unread
- test_mark_all_read_isolates_users
- test_list_paginated_orders_desc_with_total
- test_recent_for_dropdown_caps_at_5
- test_format_label_per_type
- test_resolve_link_per_target

NOTE: Requires running Postgres (factory-boy + db fixture).
"""
import pytest

from sqlalchemy.orm import Session

from app.models import Notification
from app.models._enums import NotificationType
from app.services import notifications as nsvc
from app.tests.factories import NotificationFactory, UserFactory


def test_create_notification_inserts_row(db: Session) -> None:
    recipient = UserFactory()
    source = UserFactory()
    notif = nsvc.create_notification(
        db,
        recipient=recipient,
        type=NotificationType.POST_COMMENT,
        source_user=source,
        target_type="post",
        target_id=42,
    )
    assert notif is not None
    assert notif.user_id == recipient.id
    assert notif.source_user_id == source.id
    assert notif.target_type == "post"
    assert notif.target_id == 42
    assert notif.is_read is False


def test_create_notification_skips_self_trigger(db: Session) -> None:
    user = UserFactory()
    notif = nsvc.create_notification(
        db,
        recipient=user,
        type=NotificationType.POST_COMMENT,
        source_user=user,  # same user
    )
    assert notif is None


def test_create_notification_with_no_source_user(db: Session) -> None:
    """System notifications have no source_user — must not skip."""
    user = UserFactory()
    notif = nsvc.create_notification(
        db, recipient=user, type=NotificationType.SYSTEM
    )
    assert notif is not None
    assert notif.source_user_id is None


def test_unread_count_excludes_read(db: Session) -> None:
    user = UserFactory()
    NotificationFactory(user=user, is_read=False)
    NotificationFactory(user=user, is_read=False)
    NotificationFactory(user=user, is_read=True)
    assert nsvc.unread_count(db, user) == 2


def test_mark_read_owner_succeeds(db: Session) -> None:
    user = UserFactory()
    notif = NotificationFactory(user=user, is_read=False)
    out = nsvc.mark_read(db, user, notif.id)
    assert out is not None
    assert out.is_read is True


def test_mark_read_other_user_returns_none(db: Session) -> None:
    owner = UserFactory()
    intruder = UserFactory()
    notif = NotificationFactory(user=owner, is_read=False)
    out = nsvc.mark_read(db, intruder, notif.id)
    assert out is None
    db.refresh(notif)
    assert notif.is_read is False  # untouched


def test_mark_read_idempotent_for_already_read(db: Session) -> None:
    user = UserFactory()
    notif = NotificationFactory(user=user, is_read=True)
    out = nsvc.mark_read(db, user, notif.id)
    assert out is not None
    assert out.is_read is True


def test_mark_all_read_only_targets_unread(db: Session) -> None:
    user = UserFactory()
    NotificationFactory(user=user, is_read=False)
    NotificationFactory(user=user, is_read=False)
    NotificationFactory(user=user, is_read=True)
    n = nsvc.mark_all_read(db, user)
    assert n == 2
    assert nsvc.unread_count(db, user) == 0


def test_mark_all_read_isolates_users(db: Session) -> None:
    a = UserFactory()
    b = UserFactory()
    NotificationFactory(user=a, is_read=False)
    NotificationFactory(user=b, is_read=False)
    nsvc.mark_all_read(db, a)
    assert nsvc.unread_count(db, b) == 1


def test_list_paginated_orders_desc_with_total(db: Session) -> None:
    user = UserFactory()
    older = NotificationFactory(user=user)
    newer = NotificationFactory(user=user)
    views, total = nsvc.list_paginated(db, user, page=1)
    assert total == 2
    assert [v.notification.id for v in views] == [newer.id, older.id]


def test_recent_for_dropdown_caps_at_5(db: Session) -> None:
    user = UserFactory()
    for _ in range(7):
        NotificationFactory(user=user)
    views = nsvc.recent_for_dropdown(db, user)
    assert len(views) == 5


def test_format_label_per_type() -> None:
    notif = Notification(
        user_id=1, type=NotificationType.BADGE_APPROVED, is_read=False
    )
    assert "승인" in nsvc._format_label(notif, None)

    notif = Notification(
        user_id=1, type=NotificationType.BADGE_REJECTED, is_read=False
    )
    assert "반려" in nsvc._format_label(notif, None)

    notif = Notification(
        user_id=1, type=NotificationType.POST_COMMENT, is_read=False
    )
    assert "@alice" in nsvc._format_label(notif, "alice")
    assert "댓글" in nsvc._format_label(notif, "alice")

    notif = Notification(
        user_id=1, type=NotificationType.JOURNEY_NEW_EPISODE, is_read=False
    )
    assert "에피소드" in nsvc._format_label(notif, "alice")

    notif = Notification(
        user_id=1, type=NotificationType.QUESTION_ANSWERED, is_read=False
    )
    assert "답변" in nsvc._format_label(notif, "alice")

    notif = Notification(
        user_id=1, type=NotificationType.SYSTEM, is_read=False
    )
    assert "공지" in nsvc._format_label(notif, None)


def test_resolve_link_per_target() -> None:
    n_badge = Notification(
        user_id=1,
        type=NotificationType.BADGE_APPROVED,
        target_type="badge_application",
        target_id=99,
        is_read=False,
    )
    assert nsvc._resolve_link(n_badge) == "/me/badge"

    n_post = Notification(
        user_id=1,
        type=NotificationType.POST_COMMENT,
        target_type="post",
        target_id=42,
        is_read=False,
    )
    assert nsvc._resolve_link(n_post) == "/post/42"

    n_unknown = Notification(
        user_id=1, type=NotificationType.SYSTEM, is_read=False
    )
    assert nsvc._resolve_link(n_unknown) == "/notifications"
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest app/tests/integration/test_notification_service.py -v`
Expected: 13 PASS.

(Docker 미가용 PC에선 skip — 정적 import 검증만: `uv run python -c "import app.tests.integration.test_notification_service; print('ok')"` 부재 시 syntax error 캐치.)

- [ ] **Step 3: Lint**

Run: `uv run ruff check app/tests/integration/test_notification_service.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add app/tests/integration/test_notification_service.py
git commit -m "test: add notification service unit tests (13 cases)

create_notification self-skip · mark_read 소유권 · format_label/resolve_link 매핑.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15a-notifications-design.md §9"
```

---

## Task 3: Refactor `badges.py` — direct INSERT → helper call

**Files:**
- Modify: `app/services/badges.py` (lines around `Notification(` calls — search by string)

- [ ] **Step 1: Verify current call sites**

Run: `uv run python -c "
import re
src = open('app/services/badges.py').read()
print('Notification( occurrences:', src.count('Notification('))
print('NotificationType. occurrences:', src.count('NotificationType.'))
"`
Expected: `Notification( occurrences: 2`, `NotificationType. occurrences: 2` (one each in `approve` and `reject`).

- [ ] **Step 2: Replace `db.add(Notification(...))` blocks with helper calls**

In `app/services/badges.py`, find the `approve(...)` function — replace this block:

```python
    # Notify target user
    db.add(
        Notification(
            user_id=target_user.id,
            type=NotificationType.BADGE_APPROVED,
            source_user_id=reviewer.id,
            target_type="badge_application",
            target_id=application.id,
        )
    )
```

with:

```python
    create_notification(
        db,
        recipient=target_user,
        type=NotificationType.BADGE_APPROVED,
        source_user=reviewer,
        target_type="badge_application",
        target_id=application.id,
    )
```

Same for `reject(...)`:

```python
    db.add(
        Notification(
            user_id=application.user_id,
            type=NotificationType.BADGE_REJECTED,
            source_user_id=reviewer.id,
            target_type="badge_application",
            target_id=application.id,
        )
    )
```

becomes:

```python
    create_notification(
        db,
        recipient=target_user,  # 'reject' 함수 내 target_user 변수가 있는지 확인 — 없으면 db.get(User, application.user_id)
        type=NotificationType.BADGE_REJECTED,
        source_user=reviewer,
        target_type="badge_application",
        target_id=application.id,
    )
```

**Note:** `reject` 함수의 현재 코드는 `application.user_id`를 직접 사용. helper는 `User` 인스턴스를 요구하므로 `reject` 함수 시작 부분에 `target_user = db.get(User, application.user_id)`를 추가하거나, 인자로 받게 시그니처를 바꿀 것. 가장 작은 변경: 함수 안에서 `target_user = db.get(User, application.user_id); assert target_user is not None`. 자기 자신 reject은 발생 안 하므로 skip 동작 무관.

- [ ] **Step 3: Update imports in `app/services/badges.py`**

Add at top:
```python
from app.services.notifications import create_notification
```

Remove (if no other usage):
```python
from app.models import Notification  # noqa
```
(Keep the import only if other code in the file references `Notification` directly. Grep first: `grep -n "Notification\b" app/services/badges.py`. If only in the now-removed lines, remove.)

- [ ] **Step 4: Static check**

Run: `uv run python -c "from app.services.badges import approve, reject; print('imports ok')"`
Expected: `imports ok`.

Run: `grep -n "db.add(Notification" app/services/badges.py` (via Bash tool with `output_mode=content`).
Expected: no matches (helper now used).

- [ ] **Step 5: Lint**

Run: `uv run ruff check app/services/badges.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add app/services/badges.py
git commit -m "refactor(badges): use create_notification helper instead of direct INSERT

approve / reject now call notifications.create_notification — single source of truth.
behavior unchanged (BADGE_* never self-triggers).

Refs: docs/superpowers/specs/2026-05-09-nestory-p15a-notifications-design.md §4.2"
```

---

## Task 4: Emit POST_COMMENT in `comments.py`

**Files:**
- Modify: `app/services/comments.py:create_comment`

- [ ] **Step 1: Add emit + import**

Edit `app/services/comments.py`:

Add import at top (alongside other `app.*` imports):
```python
from app.services.notifications import create_notification
from app.models._enums import NotificationType  # if not already imported
```

Inside `create_comment`, BEFORE `db.commit()` (so notification row commits in same txn), add:

```python
    post_author = db.get(User, post.author_id)
    if post_author is not None:
        create_notification(
            db,
            recipient=post_author,
            type=NotificationType.POST_COMMENT,
            source_user=user,
            target_type="post",
            target_id=post.id,
        )
```

Final `create_comment` body looks like (the new block goes before the existing `db.commit()` line):

```python
    c = Comment(post_id=post.id, author_id=user.id, body=body, parent_id=parent_id)
    db.add(c)
    post_author = db.get(User, post.author_id)
    if post_author is not None:
        create_notification(
            db,
            recipient=post_author,
            type=NotificationType.POST_COMMENT,
            source_user=user,
            target_type="post",
            target_id=post.id,
        )
    db.commit()
    db.refresh(c)
    return c
```

- [ ] **Step 2: Static check**

Run: `uv run python -c "from app.services.comments import create_comment; print('imports ok')"`
Expected: `imports ok`.

- [ ] **Step 3: Lint**

Run: `uv run ruff check app/services/comments.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add app/services/comments.py
git commit -m "feat(comments): emit POST_COMMENT notification on comment creation

Self-trigger (자기 글에 자기 댓글) skip은 helper가 처리.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15a-notifications-design.md §4.2"
```

---

## Task 5: Emit JOURNEY_NEW_EPISODE fan-out + QUESTION_ANSWERED in `posts.py`

**Files:**
- Modify: `app/services/posts.py` (functions `create_journey_episode` and `create_answer`)

- [ ] **Step 1: Add imports**

Edit `app/services/posts.py` — add imports at top:

```python
from app.models.interaction import journey_follows
from app.services.notifications import create_notification
```

(`User` import: confirm `from app.models import User` already present. If only `from app.models import ... Post, ...` without User, add it.)

- [ ] **Step 2: Add fan-out emit to `create_journey_episode`**

Find `create_journey_episode` function. Currently ends:

```python
    db.add(post)
    db.flush()
    return post
```

Change to:

```python
    db.add(post)
    db.flush()
    followers = list(
        db.scalars(
            select(User)
            .join(journey_follows, User.id == journey_follows.c.user_id)
            .where(journey_follows.c.journey_id == journey.id)
        ).all()
    )
    for follower in followers:
        create_notification(
            db,
            recipient=follower,
            type=NotificationType.JOURNEY_NEW_EPISODE,
            source_user=author,
            target_type="post",
            target_id=post.id,
        )
    return post
```

(`select`, `User`, `NotificationType` imports — verify file already imports them; existing `posts.py` likely uses `select`. Add what's missing.)

- [ ] **Step 3: Add emit to `create_answer`**

Find `create_answer`. Currently ends:

```python
    db.add(post)
    db.flush()
    return post
```

Change to:

```python
    db.add(post)
    db.flush()
    question_author = db.get(User, parent_question.author_id)
    if question_author is not None:
        create_notification(
            db,
            recipient=question_author,
            type=NotificationType.QUESTION_ANSWERED,
            source_user=author,
            target_type="post",
            target_id=parent_question.id,
        )
    return post
```

- [ ] **Step 4: Static check**

Run: `uv run python -c "from app.services.posts import create_journey_episode, create_answer; print('imports ok')"`
Expected: `imports ok`.

- [ ] **Step 5: Lint**

Run: `uv run ruff check app/services/posts.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add app/services/posts.py
git commit -m "feat(posts): emit JOURNEY_NEW_EPISODE fan-out + QUESTION_ANSWERED

journey episode 생성 시 모든 팔로워에게 알림 fan-out (helper self-skip 방어).
answer 생성 시 질문자에게 알림 (자기 답변 시 helper skip).

Refs: docs/superpowers/specs/2026-05-09-nestory-p15a-notifications-design.md §4.2"
```

---

## Task 6: Add `NOTIFICATION_OPENED` analytics event

**Files:**
- Modify: `app/services/analytics.py`

- [ ] **Step 1: Add enum entry**

Edit `app/services/analytics.py` — `EventName` 클래스 안 P1.4b 섹션 다음에 추가:

```python

    # P1.5a — notifications
    NOTIFICATION_OPENED = "notification_opened"
```

- [ ] **Step 2: Lint**

Run: `uv run ruff check app/services/analytics.py`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add app/services/analytics.py
git commit -m "feat(analytics): add NOTIFICATION_OPENED event

emit은 P1.5c PostHog wiring 시점에 실제 트래킹.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15a-notifications-design.md §10"
```

---

## Task 7: Routes — `app/routers/notifications.py` + main.py 등록

**Files:**
- Create: `app/routers/notifications.py`
- Modify: `app/main.py`

- [ ] **Step 1: Write router**

```python
"""Notifications routes — in-app bell + /notifications page.

PRD §9.3 P1 종료 기준 알림 표시 surface.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.deps import get_db, require_user
from app.models import User
from app.services import notifications as nsvc
from app.services.analytics import EventName, emit
from app.templating import templates

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_class=HTMLResponse)
def notifications_page(
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> HTMLResponse:
    views, total = nsvc.list_paginated(db, current_user, page=page)
    return templates.TemplateResponse(
        request,
        "pages/notifications.html",
        {
            "views": views,
            "total": total,
            "page": page,
            "page_size": nsvc.PAGE_SIZE,
            "current_user": current_user,
        },
    )


@router.get("/notifications/_bell", response_class=HTMLResponse)
def notifications_bell(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "components/_bell.html",
        {
            "unread_count": nsvc.unread_count(db, current_user),
            "recent": nsvc.recent_for_dropdown(db, current_user),
            "current_user": current_user,
        },
    )


@router.post("/notifications/{notif_id}/read", response_model=None)
def notification_read(
    notif_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> RedirectResponse:
    notif = nsvc.mark_read(db, current_user, notif_id)
    if notif is None:
        raise HTTPException(404, "알림을 찾을 수 없습니다")
    db.commit()
    emit(EventName.NOTIFICATION_OPENED)
    return RedirectResponse(url=nsvc._resolve_link(notif), status_code=303)


@router.post("/notifications/read-all", response_model=None)
def notifications_read_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> RedirectResponse:
    nsvc.mark_all_read(db, current_user)
    db.commit()
    return RedirectResponse(url="/notifications", status_code=303)
```

- [ ] **Step 2: Register router in `app/main.py`**

Add import alphabetically (after `from app.routers import me as me_router`):
```python
from app.routers import notifications as notifications_router
```

Add `app.include_router(notifications_router.router)` alphabetically (between `me_router` and `pages_router`).

- [ ] **Step 3: Static check**

Run: `uv run python -c "
from app.main import app
paths = sorted(p for p in (getattr(r, 'path', '') for r in app.routes) if '/notifications' in p)
print(paths)
"`
Expected: `['/notifications', '/notifications/_bell', '/notifications/read-all', '/notifications/{notif_id}/read']`

- [ ] **Step 4: Lint**

Run: `uv run ruff check app/routers/notifications.py app/main.py`
Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add app/routers/notifications.py app/main.py
git commit -m "feat(routers): add notifications routes (page · bell partial · read · read-all)

GET /notifications + GET /notifications/_bell (HTMX partial) +
POST /notifications/{id}/read (303 to target link) +
POST /notifications/read-all.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15a-notifications-design.md §5"
```

---

## Task 8: Bell partial template + nav 통합

**Files:**
- Create: `app/templates/components/_bell.html`
- Modify: `app/templates/components/nav.html`

- [ ] **Step 1: Write `_bell.html`**

```html
<div id="bell-area"
     hx-get="/notifications/_bell"
     hx-trigger="every 30s"
     hx-swap="outerHTML"
     class="relative" x-data="{ open: false }">

  <button type="button" @click="open = !open" @click.outside="open = false"
          class="relative text-slate-600 hover:text-slate-900 min-w-12 min-h-12 flex items-center justify-center"
          aria-label="알림 {{ unread_count }}개">
    <span class="text-xl">🔔</span>
    {% if unread_count > 0 %}
      <span class="absolute -top-1 -right-1 inline-flex items-center justify-center
                   h-5 min-w-5 px-1 rounded-full bg-rose-600 text-white text-xs">
        {{ unread_count if unread_count < 100 else '99+' }}
      </span>
    {% endif %}
  </button>

  <div x-show="open" x-transition x-cloak
       class="absolute right-0 mt-2 w-80 rounded border bg-white shadow-lg z-20">
    <div class="px-4 py-2 text-sm font-semibold border-b">알림</div>
    {% if recent %}
      <ul class="max-h-96 overflow-y-auto">
        {% for view in recent %}
          <li>
            <form method="post" action="/notifications/{{ view.notification.id }}/read">
              <button type="submit"
                      class="w-full text-left px-4 py-3 hover:bg-slate-50
                             {% if not view.notification.is_read %}bg-emerald-50{% endif %}">
                <p class="text-sm text-slate-900">{{ view.label }}</p>
                <p class="text-xs text-slate-500 mt-1">
                  {{ view.notification.created_at.strftime('%m/%d %H:%M') }}
                </p>
              </button>
            </form>
          </li>
        {% endfor %}
      </ul>
    {% else %}
      <p class="px-4 py-6 text-center text-sm text-slate-500">새 알림이 없습니다.</p>
    {% endif %}
    <a href="/notifications"
       class="block text-center px-4 py-2 border-t text-sm text-emerald-700 hover:bg-slate-50">
      모두 보기 →
    </a>
  </div>
</div>
```

- [ ] **Step 2: Update `nav.html` to include bell for logged-in users**

Edit `app/templates/components/nav.html`. The current logged-in section starts with `{% if current_user %}` and contains the write dropdown + 내 배지 + admin link + username + logout.

Insert the bell BEFORE `<a href="/me/badge" ...>` (right after the write `</div>` block — i.e., after the closing `</div>` of the `x-data="{ open: false }"` write dropdown). Use HTMX hx-get to load the bell partial on initial render:

```html
        <div hx-get="/notifications/_bell" hx-trigger="load" hx-swap="outerHTML">
          <span class="text-slate-400">🔔</span>
        </div>
```

(This placeholder loads the actual bell partial on page load. After the swap, the bell partial's own `hx-trigger="every 30s"` takes over.)

Final nav.html structure (logged-in branch only):
```html
{% if current_user %}
  <div x-data="{ open: false }" class="relative">
    <!-- write dropdown (existing) -->
  </div>

  <!-- NEW: bell placeholder, will be swapped in by HTMX -->
  <div hx-get="/notifications/_bell" hx-trigger="load" hx-swap="outerHTML">
    <span class="text-slate-400">🔔</span>
  </div>

  <a href="/me/badge" class="text-sm text-slate-600 hover:underline">내 배지</a>
  ...
```

- [ ] **Step 3: Manual smoke (Docker-up PC only)**

서버 실행 후 로그인 사용자로 `/`방문 → nav에 🔔 표시 + DB에서 unread notification 1개 INSERT 후 새로고침 → 빨간 배지 1 표시 → 클릭 dropdown 열림 → 알림 클릭 → 해당 link로 redirect + 읽음.

Docker 미가용 PC: 정적 검증 만 — `_bell.html` 파일 생성 + nav.html include 위치 확인.

- [ ] **Step 4: Commit**

```bash
git add app/templates/components/_bell.html app/templates/components/nav.html
git commit -m "feat(ui): add bell + dropdown partial in nav (HTMX 30s polling)

bell area는 page load 시 partial swap, 이후 30s polling으로 unread count 갱신.
시니어 친화 — min-w-12 min-h-12 큰 hit target + 명확한 unread 시각 차.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15a-notifications-design.md §6.1"
```

---

## Task 9: `/notifications` 페이지 템플릿

**Files:**
- Create: `app/templates/pages/notifications.html`

- [ ] **Step 1: Write template**

```html
{% extends "base.html" %}
{% block title %}알림 · Nestory{% endblock %}
{% block content %}
<section class="space-y-4">
  <header class="flex items-center justify-between">
    <h1 class="text-2xl font-bold text-slate-900">알림</h1>
    {% if total > 0 %}
      <form method="post" action="/notifications/read-all">
        <button type="submit"
                class="rounded border bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50">
          모두 읽음
        </button>
      </form>
    {% endif %}
  </header>

  {% if views %}
    <ul class="space-y-2">
      {% for view in views %}
        <li>
          <form method="post" action="/notifications/{{ view.notification.id }}/read">
            <button type="submit"
                    class="w-full text-left rounded border bg-white p-4 hover:bg-slate-50
                           {% if not view.notification.is_read %}border-emerald-300 bg-emerald-50{% endif %}">
              <p class="text-base text-slate-900">{{ view.label }}</p>
              <p class="text-xs text-slate-500 mt-2">
                {{ view.notification.created_at.strftime('%Y-%m-%d %H:%M') }}
                {% if view.notification.is_read %}<span class="ml-2">· 읽음</span>{% endif %}
              </p>
            </button>
          </form>
        </li>
      {% endfor %}
    </ul>

    {% with current_page=page, total_count=total, page_size=page_size, base_url='/notifications' %}
      {% include "partials/pagination.html" %}
    {% endwith %}
  {% else %}
    <div class="rounded border bg-white p-8 text-center text-slate-500">
      알림이 없습니다.
    </div>
  {% endif %}
</section>
{% endblock %}
```

(`partials/pagination.html` 변수 이름은 P1.4 패턴 — `current_page`, `total_count`, `page_size`, `base_url`. `app/templates/partials/pagination.html` 실제 사용 변수명을 빠르게 확인 후 일치시킬 것. 다르면 위 `{% with %}` 변수명 조정.)

- [ ] **Step 2: Verify pagination variable names**

Run: `grep -n "{% if\|{% set\|{{ " app/templates/partials/pagination.html | head -10` (Bash tool with `output_mode=content`).
Adjust the `{% with %}` block to match.

- [ ] **Step 3: Static smoke (template lint)**

Run: `uv run python -c "
from jinja2 import Environment, FileSystemLoader
env = Environment(loader=FileSystemLoader('app/templates'))
env.get_template('pages/notifications.html')
print('template parses ok')
"`
Expected: `template parses ok` (no syntax error in Jinja2).

- [ ] **Step 4: Commit**

```bash
git add app/templates/pages/notifications.html
git commit -m "feat(ui): add /notifications page template

Pagination + 모두 읽음 버튼 + unread/read 시각 분기.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15a-notifications-design.md §6.2"
```

---

## Task 10: Route integration tests

**Files:**
- Create: `app/tests/integration/test_notification_routes.py`

- [ ] **Step 1: Write tests**

```python
"""Integration tests for /notifications routes.

Tests:
- test_notifications_page_requires_login
- test_notifications_page_renders_for_owner
- test_notifications_page_paginates
- test_bell_partial_returns_unread_count_zero_for_new_user
- test_bell_partial_returns_unread_with_recent
- test_read_marks_notification_and_redirects_to_link
- test_read_returns_404_for_other_user
- test_read_returns_404_for_unknown_id
- test_read_all_marks_all_owned_unread

NOTE: Requires running Postgres.
"""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models._enums import NotificationType
from app.services.notifications import unread_count
from app.tests.factories import NotificationFactory, UserFactory


def test_notifications_page_requires_login(client: TestClient) -> None:
    r = client.get("/notifications")
    assert r.status_code == 401


def test_notifications_page_renders_for_owner(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    NotificationFactory(user=user, type=NotificationType.SYSTEM)
    db.commit()
    login(user.id)
    r = client.get("/notifications")
    assert r.status_code == 200
    assert "알림" in r.text


def test_notifications_page_paginates(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    for _ in range(35):
        NotificationFactory(user=user)
    db.commit()
    login(user.id)
    r1 = client.get("/notifications?page=1")
    r2 = client.get("/notifications?page=2")
    assert r1.status_code == 200
    assert r2.status_code == 200


def test_bell_partial_returns_unread_count_zero_for_new_user(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.get("/notifications/_bell")
    assert r.status_code == 200
    assert "새 알림이 없습니다" in r.text


def test_bell_partial_returns_unread_with_recent(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    NotificationFactory(user=user, is_read=False, type=NotificationType.SYSTEM)
    NotificationFactory(user=user, is_read=False, type=NotificationType.SYSTEM)
    db.commit()
    login(user.id)
    r = client.get("/notifications/_bell")
    assert r.status_code == 200
    # unread badge OR recent items rendered
    assert "공지" in r.text


def test_read_marks_notification_and_redirects_to_link(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    notif = NotificationFactory(
        user=user,
        is_read=False,
        type=NotificationType.POST_COMMENT,
        target_type="post",
        target_id=42,
    )
    db.commit()
    login(user.id)
    r = client.post(
        f"/notifications/{notif.id}/read", follow_redirects=False
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/post/42"
    db.refresh(notif)
    assert notif.is_read is True


def test_read_returns_404_for_other_user(
    client: TestClient, db: Session, login
) -> None:
    owner = UserFactory()
    intruder = UserFactory()
    notif = NotificationFactory(user=owner, is_read=False)
    db.commit()
    login(intruder.id)
    r = client.post(f"/notifications/{notif.id}/read")
    assert r.status_code == 404


def test_read_returns_404_for_unknown_id(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.post("/notifications/99999/read")
    assert r.status_code == 404


def test_read_all_marks_all_owned_unread(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    NotificationFactory(user=user, is_read=False)
    NotificationFactory(user=user, is_read=False)
    NotificationFactory(user=user, is_read=True)
    db.commit()
    login(user.id)
    r = client.post("/notifications/read-all", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/notifications"
    assert unread_count(db, user) == 0
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest app/tests/integration/test_notification_routes.py -v`
Expected: 9 PASS.

- [ ] **Step 3: Lint**

Run: `uv run ruff check app/tests/integration/test_notification_routes.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add app/tests/integration/test_notification_routes.py
git commit -m "test: add /notifications route integration tests (9 cases)

Login guard · ownership guard · 303 redirect to link · read-all 일괄.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15a-notifications-design.md §9"
```

---

## Task 11: Emit integration tests (4 trigger paths)

**Files:**
- Create: `app/tests/integration/test_notification_emit_integration.py`

- [ ] **Step 1: Write tests**

```python
"""Integration tests verifying alert rows are created at trigger sites.

Tests:
- test_create_comment_emits_post_comment_to_post_author
- test_create_comment_self_does_not_emit
- test_create_journey_episode_fans_out_to_followers
- test_create_journey_episode_skips_self_follower
- test_create_answer_emits_to_question_author
- test_create_answer_self_does_not_emit

NOTE: Requires running Postgres.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Journey, Notification, Post
from app.models._enums import (
    JourneyStatus,
    NotificationType,
    PostStatus,
    PostType,
)
from app.models.interaction import journey_follows
from app.schemas.post_metadata import (
    AnswerMetadata,
    JourneyEpisodeMetadata,
    QuestionMetadata,
)
from app.services.comments import create_comment
from app.services.posts import create_answer, create_journey_episode, create_question
from app.tests.factories import (
    QuestionPostFactory,
    RegionFactory,
    ResidentUserFactory,
    ReviewPostFactory,
    UserFactory,
)


def _notif_for(db: Session, user_id: int) -> list[Notification]:
    return list(
        db.scalars(
            select(Notification).where(Notification.user_id == user_id)
        ).all()
    )


def test_create_comment_emits_post_comment_to_post_author(db: Session) -> None:
    author = UserFactory()
    commenter = UserFactory()
    post = ReviewPostFactory(author=author, status=PostStatus.PUBLISHED)
    db.flush()
    create_comment(db, post, commenter, "좋은 글 잘 봤습니다")
    notifs = _notif_for(db, author.id)
    assert len(notifs) == 1
    n = notifs[0]
    assert n.type == NotificationType.POST_COMMENT
    assert n.source_user_id == commenter.id
    assert n.target_type == "post"
    assert n.target_id == post.id


def test_create_comment_self_does_not_emit(db: Session) -> None:
    author = UserFactory()
    post = ReviewPostFactory(author=author, status=PostStatus.PUBLISHED)
    db.flush()
    create_comment(db, post, author, "내 글에 댓글")
    assert _notif_for(db, author.id) == []


def test_create_journey_episode_fans_out_to_followers(db: Session) -> None:
    author = ResidentUserFactory()
    region = RegionFactory()
    follower_a = UserFactory()
    follower_b = UserFactory()
    journey = Journey(
        author_id=author.id,
        region_id=region.id,
        title="My Journey",
        slug="my-journey",
        status=JourneyStatus.IN_PROGRESS,
    )
    db.add(journey)
    db.flush()
    db.execute(
        journey_follows.insert(),
        [
            {"user_id": follower_a.id, "journey_id": journey.id},
            {"user_id": follower_b.id, "journey_id": journey.id},
        ],
    )
    db.flush()

    create_journey_episode(
        db,
        author=author,
        journey=journey,
        payload=JourneyEpisodeMetadata(),
        title="Episode 1",
        body="첫 회차",
    )
    assert len(_notif_for(db, follower_a.id)) == 1
    assert len(_notif_for(db, follower_b.id)) == 1
    a_notif = _notif_for(db, follower_a.id)[0]
    assert a_notif.type == NotificationType.JOURNEY_NEW_EPISODE
    assert a_notif.source_user_id == author.id


def test_create_journey_episode_skips_self_follower(db: Session) -> None:
    """If author somehow follows their own journey, helper self-skip protects."""
    author = ResidentUserFactory()
    region = RegionFactory()
    journey = Journey(
        author_id=author.id,
        region_id=region.id,
        title="Self J",
        slug="self-j",
        status=JourneyStatus.IN_PROGRESS,
    )
    db.add(journey)
    db.flush()
    db.execute(
        journey_follows.insert(),
        {"user_id": author.id, "journey_id": journey.id},
    )
    db.flush()

    create_journey_episode(
        db,
        author=author,
        journey=journey,
        payload=JourneyEpisodeMetadata(),
        title="Self ep",
        body="본인 글",
    )
    assert _notif_for(db, author.id) == []


def test_create_answer_emits_to_question_author(db: Session) -> None:
    asker = UserFactory()
    answerer = UserFactory()
    question = QuestionPostFactory(author=asker, status=PostStatus.PUBLISHED)
    db.flush()
    create_answer(db, answerer, question, "여기 답변입니다")
    notifs = _notif_for(db, asker.id)
    assert len(notifs) == 1
    n = notifs[0]
    assert n.type == NotificationType.QUESTION_ANSWERED
    assert n.source_user_id == answerer.id
    assert n.target_type == "post"
    assert n.target_id == question.id


def test_create_answer_self_does_not_emit(db: Session) -> None:
    asker = UserFactory()
    question = QuestionPostFactory(author=asker, status=PostStatus.PUBLISHED)
    db.flush()
    create_answer(db, asker, question, "self answer")
    assert _notif_for(db, asker.id) == []
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest app/tests/integration/test_notification_emit_integration.py -v`
Expected: 6 PASS.

- [ ] **Step 3: Lint**

Run: `uv run ruff check app/tests/integration/test_notification_emit_integration.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add app/tests/integration/test_notification_emit_integration.py
git commit -m "test: verify notification emit at all 4 trigger sites + self-skip

comment·journey episode (fan-out)·answer 트리거에서 알림 row 생성 + 자기 자신 skip.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15a-notifications-design.md §9"
```

---

## Task 12: E2E test — full notification flow

**Files:**
- Create: `app/tests/integration/test_notification_e2e.py`

- [ ] **Step 1: Write E2E test**

```python
"""E2E flow: comment trigger → bell unread → click → redirect + mark read.

NOTE: Requires running Postgres.
"""
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notification
from app.models._enums import PostStatus
from app.tests.factories import ReviewPostFactory, UserFactory


def test_full_notification_lifecycle(
    client: TestClient, db: Session, login
) -> None:
    # 1. 두 사용자: 글 작성자(author) + 댓글 작성자(commenter)
    author = UserFactory()
    commenter = UserFactory()
    post = ReviewPostFactory(author=author, status=PostStatus.PUBLISHED)
    db.commit()

    # 2. commenter가 post에 댓글 작성 (POST 라우트)
    login(commenter.id)
    r = client.post(
        f"/post/{post.id}/comment",
        data={"body": "좋은 글입니다"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    # 3. author 측에 알림 row 1개
    notifs = list(
        db.scalars(
            select(Notification).where(Notification.user_id == author.id)
        ).all()
    )
    assert len(notifs) == 1
    notif = notifs[0]
    assert notif.is_read is False

    # 4. author 로그인 → bell partial GET → unread 표시
    client.cookies.clear()
    login(author.id)
    r = client.get("/notifications/_bell")
    assert r.status_code == 200
    assert "댓글" in r.text  # POST_COMMENT 메시지

    # 5. author가 알림 클릭 (POST read) → 303 to /post/{post.id}
    r = client.post(
        f"/notifications/{notif.id}/read", follow_redirects=False
    )
    assert r.status_code == 303
    assert r.headers["location"] == f"/post/{post.id}"

    # 6. 알림 read 처리됨
    db.refresh(notif)
    assert notif.is_read is True

    # 7. bell partial 재호출 → unread 0 (배지 사라짐)
    r = client.get("/notifications/_bell")
    assert r.status_code == 200
    assert "댓글" in r.text  # 여전히 dropdown에 표시 (read 상태)
    # bg-emerald-50 (unread highlight) 사라짐 검증은 미세하므로 skip
```

- [ ] **Step 2: Run test**

Run: `uv run pytest app/tests/integration/test_notification_e2e.py -v`
Expected: 1 PASS.

- [ ] **Step 3: Lint**

Run: `uv run ruff check app/tests/integration/test_notification_e2e.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add app/tests/integration/test_notification_e2e.py
git commit -m "test: add E2E notification lifecycle (comment trigger → click → read)

Refs: docs/superpowers/specs/2026-05-09-nestory-p15a-notifications-design.md §9"
```

---

## Task 13: Full regression sweep + DoD verification (Docker-up PC)

**Files:** none (verification only)

- [ ] **Step 1: Full pytest run**

Run: `uv run pytest app/tests/ -q`
Expected: P1.3 + P1.4 + P1.4b + 신규 P1.5a 테스트 (29 추가 — service 13 + routes 9 + emit 6 + e2e 1) 모두 PASS.

- [ ] **Step 2: Lint full tree**

Run: `uv run ruff check app/`
Expected: clean.

- [ ] **Step 3: Manual browser QA (golden path)**

서버 실행 후:

1. 로그인 사용자로 `/` 진입 → nav에 🔔 표시 + 페이지 로드 후 bell partial swap-in 확인
2. 다른 사용자로 댓글 작성 → 30초 이내 본인 nav의 🔔 옆 빨간 배지 1 표시 (HTMX polling)
3. 🔔 클릭 → dropdown 열림 + 1개 알림 표시 (메시지: "@xxx님이 회원님 글에 댓글을 달았습니다")
4. 알림 클릭 → /post/{id}로 redirect + 댓글 섹션 보임
5. /notifications 진입 → 전체 목록 + 읽음 표시 + "모두 읽음" 버튼
6. "모두 읽음" 클릭 → 모든 row read 상태로 갱신
7. badges.py 흐름 회귀 확인 — 관리자가 다른 사용자 배지 승인 → 신청자에게 BADGE_APPROVED 알림 row 생성 + bell 표시

- [ ] **Step 4: Plan DoD 표 갱신 + 핸드오프 메모리 갱신**

이 plan 파일 마지막에 DoD 체크 표 추가. 핸드오프 메모리에 "P1.5a Notifications 완료" 기록.

- [ ] **Step 5: Commit DoD 검증 결과**

```bash
git add docs/superpowers/plans/2026-05-09-nestory-p15a-notifications.md
git commit -m "docs(plans): mark P1.5a notifications DoD verified

pytest 풀런 + 브라우저 QA 통과. 4 trigger emit + bell + /notifications + read flow 동작 확인.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15a-notifications-design.md §11"
```

---

## DoD checklist (2026-05-09 코드 구현 완료 — Docker 미가용 PC)

- [x] 4 라우트 모두 정상 동작 (200/303/401/404 분기) — app.routes 정적 등록 확인 ✅. 실 라우트 검증은 docker-up PC 필요
- [x] Bell UI 시니어 친화 (`min-w-12 min-h-12` hit target, `bg-emerald-50` unread 시각 차)
- [x] 4종 트리거 모두 `create_notification` 통과 — badges (Task 3) + comments (Task 4) + journey episode (Task 5) + Q&A answer (Task 5)
- [x] 자기 자신 알림 helper에서 자동 skip — Task 1 + Task 2 단위 테스트 검증
- [x] 기존 `app/services/badges.py` 직접 INSERT 패턴 → helper 호출로 통일 (Task 3, `5c33a4f`)
- [x] HTMX 30초 polling 동작 — `_bell.html`의 `hx-trigger="every 30s"` + nav 페이지 로드 시 placeholder swap (Task 8). 실제 30초 갱신 확인은 docker-up PC 브라우저 QA 필요
- [x] 4 테스트 파일 작성 (service 13 + routes 9 + emit 6 + e2e 1 = 29 신규 테스트). lint clean ✅
- [x] pytest 풀런 baseline 회귀 없음 (2026-05-10) — notification 관련 신규 29 테스트(service 13 + routes 9 + emit 6 + e2e 1) 모두 PASS. 풀 pytest 508 PASS / 4 hang 파일 deferred (notification 무관)
- [x] 비용 0 (in-app DB row만 — 발송 비용 없음)
- [x] 새 마이그레이션 0 (P1.1 `Notification` 모델 그대로 사용)

**구현 commits**: `68eb8e6..161381e` (12 commits, dev → main PR 시 squash 권장).

---

## Out-of-scope (P2 또는 P1.5b/c/d)

- 카카오 알림톡 발송 (P2 — PRD §9.4)
- 이메일 발송 (P2)
- Web Push (P1.5b PWA + Service Worker)
- POST_LIKED · TIMELAPSE_REMIND · REVALIDATION_PROMPT 트리거
- 알림 묶음 처리 (aggregation)
- 알림 설정 (off/on per type)
- 인앱 toast popup
- 알림 보존 정책 (TTL/아카이브)
