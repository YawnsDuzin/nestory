# Nestory — P1.5a 알림 (in-app + bell UI) 설계

**작성일**: 2026-05-09
**대상 단계**: P1.5a (P1.5 4 sub-plan 중 첫 번째)
**관련 PRD**: §9.3 Phase 1 — "알림 (bell UI · 인앱)" · §4.2 nav `🔔 알림 /notifications` · §6.4 [B5] · NotificationType enum 9종 (P1.1 정의됨)
**관련 메모리**: `project_nestory_handoff.md` — P1.5 진입 직전 상태
**관련 코드**: `app/models/notification.py` (P1.1) · `app/workers/handlers/notification.py` stub (P1.1) · `app/services/badges.py` (P1.2 — 이미 BADGE_* 알림 INSERT 중)

## 0. 핵심 결정 요약 (브레인스토밍 결과)

| 항목 | 결정 |
|---|---|
| 트리거 범위 | 5 enum 값 / 4 trigger context — BADGE_APPROVED·BADGE_REJECTED·POST_COMMENT·JOURNEY_NEW_EPISODE·QUESTION_ANSWERED. POST_LIKED·TIMELAPSE_REMIND·REVALIDATION_PROMPT는 P2. (BADGE_*는 P1.2에서 이미 생성 중 — 표시 UI만 추가) |
| Bell UI 패턴 | Nav에 🔔 + unread 배지 + dropdown preview (최근 5) + "모두 보기" → /notifications |
| 읽음 처리 | 클릭 = 자동 읽음 처리 + target deep link로 이동. /notifications 페이지에 "모두 읽음" 일괄 버튼. dropdown 열기 자체는 읽음 처리 안 함. |
| Polling | HTMX `hx-trigger="every 30s"` — bell 영역만 갱신 |
| 카카오 알림톡 | **P2 (PRD §9.4)** — P1.5a는 DB row 생성만. `JobKind.NOTIFICATION` 핸들러 stub 유지. |
| 자기 자신 알림 | helper에서 자동 skip (`source_user_id == recipient.id`) |

## 1. 배경 및 동기

PRD §9.3 Phase 1 종료 기준에 "알림 (bell UI · 인앱)" 명시. P1.1에서 `Notification` 모델 + `NotificationType` enum + `JobKind.NOTIFICATION` 핸들러 stub까지 완료. P1.2 배지 시스템은 이미 BADGE_APPROVED/REJECTED Notification row를 INSERT 중이지만 사용자가 볼 UI가 없는 상태 — **알림 row만 쌓이고 사용자 인지율 0%**.

P1.5a는 이 갭을 좁힌다:
1. **표시 레이어 완성** — bell UI + dropdown + /notifications 페이지로 row를 사용자에게 전달.
2. **트리거 통합** — `create_notification` 단일 helper로 모든 도메인 service가 호출. 자기 자신 알림 skip 등 정책을 한 곳에서 관리.
3. **신규 트리거 추가** — POST_COMMENT (댓글 도착), JOURNEY_NEW_EPISODE (팔로워에게 새 회차), QUESTION_ANSWERED (답변 도착).

P2 카카오 알림톡 도입 시점엔 `create_notification`이 `JobKind.NOTIFICATION` enqueue도 함께 수행하도록 확장 — 발송 채널만 추가하면 됨. P1.5a 설계가 이 확장을 차단하지 않도록 한다.

## 2. 범위

### 2.1 In-scope

- `app/services/notifications.py` 신규 — 단일 진실 원천. CRUD + helper.
- `app/routers/notifications.py` 신규 — 4 라우트.
- `app/templates/pages/notifications.html` 신규 — 페이지네이션된 전체 목록 + "모두 읽음" 버튼.
- `app/templates/components/_bell.html` 신규 — bell + unread 배지 + dropdown (HTMX swap target).
- `app/templates/components/nav.html` 수정 — 로그인 사용자에게 bell partial include.
- 기존 service 통합:
  - `app/services/badges.py` — 직접 `db.add(Notification(...))`을 `create_notification(...)` helper 호출로 리팩토링.
  - `app/services/comments.py` — POST_COMMENT emit (글 작성자에게).
  - Journey 에피소드 생성 service (P1.4 `app/services/journey.py` 확인 후 결정) — JOURNEY_NEW_EPISODE emit (모든 팔로워에게 fan-out).
  - Q&A 답변 생성 service (P1.4 `app/services/posts.py` 또는 별도) — QUESTION_ANSWERED emit (질문자에게).
- 새 analytics enum 1개 — `NOTIFICATION_OPENED` (사용자가 알림 클릭 시).
- 테스트 4 파일 — service / routes / emit integration / E2E.

### 2.2 Out of scope

- 카카오 알림톡 발송 — P2 (PRD §9.4). `JobKind.NOTIFICATION` 핸들러 stub 그대로.
- 이메일 발송 — P2.
- Web Push (PWA) — P1.5b 또는 P2.
- POST_LIKED 알림 — P2 (시니어 UX 노이즈 우려, 본질적 활동 신호 약함).
- TIMELAPSE_REMIND (24·26개월 회고 유도) — P2 일배치.
- REVALIDATION_PROMPT (resident 연 1회 재검증) — P2 일배치.
- 알림 묶음 처리 ("외 N명") — P2 (P1.5a는 row 1:1 표시).
- 알림 설정 (off/on per type) — P2.
- /notifications 정렬 옵션 — latest only.
- 인앱 toast popup — P2.
- 오프라인 큐잉 / Service Worker — P1.5b PWA에서.
- 알림 보존 정책 (오래된 row 아카이브 / TTL) — P2 운영 데이터 분석 후 결정.

## 3. 데이터 모델

**기존 `Notification` 모델 그대로 사용** (P1.1, `app/models/notification.py`):

```python
class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_unread_created",
              "user_id", "is_read", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[NotificationType] = mapped_column(...)  # 9종 enum
    source_user_id: Mapped[int | None] = ...  # nullable (system 알림 등)
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = ...
```

**새 마이그레이션 불필요** — 기존 인덱스 `ix_notifications_user_unread_created` 가 이미 dropdown unread 조회에 최적.

### 3.1 `target_type` 값 표준 (P1.5a)

| target_type | 의미 | URL 매핑 |
|---|---|---|
| `badge_application` | 배지 신청 | `/me/badge` |
| `post` | 게시글 (review/journey_episode/question/answer/plan 모두) | `/post/{target_id}` |

(P2에서 `journey`(시리즈), `comment`(특정 댓글) 등 추가 가능. P1.5a는 위 2개만.)

## 4. Service 레이어

### 4.1 `app/services/notifications.py` 신규

```python
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select, update, func
from sqlalchemy.orm import Session

from app.models import Notification, User
from app.models._enums import NotificationType


PAGE_SIZE = 30
DROPDOWN_LIMIT = 5


@dataclass(frozen=True)
class NotificationView:
    """Service 결과 객체 — 라우트/템플릿이 받는 표시용 뷰."""
    notification: Notification
    label: str           # "양평인님이 회원님 글에 댓글을 달았습니다"
    link: str            # "/post/42"
    source_username: str | None  # dropdown 표시용


def create_notification(
    db: Session,
    *,
    recipient: User,
    type: NotificationType,
    source_user: User | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
) -> Notification | None:
    """알림 row 생성. self-trigger 시 skip (None 반환).

    추후 P2에서 JobKind.NOTIFICATION enqueue도 이 함수에서 처리.
    """
    if source_user and source_user.id == recipient.id:
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
    """Bell dropdown — 최근 N개 (읽음 무관)."""
    rows = db.scalars(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    ).all()
    return [_to_view(db, n) for n in rows]


def list_paginated(
    db: Session, user: User, *, page: int = 1
) -> tuple[list[NotificationView], int]:
    """/notifications 전체 목록 + 총 개수."""
    base = select(Notification).where(Notification.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        base.order_by(Notification.created_at.desc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all()
    return [_to_view(db, n) for n in rows], total


def mark_read(db: Session, user: User, notif_id: int) -> Notification | None:
    """소유권 확인 후 읽음 처리. 다른 사용자의 alert 읽음 시도 → None."""
    notif = db.get(Notification, notif_id)
    if notif is None or notif.user_id != user.id:
        return None
    if not notif.is_read:
        notif.is_read = True
        db.flush()
    return notif


def mark_all_read(db: Session, user: User) -> int:
    """이 사용자의 모든 unread → read. 처리한 row 수 반환."""
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    return result.rowcount or 0


def _to_view(db: Session, notif: Notification) -> NotificationView:
    """Notification → NotificationView (label + link 매핑)."""
    source_username = None
    if notif.source_user_id:
        src = db.get(User, notif.source_user_id)
        source_username = src.username if src else None
    label = _format_label(notif, source_username)
    link = _resolve_link(notif)
    return NotificationView(
        notification=notif,
        label=label,
        link=link,
        source_username=source_username,
    )


def _format_label(notif: Notification, source_username: str | None) -> str:
    """Type별 한국어 메시지 — 시니어 존댓말."""
    src = f"@{source_username}" if source_username else "운영진"
    match notif.type:
        case NotificationType.BADGE_APPROVED:
            return "🎉 실거주자 배지가 승인되었습니다."
        case NotificationType.BADGE_REJECTED:
            return "❌ 배지 신청이 반려되었습니다. 사유를 확인해주세요."
        case NotificationType.POST_COMMENT:
            return f"{src}님이 회원님 글에 댓글을 달았습니다."
        case NotificationType.JOURNEY_NEW_EPISODE:
            return f"{src}님이 새 에피소드를 게시했습니다."
        case NotificationType.QUESTION_ANSWERED:
            return f"{src}님이 회원님 질문에 답변했습니다."
        case NotificationType.SYSTEM:
            return "운영진 공지가 도착했습니다."
        case _:
            return "새 알림이 있습니다."  # POST_LIKED·REVALIDATION·TIMELAPSE — P2


def _resolve_link(notif: Notification) -> str:
    """target_type/id → URL. 모르는 type이면 /notifications fallback."""
    if notif.target_type == "badge_application":
        return "/me/badge"
    if notif.target_type == "post" and notif.target_id is not None:
        return f"/post/{notif.target_id}"
    return "/notifications"
```

### 4.2 기존 service 통합

**`app/services/badges.py`** — `approve()` / `reject()` 함수 안의 `db.add(Notification(...))` 호출 2곳을 `create_notification(db, recipient=target_user, type=..., source_user=reviewer, target_type="badge_application", target_id=application.id)` 로 변경. 행동 변화 없음 (BADGE_* 는 self-trigger 불가능).

**`app/services/comments.py:create_comment`** — `db.commit()` 직전에 추가:

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
# self-trigger (자기 글에 자기 댓글) 시 helper가 None 반환 → 무시
```

**`app/services/posts.py:create_journey_episode`** — fan-out to journey followers (Table 객체 `journey_follows`는 `app/models/interaction.py` 정의):

```python
from app.models.interaction import journey_follows

# create_journey_episode 함수 내, db.flush() 다음:
followers = db.scalars(
    select(User).join(journey_follows, User.id == journey_follows.c.user_id)
    .where(journey_follows.c.journey_id == journey.id)
).all()
for f in followers:
    create_notification(
        db, recipient=f, type=NotificationType.JOURNEY_NEW_EPISODE,
        source_user=author, target_type="post", target_id=post.id,  # episode post
    )
```

(작성자가 자기 Journey를 팔로우 중이면 helper의 self-skip이 방어 — 표시 UX 일관성.)

**`app/services/posts.py:create_answer`** — `db.flush()` 직후 추가:

```python
question_author = db.get(User, parent_question.author_id)
if question_author is not None:
    create_notification(
        db, recipient=question_author, type=NotificationType.QUESTION_ANSWERED,
        source_user=author, target_type="post", target_id=parent_question.id,  # 질문 글로 이동
    )
```

## 5. Routes

| Method | Path | 역할 | Guard |
|---|---|---|---|
| GET | `/notifications` | 페이지네이션 전체 목록 + "모두 읽음" 버튼 | `require_user` |
| GET | `/notifications/_bell` | Bell + dropdown HTMX partial (30s polling) | `require_user` |
| POST | `/notifications/{id}/read` | 개별 읽음 + target link로 303 redirect | `require_user` |
| POST | `/notifications/read-all` | 일괄 읽음 + /notifications로 303 redirect | `require_user` |

```python
# app/routers/notifications.py
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.deps import get_db, require_user
from app.models import User
from app.services import notifications as notif_service
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
    views, total = notif_service.list_paginated(db, current_user, page=page)
    return templates.TemplateResponse(
        request,
        "pages/notifications.html",
        {"views": views, "total": total, "page": page,
         "page_size": notif_service.PAGE_SIZE, "current_user": current_user},
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
            "unread_count": notif_service.unread_count(db, current_user),
            "recent": notif_service.recent_for_dropdown(db, current_user),
            "current_user": current_user,
        },
    )


@router.post("/notifications/{notif_id}/read", response_model=None)
def notification_read(
    notif_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> RedirectResponse:
    notif = notif_service.mark_read(db, current_user, notif_id)
    if notif is None:
        raise HTTPException(404, "알림을 찾을 수 없습니다")
    db.commit()
    emit(EventName.NOTIFICATION_OPENED)
    link = notif_service._resolve_link(notif)  # service 헬퍼 재사용
    return RedirectResponse(url=link, status_code=303)


@router.post("/notifications/read-all", response_class=HTMLResponse)
def notifications_read_all(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> RedirectResponse:
    notif_service.mark_all_read(db, current_user)
    db.commit()
    return RedirectResponse(url="/notifications", status_code=303)
```

## 6. UI

### 6.1 Bell partial (`_bell.html`)

```html
<!-- nav 내부에 include — 로그인 사용자에게만 -->
<div id="bell-area"
     hx-get="/notifications/_bell"
     hx-trigger="every 30s"
     hx-swap="outerHTML"
     class="relative" x-data="{ open: false }">

  <button type="button" @click="open = !open" @click.outside="open = false"
          class="relative text-slate-600 hover:text-slate-900"
          aria-label="알림 {{ unread_count }}개">
    🔔
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

### 6.2 /notifications 페이지

- 헤더: "알림" + 우측 "모두 읽음" 버튼 (form POST `/notifications/read-all`)
- 본문: NotificationView row 30개. 읽음 row는 회색 톤, unread는 emerald 강조.
- 각 row는 `_bell.html`과 동일 form (POST read → redirect link).
- 하단: 기존 `partials/pagination.html` include.

## 7. 시니어 UX 디테일

- 큰 hit target — bell 버튼 `min-w-12 min-h-12`
- dropdown 행 `py-3` (세로 충분)
- 읽음 row와 unread row의 시각 차이 명확 (배경색 차)
- "모두 읽음" 버튼은 secondary 스타일 (실수 클릭 시 회복 어려움 인지 — 5px 더 작게)
- 시간 표시 `MM/DD HH:MM` 단순 포맷 (시니어 친숙)

## 8. 에러 처리

| 상황 | 처리 |
|---|---|
| 미로그인 → /notifications | 401 (`require_user`가 자동) |
| 다른 사용자 알림 read 시도 | 404 (소유권 미달 — `mark_read` None 반환) |
| 존재하지 않는 notif_id | 404 |
| HTMX bell partial 호출 시 unread=0 | 빈 dropdown + "새 알림 없음" 메시지 |
| Notification target post 삭제됨 (target_id 유효하지 않음) | redirect 후 /post/{id} 가 404 — 별도 처리 안 함 (정상 흐름) |

## 9. 테스트 전략

| Test file | Verifies |
|---|---|
| `test_notification_service.py` | `create_notification` self-skip · type 매핑 · `mark_read` 소유권 · `unread_count` · `_format_label` 5종 type · `_resolve_link` 5종 매핑 · `list_paginated` 페이지네이션 |
| `test_notification_routes.py` | 4 라우트 — login required · `/notifications/_bell` HTMX partial · read → 303 redirect link · read-all 일괄 |
| `test_notification_emit_integration.py` | comment 작성 시 글 작성자 알림 row · journey episode 시 모든 팔로워 fan-out · answer 시 질문자 알림 · 자기 자신 trigger 모두 skip |
| `test_notification_e2e.py` | 댓글 작성 → bell unread 1 → dropdown 표시 → 클릭 → 읽음 + redirect → bell unread 0 |

## 10. Analytics

`EventName.NOTIFICATION_OPENED` 1개 추가 — 사용자가 알림 클릭 (`mark_read` 라우트) 시 emit.

P1.5c PostHog 활성화 시 `NOTIFICATION_OPENED` props에 `notification_type` 포함 (PII 없음, type enum 값만).

## 11. DoD (Definition of Done)

- 4 라우트 모두 정상 동작 (200/303/401/404 분기)
- Bell UI 시니어 친화 (큰 hit target, 명확 unread 시각 차)
- 4종 트리거 모두 `create_notification` 통과 (badges + comments + journey episode + Q&A answer)
- 자기 자신 알림 helper에서 자동 skip
- 기존 `app/services/badges.py` 직접 INSERT 패턴 → helper 호출로 통일
- HTMX 30초 polling 동작 (수동 QA로 unread 도착 시 30초 내 갱신 확인)
- 4 테스트 파일 모두 PASS
- pytest baseline 회귀 없음
- 비용 0 (P1.5a는 in-app DB row만 — 발송 비용 없음)

## 12. 구현 task 추정

10-12 task. 대략 분해:

1. `app/services/notifications.py` — `create_notification` + helper 함수
2. `_format_label` + `_resolve_link` + service 단위 테스트
3. `app/services/badges.py` — `db.add(Notification(...))` → `create_notification(...)` 리팩토링 + 테스트 회귀 확인
4. `app/services/comments.py` — POST_COMMENT emit + 자기 자신 skip 검증
5. Journey episode 생성 경로 — JOURNEY_NEW_EPISODE fan-out emit
6. Q&A answer 생성 경로 — QUESTION_ANSWERED emit
7. `app/routers/notifications.py` — 4 라우트
8. `app/templates/components/_bell.html` + nav.html include
9. `app/templates/pages/notifications.html` + pagination
10. Analytics enum `NOTIFICATION_OPENED` 추가 + emit 연결
11. 4 test file (service · routes · emit integration · e2e)
12. 수동 QA + handoff 메모리 갱신

---

## Out-of-scope (별도 plan / P2+)

- 카카오 알림톡 발송 (PRD §9.4 — Phase 2)
- 이메일 발송
- Web Push (PWA) — P1.5b 또는 P2
- POST_LIKED · REVALIDATION_PROMPT · TIMELAPSE_REMIND 트리거
- 알림 묶음 처리
- 알림 설정 (off/on per type)
- 인앱 toast popup
- 알림 보존 정책 (TTL/아카이브)
