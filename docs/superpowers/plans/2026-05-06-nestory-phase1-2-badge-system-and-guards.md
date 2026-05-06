# Nestory Phase 1.2 — Badge System + Permission Guards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 1.1 의 모델 + 워커 인프라 위에 **사용자가 직접 사용하는 첫 워크플로우**를 구축한다 — 회원이 `region_verified` (지역 인증) 또는 `resident` (실거주자) 배지를 신청하고, 관리자가 증빙 파일을 보고 승인·반려하는 전체 흐름. 승인 30일 후 증빙 파일은 worker가 자동 삭제.

**Architecture:** PRD §2.2 권한 매트릭스를 `app/deps.py`의 4개 표준 가드(`require_user`·`require_admin`·`require_badge(level)`·`require_resident_in_region(region_id)`)로 강제한다. 배지 신청은 모델 단(`BadgeApplication` + `BadgeEvidence`)을 P1.1에서 이미 만들어 두었으므로 P1.2는 **서비스 + 라우트 + 템플릿 + 워커 핸들러**만 추가한다. 증빙 파일은 비공개 디렉토리(`EVIDENCE_BASE_PATH`)에 path만 DB에 보관, 승인 30일 후 `JobKind.EVIDENCE_CLEANUP` worker 잡으로 파일+행 삭제. EXIF 제거·이미지 리사이즈는 P1.3에서 통합되므로 P1.2는 raw 파일 저장만 (관리자만 접근하는 비공개 경로라 안전).

**Tech Stack:** FastAPI Depends 가드, Jinja2 SSR (HTMX는 P1.3부터), python-multipart (`UploadFile`), Pillow는 P1.3 보류, Phase 1.1의 `app/workers/queue.py` enqueue API.

---

## P1.2 잠정 가정 (sub-plan 내 확정 필요)

| OI | 잠정 가정 | 영향 범위 |
|---|---|---|
| OI-3 | 증빙 파일 4종 (utility_bill·contract·building_cert·geo_selfie) 모두 허용. 최소 1개 첨부 강제. 관리자가 시각으로 검토 — 자동 검증 없음 | Task 5 (resident 신청 폼) |
| OI-3 | region_verified 는 **주소 텍스트 입력 + region_id 선택** 만으로 신청 → 관리자 승인. GPS·셀카 자동 검증은 Phase 2 | Task 4 (region 신청) |
| 증빙 저장소 | 로컬 dev: `./media-private/evidence/` (gitignore 추가). 운영(P1.5+): `/var/nestory/evidence/`. ENV `EVIDENCE_BASE_PATH` 로 주입 | Task 3 (evidence_storage) |
| EXIF 제거 | P1.2 미적용 (raw 저장). P1.3 image pipeline 통합 시점에 EXIF 제거. 증빙은 비공개 경로라 단기 안전 | Task 3·5 |
| 30일 보존 | 승인 시점 기준 30일 후 evidence_cleanup 잡이 파일+행 삭제. 반려된 신청은 즉시 cleanup | Task 7·8 |

---

## 파일 구조 개요

P1.2 종료 시 저장소에 추가/변경되는 파일:

```
nestory/
├── app/
│   ├── config.py                            # 갱신: evidence_base_path 필드
│   ├── deps.py                              # 갱신: require_badge, require_resident_in_region 추가
│   ├── main.py                              # 갱신: me_router, admin_router 등록
│   │
│   ├── services/
│   │   ├── badges.py                        # 신규: 신청·승인·반려·전이 비즈니스 로직
│   │   └── evidence_storage.py              # 신규: 비공개 디렉토리 파일 저장·삭제·path
│   │
│   ├── routers/
│   │   ├── me.py                            # 신규: /me/badge GET·POST (region·resident 신청)
│   │   └── admin.py                         # 신규: /admin/badge-queue GET·POST (목록·승인·반려·증빙 다운로드)
│   │
│   ├── templates/
│   │   ├── components/
│   │   │   └── badge.html                   # 신규: 배지 표시 컴포넌트 (badge_level → 이모지·라벨)
│   │   └── pages/
│   │       ├── me_badge.html                # 신규: 내 배지 + 신청 폼
│   │       ├── admin_badge_queue.html       # 신규: 신청 목록
│   │       └── admin_badge_detail.html      # 신규: 단일 신청 상세 (증빙 + 승인/반려)
│   │
│   ├── workers/
│   │   └── handlers/
│   │       └── evidence_cleanup.py          # 신규: JobKind.EVIDENCE_CLEANUP 핸들러
│   │
│   └── tests/integration/
│       ├── test_deps_guards.py              # 신규: 4개 가드 unit·integration
│       ├── test_badges_service.py           # 신규: services/badges 단위
│       ├── test_evidence_storage.py         # 신규: 파일 IO + cleanup
│       ├── test_me_badge_routes.py          # 신규: /me/badge HTTP
│       ├── test_admin_badge_routes.py       # 신규: /admin/badge-queue HTTP
│       ├── test_evidence_cleanup_handler.py # 신규: 핸들러 단위
│       └── test_badge_workflow_e2e.py       # 신규: 가입→신청→승인→cleanup round-trip
│
├── .env.example                             # 갱신: EVIDENCE_BASE_PATH=
├── .gitignore                               # 갱신: media-private/
└── media-private/                           # 신규 (런타임에 생성, gitignore)
```

---

## Task 1: deps.py 권한 가드 확장 — `require_badge`·`require_resident_in_region`

**Files:**
- Modify: `app/deps.py`
- Create: `app/tests/integration/test_deps_guards.py`

PRD §6.2 [v1.1 · C2] — 라우트 인증·인가는 모두 표준 가드로만 강제. P1.1의 `require_user`·`require_admin` 위에 배지 레벨 + 시군 거주자 가드를 추가.

- [ ] **Step 1: 가드 확장**

`app/deps.py` 를 다음으로 교체:

```python
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import BadgeLevel, User, UserRole


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


def require_user(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Login required")
    return user


def require_admin(user: User = Depends(require_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user


_BADGE_RANK = {
    BadgeLevel.INTERESTED: 0,
    BadgeLevel.REGION_VERIFIED: 1,
    BadgeLevel.RESIDENT: 2,
    BadgeLevel.EX_RESIDENT: -1,  # 작성 권한 박탈 — 어떤 require_badge도 통과 안 함
}


def require_badge(min_level: BadgeLevel) -> Callable[[User], User]:
    """배지 레벨 기반 가드 팩토리.

    `Depends(require_badge(BadgeLevel.RESIDENT))` 형태로 라우트에서 사용.
    EX_RESIDENT 는 모든 require_badge 가드를 통과 못한다 (PRD §5.4.1).
    """
    required_rank = _BADGE_RANK[min_level]

    def _checker(user: User = Depends(require_user)) -> User:
        user_rank = _BADGE_RANK.get(user.badge_level, -1)
        if user_rank < required_rank:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"Badge level '{min_level.value}' or higher required",
            )
        return user

    return _checker


def require_resident_in_region(region_id_param: str = "region_id") -> Callable[..., User]:
    """동일 시군의 resident 만 통과 — Pillar V 검증 권한 등에 사용.

    `region_id_param` 은 path/query parameter 이름. 기본값 'region_id'.
    """

    def _checker(
        request: Request,
        user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    ) -> User:
        path_value = request.path_params.get(region_id_param)
        query_value = request.query_params.get(region_id_param)
        target_region_id = path_value or query_value
        if target_region_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Missing '{region_id_param}' in request",
            )
        if user.primary_region_id is None or str(user.primary_region_id) != str(target_region_id):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Resident in this region only",
            )
        return user

    return _checker


__all__ = [
    "get_current_user",
    "get_db",
    "require_admin",
    "require_badge",
    "require_resident_in_region",
    "require_user",
]
```

> **NOTE**: User 모델에 `primary_region_id` 컬럼은 PRD §5.1에 있지만 P1.0 user.py 에는 아직 없을 수 있음. 확인 필요. 만약 없다면 별도 마이그레이션 task 가 선행되어야 함 — Step 2 검증에서 확인.

- [ ] **Step 2: User.primary_region_id 컬럼 확인**

Run: `uv run python -c "from app.models.user import User; print('primary_region_id' in User.__table__.columns.keys())"`

출력 `False` 이면 모델·마이그레이션 추가 필요. **이 경우 BLOCKED 보고하고 controller 가 별도 task 추가**. 출력 `True` 이면 다음 step 진행.

- [ ] **Step 3: 단위·통합 테스트 작성**

`app/tests/integration/test_deps_guards.py`:

```python
from datetime import UTC, datetime

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.deps import (
    require_admin,
    require_badge,
    require_resident_in_region,
    require_user,
)
from app.models import Region, User
from app.models.user import BadgeLevel, UserRole


def _make_user(
    db: Session,
    *,
    badge: BadgeLevel = BadgeLevel.INTERESTED,
    role: UserRole = UserRole.USER,
    primary_region_id: int | None = None,
) -> User:
    ts = int(datetime.now(UTC).timestamp() * 1_000_000)
    u = User(
        email=f"t{ts}@example.com",
        username=f"u{ts}",
        display_name="테스터",
        password_hash="x",
        badge_level=badge,
        role=role,
        primary_region_id=primary_region_id,
    )
    db.add(u)
    db.flush()
    return u


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="t" * 32)

    @app.get("/protected")
    def protected(user: User = Depends(require_user)) -> dict:
        return {"id": user.id}

    @app.get("/admin")
    def admin(user: User = Depends(require_admin)) -> dict:
        return {"id": user.id}

    @app.get("/resident")
    def resident_only(user: User = Depends(require_badge(BadgeLevel.RESIDENT))) -> dict:
        return {"id": user.id}

    @app.get("/region/{region_id}")
    def region_only(
        region_id: int,
        user: User = Depends(require_resident_in_region("region_id")),
    ) -> dict:
        return {"id": user.id, "region_id": region_id}

    return app


def _login(client: TestClient, user_id: int) -> None:
    with client:
        response = client.get("/protected")
        # session 직접 주입은 starlette TestClient의 session API 미제공 — 대신 우회:
    # TestClient는 cookies로 작동하지만 itsdangerous 서명이 필요해 직접 session 조작 어려움.
    # 따라서 fixture 패턴으로 작성한다 — 아래 conftest fixture 활용.


def test_require_user_unauthenticated_rejects(client: TestClient) -> None:
    test_app = _build_app()
    with TestClient(test_app) as c:
        r = c.get("/protected")
        assert r.status_code == 401


def test_require_user_authenticated_passes(db: Session, client: TestClient) -> None:
    test_app = _build_app()
    user = _make_user(db)
    with TestClient(test_app) as c:
        # itsdangerous 서명 세션 직접 주입 — starlette session middleware 호환
        from itsdangerous import URLSafeSerializer
        s = URLSafeSerializer("t" * 32, salt="starlette.sessions")
        c.cookies.set("session", s.dumps({"user_id": user.id}))
        r = c.get("/protected")
        assert r.status_code == 200
        assert r.json() == {"id": user.id}


def test_require_admin_non_admin_rejects(db: Session) -> None:
    test_app = _build_app()
    user = _make_user(db, role=UserRole.USER)
    with TestClient(test_app) as c:
        from itsdangerous import URLSafeSerializer
        s = URLSafeSerializer("t" * 32, salt="starlette.sessions")
        c.cookies.set("session", s.dumps({"user_id": user.id}))
        assert c.get("/admin").status_code == 403


def test_require_admin_admin_passes(db: Session) -> None:
    test_app = _build_app()
    user = _make_user(db, role=UserRole.ADMIN)
    with TestClient(test_app) as c:
        from itsdangerous import URLSafeSerializer
        s = URLSafeSerializer("t" * 32, salt="starlette.sessions")
        c.cookies.set("session", s.dumps({"user_id": user.id}))
        assert c.get("/admin").status_code == 200


@pytest.mark.parametrize(
    "user_badge,expected",
    [
        (BadgeLevel.INTERESTED, 403),
        (BadgeLevel.REGION_VERIFIED, 403),
        (BadgeLevel.RESIDENT, 200),
        (BadgeLevel.EX_RESIDENT, 403),
    ],
)
def test_require_badge_resident(db: Session, user_badge, expected) -> None:
    test_app = _build_app()
    user = _make_user(db, badge=user_badge)
    with TestClient(test_app) as c:
        from itsdangerous import URLSafeSerializer
        s = URLSafeSerializer("t" * 32, salt="starlette.sessions")
        c.cookies.set("session", s.dumps({"user_id": user.id}))
        assert c.get("/resident").status_code == expected


def test_require_resident_in_region_match(db: Session) -> None:
    test_app = _build_app()
    r = Region(sido="경기", sigungu="양평군", slug="yp-test-deps")
    db.add(r)
    db.flush()
    user = _make_user(db, badge=BadgeLevel.RESIDENT, primary_region_id=r.id)
    with TestClient(test_app) as c:
        from itsdangerous import URLSafeSerializer
        s = URLSafeSerializer("t" * 32, salt="starlette.sessions")
        c.cookies.set("session", s.dumps({"user_id": user.id}))
        assert c.get(f"/region/{r.id}").status_code == 200


def test_require_resident_in_region_mismatch(db: Session) -> None:
    test_app = _build_app()
    r1 = Region(sido="경기", sigungu="양평군", slug="yp-test-deps-2")
    r2 = Region(sido="경기", sigungu="가평군", slug="gp-test-deps-2")
    db.add_all([r1, r2])
    db.flush()
    user = _make_user(db, badge=BadgeLevel.RESIDENT, primary_region_id=r1.id)
    with TestClient(test_app) as c:
        from itsdangerous import URLSafeSerializer
        s = URLSafeSerializer("t" * 32, salt="starlette.sessions")
        c.cookies.set("session", s.dumps({"user_id": user.id}))
        assert c.get(f"/region/{r2.id}").status_code == 403
```

- [ ] **Step 4: 전체 ruff + 전체 pytest**

Run: `uv run ruff check app/ && uv run pytest app/tests/ -q`
Expected: `99 passed` (90 baseline + 9 new — parametrize 4 + 5 individual).

- [ ] **Step 5: Commit**

```bash
git add app/deps.py app/tests/integration/test_deps_guards.py
git commit -m "feat(deps): add require_badge and require_resident_in_region guards"
```

---

## Task 2: services/badges.py — 신청·승인·반려 비즈니스 로직

**Files:**
- Create: `app/services/badges.py`
- Create: `app/tests/integration/test_badges_service.py`

PRD §5.4 + §5.4.1 — 배지 상태 머신을 비즈니스 로직 함수로 표현. 라우트는 폼 파싱·검증만 하고 모든 전이는 이 서비스를 통과.

- [ ] **Step 1: 서비스 모듈 작성**

`app/services/badges.py`:

```python
"""Badge application & promotion business logic.

Reference: PRD §2.2 (권한 매트릭스), §5.4 (상태 머신), §5.4.1 (재검증·이사·탈거).

All functions accept Session and flush only — caller commits.
"""
from datetime import UTC, datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AuditLog,
    BadgeApplication,
    BadgeEvidence,
    Notification,
    User,
)
from app.models._enums import (
    AuditAction,
    BadgeApplicationStatus,
    BadgeRequestedLevel,
    EvidenceType,
    NotificationType,
)
from app.models.user import BadgeLevel


def submit_application(
    db: Session,
    *,
    user: User,
    requested_level: BadgeRequestedLevel,
    region_id: int,
) -> BadgeApplication:
    """Create a new pending BadgeApplication. Caller must commit."""
    app_obj = BadgeApplication(
        user_id=user.id,
        requested_level=requested_level,
        region_id=region_id,
        status=BadgeApplicationStatus.PENDING,
    )
    db.add(app_obj)
    db.flush()
    return app_obj


def attach_evidence(
    db: Session,
    *,
    application: BadgeApplication,
    evidence_type: EvidenceType,
    file_path: str,
    scheduled_delete_at: datetime | None = None,
) -> BadgeEvidence:
    """Attach a stored evidence file's path to a BadgeApplication."""
    e = BadgeEvidence(
        application_id=application.id,
        evidence_type=evidence_type,
        file_path=file_path,
        scheduled_delete_at=scheduled_delete_at,
    )
    db.add(e)
    db.flush()
    return e


def list_pending(db: Session) -> Sequence[BadgeApplication]:
    """Return all pending applications, oldest first."""
    stmt = (
        select(BadgeApplication)
        .where(BadgeApplication.status == BadgeApplicationStatus.PENDING)
        .order_by(BadgeApplication.applied_at.asc())
    )
    return db.scalars(stmt).all()


def approve(
    db: Session,
    *,
    application: BadgeApplication,
    reviewer: User,
    note: str | None = None,
) -> None:
    """Approve a pending application — promotes user, writes audit + notification.

    Caller must commit. After commit, caller should enqueue an
    `evidence_cleanup` job (30 days delay) — see Task 7.
    """
    if application.status != BadgeApplicationStatus.PENDING:
        raise ValueError(f"Cannot approve application in status {application.status}")

    target_user = db.get(User, application.user_id)
    if target_user is None:
        raise ValueError(f"User {application.user_id} not found")

    # Update application
    application.status = BadgeApplicationStatus.APPROVED
    application.reviewer_id = reviewer.id
    application.review_note = note
    application.reviewed_at = datetime.now(UTC)

    # Promote user
    if application.requested_level == BadgeRequestedLevel.REGION_VERIFIED:
        target_user.badge_level = BadgeLevel.REGION_VERIFIED
        target_user.primary_region_id = application.region_id
    elif application.requested_level == BadgeRequestedLevel.RESIDENT:
        target_user.badge_level = BadgeLevel.RESIDENT
        target_user.primary_region_id = application.region_id
        target_user.resident_verified_at = datetime.now(UTC)
        target_user.resident_revalidated_at = datetime.now(UTC)

    # Audit log
    db.add(
        AuditLog(
            actor_id=reviewer.id,
            action=AuditAction.BADGE_APPROVED,
            target_type="badge_application",
            target_id=application.id,
            note=note,
        )
    )

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

    db.flush()


def reject(
    db: Session,
    *,
    application: BadgeApplication,
    reviewer: User,
    note: str,
) -> None:
    """Reject a pending application — writes audit + notification.

    Note is required for rejection (user-facing reason).
    Caller must commit. Evidence files should be cleaned up immediately
    (caller enqueues evidence_cleanup with run_after=now).
    """
    if application.status != BadgeApplicationStatus.PENDING:
        raise ValueError(f"Cannot reject application in status {application.status}")

    application.status = BadgeApplicationStatus.REJECTED
    application.reviewer_id = reviewer.id
    application.review_note = note
    application.reviewed_at = datetime.now(UTC)

    db.add(
        AuditLog(
            actor_id=reviewer.id,
            action=AuditAction.BADGE_REJECTED,
            target_type="badge_application",
            target_id=application.id,
            note=note,
        )
    )

    db.add(
        Notification(
            user_id=application.user_id,
            type=NotificationType.BADGE_REJECTED,
            source_user_id=reviewer.id,
            target_type="badge_application",
            target_id=application.id,
        )
    )

    db.flush()


def evidences_for(db: Session, application_id: int) -> Sequence[BadgeEvidence]:
    """Return all evidence rows for an application."""
    stmt = (
        select(BadgeEvidence)
        .where(BadgeEvidence.application_id == application_id)
        .order_by(BadgeEvidence.uploaded_at.asc())
    )
    return db.scalars(stmt).all()
```

- [ ] **Step 2: 단위 테스트**

`app/tests/integration/test_badges_service.py`:

```python
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.models import BadgeApplication, Notification, Region, User
from app.models._enums import (
    BadgeApplicationStatus,
    BadgeRequestedLevel,
    EvidenceType,
    NotificationType,
)
from app.models.user import BadgeLevel, UserRole
from app.services.badges import (
    approve,
    attach_evidence,
    evidences_for,
    list_pending,
    reject,
    submit_application,
)


def _seed(db: Session) -> tuple[User, User, Region]:
    ts = int(datetime.now(UTC).timestamp() * 1_000_000)
    applicant = User(
        email=f"a{ts}@example.com",
        username=f"a{ts}",
        display_name="신청자",
        password_hash="x",
    )
    admin = User(
        email=f"adm{ts}@example.com",
        username=f"adm{ts}",
        display_name="관리자",
        password_hash="x",
        role=UserRole.ADMIN,
    )
    region = Region(sido="경기", sigungu="양평군", slug=f"yp-{ts}")
    db.add_all([applicant, admin, region])
    db.flush()
    return applicant, admin, region


def test_submit_application_pending(db: Session) -> None:
    user, _, region = _seed(db)
    app_obj = submit_application(
        db,
        user=user,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
    )
    db.commit()
    assert app_obj.status == BadgeApplicationStatus.PENDING
    assert app_obj.user_id == user.id


def test_attach_evidence(db: Session) -> None:
    user, _, region = _seed(db)
    app_obj = submit_application(
        db, user=user, requested_level=BadgeRequestedLevel.RESIDENT, region_id=region.id
    )
    e = attach_evidence(
        db,
        application=app_obj,
        evidence_type=EvidenceType.UTILITY_BILL,
        file_path="/private/evidence/2026/05/abc.jpg",
    )
    db.commit()
    assert e.id is not None
    assert e.evidence_type == EvidenceType.UTILITY_BILL


def test_list_pending_orders_oldest_first(db: Session) -> None:
    u1, _, region = _seed(db)
    submit_application(db, user=u1, requested_level=BadgeRequestedLevel.RESIDENT, region_id=region.id)
    submit_application(db, user=u1, requested_level=BadgeRequestedLevel.REGION_VERIFIED, region_id=region.id)
    db.commit()
    pending = list_pending(db)
    assert len(pending) == 2
    assert pending[0].requested_level == BadgeRequestedLevel.RESIDENT  # 먼저 신청


def test_approve_resident_promotes_user(db: Session) -> None:
    user, admin_user, region = _seed(db)
    app_obj = submit_application(
        db, user=user, requested_level=BadgeRequestedLevel.RESIDENT, region_id=region.id
    )
    approve(db, application=app_obj, reviewer=admin_user, note="확인 완료")
    db.commit()

    db.refresh(user)
    assert user.badge_level == BadgeLevel.RESIDENT
    assert user.primary_region_id == region.id
    assert user.resident_verified_at is not None
    assert user.resident_revalidated_at is not None
    assert app_obj.status == BadgeApplicationStatus.APPROVED
    assert app_obj.reviewer_id == admin_user.id
    assert app_obj.reviewed_at is not None


def test_approve_region_verified_only(db: Session) -> None:
    user, admin_user, region = _seed(db)
    app_obj = submit_application(
        db,
        user=user,
        requested_level=BadgeRequestedLevel.REGION_VERIFIED,
        region_id=region.id,
    )
    approve(db, application=app_obj, reviewer=admin_user)
    db.commit()
    db.refresh(user)
    assert user.badge_level == BadgeLevel.REGION_VERIFIED
    assert user.resident_verified_at is None  # resident 가 아니므로 미설정


def test_approve_creates_audit_and_notification(db: Session) -> None:
    user, admin_user, region = _seed(db)
    app_obj = submit_application(
        db, user=user, requested_level=BadgeRequestedLevel.RESIDENT, region_id=region.id
    )
    approve(db, application=app_obj, reviewer=admin_user)
    db.commit()

    notifs = db.query(Notification).filter_by(user_id=user.id).all()
    assert len(notifs) == 1
    assert notifs[0].type == NotificationType.BADGE_APPROVED


def test_reject_blocks_promotion(db: Session) -> None:
    user, admin_user, region = _seed(db)
    app_obj = submit_application(
        db, user=user, requested_level=BadgeRequestedLevel.RESIDENT, region_id=region.id
    )
    reject(db, application=app_obj, reviewer=admin_user, note="증빙 불충분")
    db.commit()

    db.refresh(user)
    assert user.badge_level == BadgeLevel.INTERESTED  # 미변경
    assert app_obj.status == BadgeApplicationStatus.REJECTED
    assert app_obj.review_note == "증빙 불충분"


def test_approve_rejects_non_pending(db: Session) -> None:
    user, admin_user, region = _seed(db)
    app_obj = submit_application(
        db, user=user, requested_level=BadgeRequestedLevel.RESIDENT, region_id=region.id
    )
    approve(db, application=app_obj, reviewer=admin_user)
    db.commit()
    with pytest.raises(ValueError, match="Cannot approve"):
        approve(db, application=app_obj, reviewer=admin_user)


def test_evidences_for_returns_attached(db: Session) -> None:
    user, _, region = _seed(db)
    app_obj = submit_application(
        db, user=user, requested_level=BadgeRequestedLevel.RESIDENT, region_id=region.id
    )
    attach_evidence(
        db, application=app_obj, evidence_type=EvidenceType.UTILITY_BILL, file_path="/p/1.jpg"
    )
    attach_evidence(
        db, application=app_obj, evidence_type=EvidenceType.CONTRACT, file_path="/p/2.jpg"
    )
    db.commit()
    es = evidences_for(db, app_obj.id)
    assert len(es) == 2
```

- [ ] **Step 3: 전체 ruff + pytest**
Expected: 99 baseline + 8 new = `107 passed`. (Task 1이 9개 추가했으므로 누적 99에서 시작.)

- [ ] **Step 4: Commit**

```bash
git add app/services/badges.py app/tests/integration/test_badges_service.py
git commit -m "feat(services): add badges service for application/approval/rejection workflow"
```

---

## Task 3: services/evidence_storage.py — 비공개 디렉토리 파일 IO

**Files:**
- Modify: `app/config.py` (+ `evidence_base_path` 필드)
- Modify: `.env.example` (+ `EVIDENCE_BASE_PATH=`)
- Modify: `.gitignore` (+ `media-private/`)
- Create: `app/services/evidence_storage.py`
- Create: `app/tests/integration/test_evidence_storage.py`

PRD §6.4 + §8.1 — 증빙은 비공개 디렉토리(웹에서 직접 접근 불가)에 저장하고 `BadgeEvidence.file_path` 에 path만 보관. 30일 후 worker 가 삭제.

- [ ] **Step 1: 설정 갱신**

`app/config.py` — `evidence_base_path` 필드 추가:

```python
class Settings(BaseSettings):
    # ... 기존 필드 ...
    evidence_base_path: str = "./media-private/evidence"
```

`.env.example` 끝에 추가:
```
EVIDENCE_BASE_PATH=./media-private/evidence
```

`.gitignore` 끝에 추가:
```
media-private/
```

- [ ] **Step 2: 저장소 모듈 작성**

`app/services/evidence_storage.py`:

```python
"""Private evidence file storage (filesystem).

Files are stored under EVIDENCE_BASE_PATH and never exposed via static mounts.
Path layout: {base}/{YYYY}/{MM}/{application_id}/{uuid}.{ext}

Reference: PRD §6.4 (저장 레이아웃) · §8.1 (비공개 디렉토리).
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import BinaryIO

from app.config import get_settings

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf", ".heic"}
MAX_BYTES = 10 * 1024 * 1024  # 10MB


def _base_dir() -> Path:
    return Path(get_settings().evidence_base_path).resolve()


def store(
    *,
    application_id: int,
    filename: str,
    stream: BinaryIO,
    now_year: int,
    now_month: int,
) -> str:
    """Persist a file to the private evidence dir. Returns the absolute path string.

    - Validates extension against ALLOWED_EXTENSIONS.
    - Validates size against MAX_BYTES (raises ValueError if exceeded).
    - Generates a uuid4 filename to avoid path traversal.
    """
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValueError(f"File extension '{suffix}' not allowed")

    target_dir = _base_dir() / f"{now_year:04d}" / f"{now_month:02d}" / str(application_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{uuid.uuid4().hex}{suffix}"

    written = 0
    with target_path.open("wb") as out:
        while True:
            chunk = stream.read(64 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > MAX_BYTES:
                out.close()
                target_path.unlink(missing_ok=True)
                raise ValueError(f"File too large (> {MAX_BYTES} bytes)")
            out.write(chunk)

    return str(target_path)


def delete(path: str) -> bool:
    """Delete a stored file. Returns True if deleted, False if missing."""
    p = Path(path)
    if not p.exists():
        return False
    p.unlink()
    # Try to clean up empty parent dirs (year/month/application) up to base.
    base = _base_dir()
    parent = p.parent
    while parent != base and parent.exists() and not any(parent.iterdir()):
        parent.rmdir()
        parent = parent.parent
    return True


def delete_all_for_application(application_id: int) -> int:
    """Delete the entire {base}/{YYYY}/{MM}/{application_id}/ directory tree.

    Returns count of files deleted. Used by evidence_cleanup worker.
    """
    base = _base_dir()
    deleted = 0
    if not base.exists():
        return 0
    for year_dir in base.iterdir():
        if not year_dir.is_dir():
            continue
        for month_dir in year_dir.iterdir():
            if not month_dir.is_dir():
                continue
            app_dir = month_dir / str(application_id)
            if app_dir.exists() and app_dir.is_dir():
                deleted += sum(1 for _ in app_dir.rglob("*") if _.is_file())
                shutil.rmtree(app_dir)
                # cleanup empty parents
                if not any(month_dir.iterdir()):
                    month_dir.rmdir()
                    if not any(year_dir.iterdir()):
                        year_dir.rmdir()
    return deleted
```

- [ ] **Step 3: 테스트**

`app/tests/integration/test_evidence_storage.py`:

```python
import io
from pathlib import Path

import pytest

from app.config import get_settings
from app.services import evidence_storage


@pytest.fixture(autouse=True)
def _isolate_evidence_dir(tmp_path, monkeypatch):
    """Each test gets a fresh tmp evidence dir — settings cache cleared."""
    monkeypatch.setenv("EVIDENCE_BASE_PATH", str(tmp_path / "evidence"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_store_creates_file_with_uuid_name() -> None:
    path = evidence_storage.store(
        application_id=42,
        filename="utility_bill.jpg",
        stream=io.BytesIO(b"fake-jpg-content"),
        now_year=2026,
        now_month=5,
    )
    p = Path(path)
    assert p.exists()
    assert p.suffix == ".jpg"
    assert "/2026/05/42/" in path.replace("\\", "/")
    assert p.read_bytes() == b"fake-jpg-content"


def test_store_rejects_disallowed_extension() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        evidence_storage.store(
            application_id=1,
            filename="evil.exe",
            stream=io.BytesIO(b"x"),
            now_year=2026,
            now_month=5,
        )


def test_store_rejects_oversize_file() -> None:
    big = io.BytesIO(b"x" * (evidence_storage.MAX_BYTES + 1))
    with pytest.raises(ValueError, match="too large"):
        evidence_storage.store(
            application_id=1, filename="big.jpg", stream=big, now_year=2026, now_month=5
        )


def test_delete_removes_file() -> None:
    path = evidence_storage.store(
        application_id=1,
        filename="x.jpg",
        stream=io.BytesIO(b"x"),
        now_year=2026,
        now_month=5,
    )
    assert evidence_storage.delete(path) is True
    assert evidence_storage.delete(path) is False  # 두 번째는 missing


def test_delete_all_for_application() -> None:
    p1 = evidence_storage.store(
        application_id=99, filename="a.jpg", stream=io.BytesIO(b"a"), now_year=2026, now_month=5
    )
    p2 = evidence_storage.store(
        application_id=99, filename="b.pdf", stream=io.BytesIO(b"b"), now_year=2026, now_month=5
    )
    n = evidence_storage.delete_all_for_application(99)
    assert n == 2
    assert not Path(p1).exists()
    assert not Path(p2).exists()
```

- [ ] **Step 4: 전체 ruff + pytest**
Expected: `112 passed` (107 baseline + 5 new).

- [ ] **Step 5: Commit**

```bash
git add app/config.py app/services/evidence_storage.py app/tests/integration/test_evidence_storage.py .env.example .gitignore
git commit -m "feat(services): add evidence_storage with private path layout and size/ext validation"
```

---

## Task 4: /me/badge GET + region_verified 신청 POST

**Files:**
- Create: `app/routers/me.py`
- Create: `app/templates/components/badge.html`
- Create: `app/templates/pages/me_badge.html`
- Modify: `app/main.py` (라우터 등록)
- Create: `app/tests/integration/test_me_badge_routes.py`

PRD §4.2·§4.3 — `/me/badge` 는 🔒 로그인 필요. 사용자가 자신의 배지 상태 확인 + region_verified 신청. resident 신청은 Task 5 에서 (파일 업로드 분리).

- [ ] **Step 1: 라우터 작성**

`app/routers/me.py`:

```python
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.deps import get_db, require_user
from app.models import BadgeApplication, Region, User
from app.models._enums import BadgeApplicationStatus, BadgeRequestedLevel
from app.services import badges
from app.templating import templates

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/badge", response_class=HTMLResponse)
def badge_page(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    pending = (
        db.query(BadgeApplication)
        .filter(
            BadgeApplication.user_id == user.id,
            BadgeApplication.status == BadgeApplicationStatus.PENDING,
        )
        .order_by(BadgeApplication.applied_at.desc())
        .first()
    )
    regions = db.query(Region).order_by(Region.sigungu).all()
    return templates.TemplateResponse(
        request,
        "pages/me_badge.html",
        {"user": user, "pending": pending, "regions": regions},
    )


@router.post("/badge/region")
def apply_region(
    region_id: int = Form(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid region")

    # Block duplicate pending applications
    existing = (
        db.query(BadgeApplication)
        .filter(
            BadgeApplication.user_id == user.id,
            BadgeApplication.status == BadgeApplicationStatus.PENDING,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pending application exists")

    badges.submit_application(
        db,
        user=user,
        requested_level=BadgeRequestedLevel.REGION_VERIFIED,
        region_id=region.id,
    )
    db.commit()
    return RedirectResponse("/me/badge", status_code=status.HTTP_303_SEE_OTHER)
```

- [ ] **Step 2: 템플릿 작성**

`app/templates/components/badge.html`:

```jinja2
{# Reusable badge display — input: badge_level (BadgeLevel enum value as string) #}
{% set labels = {
    "interested": ("🌱", "관심자"),
    "region_verified": ("📍", "지역 인증"),
    "resident": ("🏡", "실거주자"),
    "ex_resident": ("🌿", "이전 거주자"),
} %}
{% set emoji, label = labels.get(badge_level, ("❔", "알 수 없음")) %}
<span class="inline-flex items-center gap-1 rounded bg-emerald-50 px-2 py-1 text-sm">
  <span aria-hidden="true">{{ emoji }}</span>
  <span>{{ label }}</span>
</span>
```

`app/templates/pages/me_badge.html`:

```jinja2
{% extends "base.html" %}
{% block title %}내 배지 · Nestory{% endblock %}
{% block content %}
<section class="mx-auto max-w-2xl p-6 space-y-6">
  <h1 class="text-2xl font-bold">내 배지</h1>

  <div class="rounded border p-4">
    <p class="text-sm text-slate-600">현재 배지</p>
    <div class="mt-2">
      {% include "components/badge.html" %}
    </div>
  </div>

  {% if pending %}
    <div class="rounded border-2 border-amber-200 bg-amber-50 p-4">
      <p class="font-semibold">신청 대기 중</p>
      <p class="text-sm">관리자 승인 대기 — 평균 48시간 이내 처리됩니다.</p>
    </div>
  {% else %}
    {% if user.badge_level == "interested" %}
      <form method="post" action="/me/badge/region" class="rounded border p-4 space-y-3">
        <h2 class="font-semibold">📍 지역 인증 신청</h2>
        <p class="text-sm text-slate-600">관심 시군을 선택하세요. 관리자가 승인하면 그 지역의 커뮤니티에 글을 쓸 수 있습니다.</p>
        <select name="region_id" required class="w-full rounded border p-2">
          <option value="">— 시군 선택 —</option>
          {% for r in regions %}
            <option value="{{ r.id }}">{{ r.sido }} {{ r.sigungu }}</option>
          {% endfor %}
        </select>
        <button type="submit" class="rounded bg-emerald-600 text-white px-4 py-2">신청</button>
      </form>
    {% endif %}

    {% if user.badge_level in ("region_verified", "interested") %}
      <a href="/me/badge/resident" class="block rounded border p-4 hover:bg-slate-50">
        <h2 class="font-semibold">🏡 실거주자 인증 신청 →</h2>
        <p class="text-sm text-slate-600">증빙 파일(공과금·계약서·건축물대장 등)을 업로드합니다.</p>
      </a>
    {% endif %}
  {% endif %}
</section>
{% endblock %}
```

- [ ] **Step 3: main.py 라우터 등록**

`app/main.py` 의 router include 부분에 추가:

```python
from app.routers import me as me_router
# ...
app.include_router(me_router.router)
```

- [ ] **Step 4: 통합 테스트**

`app/tests/integration/test_me_badge_routes.py`:

```python
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from itsdangerous import URLSafeSerializer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BadgeApplication, Region, User


def _login_cookie(user_id: int) -> str:
    s = URLSafeSerializer(get_settings().app_secret_key, salt="starlette.sessions")
    return s.dumps({"user_id": user_id})


def _make_user(db: Session) -> User:
    ts = int(datetime.now(UTC).timestamp() * 1_000_000)
    u = User(
        email=f"t{ts}@example.com",
        username=f"u{ts}",
        display_name="테스터",
        password_hash="x",
    )
    db.add(u)
    db.flush()
    db.commit()
    return u


def test_badge_page_requires_login(client: TestClient) -> None:
    r = client.get("/me/badge")
    assert r.status_code == 401


def test_badge_page_renders_for_logged_in_user(db: Session, client: TestClient) -> None:
    user = _make_user(db)
    client.cookies.set("nestory_session", _login_cookie(user.id))
    r = client.get("/me/badge")
    assert r.status_code == 200
    assert "내 배지" in r.text
    assert "관심자" in r.text  # 기본 배지 표시


def test_apply_region_creates_pending_application(db: Session, client: TestClient) -> None:
    user = _make_user(db)
    region = Region(sido="경기", sigungu="양평군", slug="yp-me-test")
    db.add(region)
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(user.id))
    r = client.post("/me/badge/region", data={"region_id": region.id}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/me/badge"

    apps = db.query(BadgeApplication).filter_by(user_id=user.id).all()
    assert len(apps) == 1
    assert apps[0].region_id == region.id


def test_apply_region_blocks_duplicate_pending(db: Session, client: TestClient) -> None:
    user = _make_user(db)
    region = Region(sido="경기", sigungu="양평군", slug="yp-dup")
    db.add(region)
    db.commit()
    client.cookies.set("nestory_session", _login_cookie(user.id))
    client.post("/me/badge/region", data={"region_id": region.id})
    r = client.post("/me/badge/region", data={"region_id": region.id})
    assert r.status_code == 409


def test_apply_region_invalid_id(db: Session, client: TestClient) -> None:
    user = _make_user(db)
    client.cookies.set("nestory_session", _login_cookie(user.id))
    r = client.post("/me/badge/region", data={"region_id": 99999})
    assert r.status_code == 400
```

- [ ] **Step 5: 전체 ruff + pytest**
Expected: `117 passed` (112 + 5).

- [ ] **Step 6: Commit**

```bash
git add app/routers/me.py app/templates/components/badge.html app/templates/pages/me_badge.html app/main.py app/tests/integration/test_me_badge_routes.py
git commit -m "feat(routes): add /me/badge page and region_verified application flow"
```

---

## Task 5: resident 신청 — 증빙 업로드 폼

**Files:**
- Modify: `app/routers/me.py` (+ `/me/badge/resident` GET·POST)
- Create: `app/templates/pages/me_badge_resident.html`
- Modify: `app/tests/integration/test_me_badge_routes.py` (+ tests)

PRD §5.5 — 증빙 4종 (utility_bill·contract·building_cert·geo_selfie). 최소 1개 첨부 필수. 폼은 multipart, region_id 선택 + 각 증빙 type 별 파일 input.

- [ ] **Step 1: GET 폼 + POST 처리 추가**

`app/routers/me.py` 끝에 추가:

```python
from datetime import UTC, datetime
from typing import Annotated

from fastapi import File, UploadFile

from app.models._enums import EvidenceType
from app.services import evidence_storage


@router.get("/badge/resident", response_class=HTMLResponse)
def resident_form(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    regions = db.query(Region).order_by(Region.sigungu).all()
    return templates.TemplateResponse(
        request,
        "pages/me_badge_resident.html",
        {"user": user, "regions": regions, "evidence_types": list(EvidenceType)},
    )


@router.post("/badge/resident")
async def apply_resident(
    region_id: Annotated[int, Form()],
    utility_bill: Annotated[UploadFile | None, File()] = None,
    contract: Annotated[UploadFile | None, File()] = None,
    building_cert: Annotated[UploadFile | None, File()] = None,
    geo_selfie: Annotated[UploadFile | None, File()] = None,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    uploads: list[tuple[EvidenceType, UploadFile]] = []
    for kind, upload in (
        (EvidenceType.UTILITY_BILL, utility_bill),
        (EvidenceType.CONTRACT, contract),
        (EvidenceType.BUILDING_CERT, building_cert),
        (EvidenceType.GEO_SELFIE, geo_selfie),
    ):
        if upload is not None and upload.filename:
            uploads.append((kind, upload))

    if not uploads:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "At least one evidence file required")

    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid region")

    # Block duplicate pending
    existing = (
        db.query(BadgeApplication)
        .filter(
            BadgeApplication.user_id == user.id,
            BadgeApplication.status == BadgeApplicationStatus.PENDING,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Pending application exists")

    application = badges.submit_application(
        db,
        user=user,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
    )

    now = datetime.now(UTC)
    try:
        for kind, upload in uploads:
            stored_path = evidence_storage.store(
                application_id=application.id,
                filename=upload.filename or "evidence",
                stream=upload.file,
                now_year=now.year,
                now_month=now.month,
            )
            badges.attach_evidence(
                db,
                application=application,
                evidence_type=kind,
                file_path=stored_path,
            )
    except ValueError as err:
        # Rollback both DB & files
        db.rollback()
        evidence_storage.delete_all_for_application(application.id)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err)) from err

    db.commit()
    return RedirectResponse("/me/badge", status_code=status.HTTP_303_SEE_OTHER)
```

- [ ] **Step 2: 템플릿**

`app/templates/pages/me_badge_resident.html`:

```jinja2
{% extends "base.html" %}
{% block title %}실거주자 인증 신청 · Nestory{% endblock %}
{% block content %}
<section class="mx-auto max-w-2xl p-6 space-y-4">
  <h1 class="text-2xl font-bold">🏡 실거주자 인증 신청</h1>
  <p class="text-sm text-slate-600">최소 1개 증빙 파일이 필요합니다. 모든 파일은 비공개 저장되며 승인 30일 후 자동 삭제됩니다.</p>

  <form method="post" action="/me/badge/resident" enctype="multipart/form-data" class="space-y-4 rounded border p-4">
    <label class="block">
      <span class="text-sm font-medium">시군 선택</span>
      <select name="region_id" required class="mt-1 w-full rounded border p-2">
        <option value="">— 시군 선택 —</option>
        {% for r in regions %}
          <option value="{{ r.id }}">{{ r.sido }} {{ r.sigungu }}</option>
        {% endfor %}
      </select>
    </label>

    <fieldset class="space-y-3">
      <legend class="text-sm font-medium">증빙 파일 (jpg/jpeg/png/pdf/heic, ≤ 10MB)</legend>
      <label class="block">
        <span class="text-sm">전기·수도·가스 고지서 (utility_bill)</span>
        <input type="file" name="utility_bill" accept=".jpg,.jpeg,.png,.pdf,.heic" class="block">
      </label>
      <label class="block">
        <span class="text-sm">매매·건축 계약서 (contract)</span>
        <input type="file" name="contract" accept=".jpg,.jpeg,.png,.pdf,.heic" class="block">
      </label>
      <label class="block">
        <span class="text-sm">건축물대장 (building_cert)</span>
        <input type="file" name="building_cert" accept=".jpg,.jpeg,.png,.pdf,.heic" class="block">
      </label>
      <label class="block">
        <span class="text-sm">집 앞 셀카 + GPS (geo_selfie)</span>
        <input type="file" name="geo_selfie" accept=".jpg,.jpeg,.png,.heic" class="block">
      </label>
    </fieldset>

    <button type="submit" class="rounded bg-emerald-600 text-white px-4 py-2">신청</button>
  </form>
</section>
{% endblock %}
```

- [ ] **Step 3: 테스트 추가**

`app/tests/integration/test_me_badge_routes.py` 끝에 추가:

```python
import io


def test_resident_form_renders(db: Session, client: TestClient) -> None:
    user = _make_user(db)
    client.cookies.set("nestory_session", _login_cookie(user.id))
    r = client.get("/me/badge/resident")
    assert r.status_code == 200
    assert "실거주자 인증" in r.text


def test_resident_apply_with_one_evidence(db: Session, client: TestClient, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("EVIDENCE_BASE_PATH", str(tmp_path / "evidence"))
    from app.config import get_settings
    get_settings.cache_clear()

    user = _make_user(db)
    region = Region(sido="경기", sigungu="양평군", slug="yp-resident")
    db.add(region)
    db.commit()
    client.cookies.set("nestory_session", _login_cookie(user.id))

    files = {"utility_bill": ("bill.jpg", io.BytesIO(b"fake"), "image/jpeg")}
    r = client.post(
        "/me/badge/resident",
        data={"region_id": region.id},
        files=files,
        follow_redirects=False,
    )
    assert r.status_code == 303

    apps = db.query(BadgeApplication).filter_by(user_id=user.id).all()
    assert len(apps) == 1
    assert apps[0].requested_level.value == "resident"
    db.refresh(apps[0])
    assert len(apps[0].__dict__.get("badge_evidence_collection", [])) == 0  # no relationship; check directly
    from app.models import BadgeEvidence
    es = db.query(BadgeEvidence).filter_by(application_id=apps[0].id).all()
    assert len(es) == 1


def test_resident_apply_rejects_no_evidence(db: Session, client: TestClient) -> None:
    user = _make_user(db)
    region = Region(sido="경기", sigungu="양평군", slug="yp-no-ev")
    db.add(region)
    db.commit()
    client.cookies.set("nestory_session", _login_cookie(user.id))
    r = client.post("/me/badge/resident", data={"region_id": region.id})
    assert r.status_code == 400
```

- [ ] **Step 4: 전체 ruff + pytest**
Expected: `120 passed` (117 + 3).

- [ ] **Step 5: Commit**

```bash
git add app/routers/me.py app/templates/pages/me_badge_resident.html app/tests/integration/test_me_badge_routes.py
git commit -m "feat(routes): add resident application with multi-file evidence upload"
```

---

## Task 6: /admin/badge-queue — 신청 목록 + 상세 + 증빙 다운로드

**Files:**
- Create: `app/routers/admin.py`
- Create: `app/templates/pages/admin_badge_queue.html`
- Create: `app/templates/pages/admin_badge_detail.html`
- Modify: `app/main.py` (admin_router 등록)
- Create: `app/tests/integration/test_admin_badge_routes.py`

PRD §4.3 — `/admin/*` 는 🛡 admin 만. 큐 페이지·상세 페이지·증빙 파일 다운로드 라우트.

- [ ] **Step 1: 라우터 작성**

`app/routers/admin.py`:

```python
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session

from app.deps import get_db, require_admin
from app.models import BadgeApplication, BadgeEvidence, Region, User
from app.services import badges
from app.templating import templates

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/badge-queue", response_class=HTMLResponse)
def badge_queue(
    request: Request,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    pending = badges.list_pending(db)
    # eager-load applicant + region for display
    rows = []
    for app_obj in pending:
        applicant = db.get(User, app_obj.user_id)
        region = db.get(Region, app_obj.region_id)
        rows.append({"app": app_obj, "applicant": applicant, "region": region})
    return templates.TemplateResponse(
        request, "pages/admin_badge_queue.html", {"rows": rows}
    )


@router.get("/badge-queue/{application_id}", response_class=HTMLResponse)
def badge_detail(
    request: Request,
    application_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    app_obj = db.get(BadgeApplication, application_id)
    if app_obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    applicant = db.get(User, app_obj.user_id)
    region = db.get(Region, app_obj.region_id)
    evidences = badges.evidences_for(db, app_obj.id)
    return templates.TemplateResponse(
        request,
        "pages/admin_badge_detail.html",
        {
            "app": app_obj,
            "applicant": applicant,
            "region": region,
            "evidences": evidences,
        },
    )


@router.get("/badge-queue/{application_id}/evidence/{evidence_id}")
def download_evidence(
    application_id: int,
    evidence_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> FileResponse:
    e = db.get(BadgeEvidence, evidence_id)
    if e is None or e.application_id != application_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Evidence not found")
    p = Path(e.file_path)
    if not p.exists():
        raise HTTPException(status.HTTP_410_GONE, "Evidence file already cleaned up")
    return FileResponse(path=str(p), filename=p.name)
```

- [ ] **Step 2: 템플릿**

`app/templates/pages/admin_badge_queue.html`:

```jinja2
{% extends "base.html" %}
{% block title %}배지 신청 큐 · 관리자{% endblock %}
{% block content %}
<section class="mx-auto max-w-4xl p-6 space-y-4">
  <h1 class="text-2xl font-bold">🛡 배지 신청 큐</h1>
  <p class="text-sm text-slate-600">대기 중인 신청 {{ rows|length }}건. 오래된 순.</p>
  {% if not rows %}
    <p class="rounded border p-6 text-center text-slate-500">대기 중인 신청이 없습니다.</p>
  {% else %}
    <table class="w-full border-collapse">
      <thead><tr class="bg-slate-100">
        <th class="border p-2 text-left">#</th>
        <th class="border p-2 text-left">신청자</th>
        <th class="border p-2 text-left">레벨</th>
        <th class="border p-2 text-left">시군</th>
        <th class="border p-2 text-left">신청일</th>
        <th class="border p-2"></th>
      </tr></thead>
      <tbody>
      {% for row in rows %}
        <tr>
          <td class="border p-2">{{ row.app.id }}</td>
          <td class="border p-2">@{{ row.applicant.username }}</td>
          <td class="border p-2">{{ row.app.requested_level.value }}</td>
          <td class="border p-2">{{ row.region.sido }} {{ row.region.sigungu }}</td>
          <td class="border p-2">{{ row.app.applied_at.strftime("%Y-%m-%d") }}</td>
          <td class="border p-2"><a href="/admin/badge-queue/{{ row.app.id }}" class="text-emerald-700 underline">상세</a></td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  {% endif %}
</section>
{% endblock %}
```

`app/templates/pages/admin_badge_detail.html`:

```jinja2
{% extends "base.html" %}
{% block title %}신청 #{{ app.id }} · 관리자{% endblock %}
{% block content %}
<section class="mx-auto max-w-2xl p-6 space-y-4">
  <h1 class="text-2xl font-bold">신청 #{{ app.id }}</h1>

  <dl class="grid grid-cols-3 gap-2 rounded border p-4 text-sm">
    <dt class="font-semibold">신청자</dt><dd class="col-span-2">@{{ applicant.username }} · {{ applicant.email }}</dd>
    <dt class="font-semibold">레벨</dt><dd class="col-span-2">{{ app.requested_level.value }}</dd>
    <dt class="font-semibold">시군</dt><dd class="col-span-2">{{ region.sido }} {{ region.sigungu }}</dd>
    <dt class="font-semibold">신청일</dt><dd class="col-span-2">{{ app.applied_at.strftime("%Y-%m-%d %H:%M") }}</dd>
    <dt class="font-semibold">상태</dt><dd class="col-span-2">{{ app.status.value }}</dd>
  </dl>

  <div class="rounded border p-4">
    <h2 class="font-semibold mb-2">증빙 파일 ({{ evidences|length }}건)</h2>
    {% if not evidences %}
      <p class="text-sm text-slate-500">증빙 없음</p>
    {% else %}
      <ul class="space-y-1">
      {% for e in evidences %}
        <li>
          <a href="/admin/badge-queue/{{ app.id }}/evidence/{{ e.id }}" target="_blank" class="text-emerald-700 underline">
            {{ e.evidence_type.value }} 다운로드
          </a>
          <span class="text-xs text-slate-500">({{ e.uploaded_at.strftime("%Y-%m-%d") }})</span>
        </li>
      {% endfor %}
      </ul>
    {% endif %}
  </div>

  {% if app.status.value == "pending" %}
    <div class="grid grid-cols-2 gap-2">
      <form method="post" action="/admin/badge-queue/{{ app.id }}/approve">
        <button type="submit" class="w-full rounded bg-emerald-600 text-white p-2">✓ 승인</button>
      </form>
      <form method="post" action="/admin/badge-queue/{{ app.id }}/reject" class="space-y-1">
        <input type="text" name="note" required placeholder="반려 사유 (필수)" class="w-full rounded border p-2 text-sm">
        <button type="submit" class="w-full rounded bg-red-600 text-white p-2">✗ 반려</button>
      </form>
    </div>
  {% endif %}
</section>
{% endblock %}
```

- [ ] **Step 3: main.py 라우터 등록**

`app/main.py` 에 추가:

```python
from app.routers import admin as admin_router
app.include_router(admin_router.router)
```

- [ ] **Step 4: 통합 테스트**

`app/tests/integration/test_admin_badge_routes.py`:

```python
import io
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from itsdangerous import URLSafeSerializer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BadgeApplication, BadgeEvidence, Region, User
from app.models._enums import (
    BadgeApplicationStatus,
    BadgeRequestedLevel,
    EvidenceType,
)
from app.models.user import UserRole


def _login_cookie(user_id: int) -> str:
    s = URLSafeSerializer(get_settings().app_secret_key, salt="starlette.sessions")
    return s.dumps({"user_id": user_id})


def _make_user(db: Session, *, role: UserRole = UserRole.USER) -> User:
    ts = int(datetime.now(UTC).timestamp() * 1_000_000)
    u = User(
        email=f"t{ts}@example.com",
        username=f"u{ts}",
        display_name="테스터",
        password_hash="x",
        role=role,
    )
    db.add(u)
    db.flush()
    db.commit()
    return u


def test_queue_requires_admin(db: Session, client: TestClient) -> None:
    user = _make_user(db, role=UserRole.USER)
    client.cookies.set("nestory_session", _login_cookie(user.id))
    assert client.get("/admin/badge-queue").status_code == 403


def test_queue_lists_pending(db: Session, client: TestClient) -> None:
    admin = _make_user(db, role=UserRole.ADMIN)
    applicant = _make_user(db, role=UserRole.USER)
    region = Region(sido="경기", sigungu="양평군", slug="yp-q")
    db.add(region)
    db.commit()
    db.add(
        BadgeApplication(
            user_id=applicant.id,
            requested_level=BadgeRequestedLevel.RESIDENT,
            region_id=region.id,
        )
    )
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.get("/admin/badge-queue")
    assert r.status_code == 200
    assert "@" + applicant.username in r.text


def test_detail_shows_application(db: Session, client: TestClient) -> None:
    admin = _make_user(db, role=UserRole.ADMIN)
    applicant = _make_user(db, role=UserRole.USER)
    region = Region(sido="경기", sigungu="양평군", slug="yp-d")
    db.add(region)
    db.commit()
    app_obj = BadgeApplication(
        user_id=applicant.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
    )
    db.add(app_obj)
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.get(f"/admin/badge-queue/{app_obj.id}")
    assert r.status_code == 200
    assert "양평군" in r.text


def test_evidence_download_returns_file(db: Session, client: TestClient, tmp_path) -> None:
    admin = _make_user(db, role=UserRole.ADMIN)
    applicant = _make_user(db, role=UserRole.USER)
    region = Region(sido="경기", sigungu="양평군", slug="yp-e")
    db.add(region)
    db.commit()
    app_obj = BadgeApplication(
        user_id=applicant.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
    )
    db.add(app_obj)
    db.commit()

    # Create real file
    f = tmp_path / "ev.jpg"
    f.write_bytes(b"sample")
    e = BadgeEvidence(
        application_id=app_obj.id,
        evidence_type=EvidenceType.UTILITY_BILL,
        file_path=str(f),
    )
    db.add(e)
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.get(f"/admin/badge-queue/{app_obj.id}/evidence/{e.id}")
    assert r.status_code == 200
    assert r.content == b"sample"


def test_evidence_download_404_for_other_app(db: Session, client: TestClient) -> None:
    admin = _make_user(db, role=UserRole.ADMIN)
    applicant = _make_user(db, role=UserRole.USER)
    region = Region(sido="경기", sigungu="양평군", slug="yp-x")
    db.add(region)
    db.commit()
    app1 = BadgeApplication(user_id=applicant.id, requested_level=BadgeRequestedLevel.RESIDENT, region_id=region.id)
    app2 = BadgeApplication(user_id=applicant.id, requested_level=BadgeRequestedLevel.REGION_VERIFIED, region_id=region.id)
    db.add_all([app1, app2])
    db.commit()
    e = BadgeEvidence(application_id=app1.id, evidence_type=EvidenceType.UTILITY_BILL, file_path="/nope")
    db.add(e)
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(admin.id))
    # Try downloading via wrong app id
    r = client.get(f"/admin/badge-queue/{app2.id}/evidence/{e.id}")
    assert r.status_code == 404
```

- [ ] **Step 5: 전체 ruff + pytest**
Expected: `125 passed` (120 + 5).

- [ ] **Step 6: Commit**

```bash
git add app/routers/admin.py app/templates/pages/admin_badge_queue.html app/templates/pages/admin_badge_detail.html app/main.py app/tests/integration/test_admin_badge_routes.py
git commit -m "feat(routes): add /admin/badge-queue list, detail, and evidence download"
```

---

## Task 7: 승인·반려 처리 + evidence_cleanup 잡 enqueue

**Files:**
- Modify: `app/routers/admin.py` (+ approve/reject POST)
- Modify: `app/tests/integration/test_admin_badge_routes.py` (+ tests)

PRD §5.4 + §6.7 — 승인·반려 시 services/badges 호출 + evidence_cleanup 잡 enqueue (승인은 30일 후, 반려는 즉시).

- [ ] **Step 1: 승인·반려 라우트 추가**

`app/routers/admin.py` 끝에 추가:

```python
from datetime import UTC, datetime, timedelta

from fastapi import Form
from fastapi.responses import RedirectResponse

from app.models._enums import JobKind
from app.workers import queue


EVIDENCE_RETENTION_DAYS = 30


@router.post("/badge-queue/{application_id}/approve")
def approve_application(
    application_id: int,
    note: str | None = Form(default=None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    app_obj = db.get(BadgeApplication, application_id)
    if app_obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    try:
        badges.approve(db, application=app_obj, reviewer=admin, note=note)
    except ValueError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err)) from err

    # Schedule evidence cleanup 30 days out
    queue.enqueue(
        db,
        JobKind.EVIDENCE_CLEANUP,
        {"application_id": app_obj.id},
        run_after=datetime.now(UTC) + timedelta(days=EVIDENCE_RETENTION_DAYS),
    )
    db.commit()
    return RedirectResponse("/admin/badge-queue", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/badge-queue/{application_id}/reject")
def reject_application(
    application_id: int,
    note: str = Form(...),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    app_obj = db.get(BadgeApplication, application_id)
    if app_obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    try:
        badges.reject(db, application=app_obj, reviewer=admin, note=note)
    except ValueError as err:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(err)) from err

    # Immediate evidence cleanup
    queue.enqueue(db, JobKind.EVIDENCE_CLEANUP, {"application_id": app_obj.id})
    db.commit()
    return RedirectResponse("/admin/badge-queue", status_code=status.HTTP_303_SEE_OTHER)
```

- [ ] **Step 2: 테스트 추가**

`app/tests/integration/test_admin_badge_routes.py` 끝에 추가:

```python
from datetime import UTC, datetime, timedelta

from app.models import Job
from app.models._enums import JobKind, JobStatus
from app.models.user import BadgeLevel


def test_approve_promotes_user_and_schedules_cleanup(db: Session, client: TestClient) -> None:
    admin = _make_user(db, role=UserRole.ADMIN)
    applicant = _make_user(db, role=UserRole.USER)
    region = Region(sido="경기", sigungu="양평군", slug="yp-app")
    db.add(region)
    db.commit()
    app_obj = BadgeApplication(
        user_id=applicant.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
    )
    db.add(app_obj)
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.post(
        f"/admin/badge-queue/{app_obj.id}/approve",
        data={"note": "확인 완료"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    db.refresh(applicant)
    assert applicant.badge_level == BadgeLevel.RESIDENT

    db.refresh(app_obj)
    assert app_obj.status == BadgeApplicationStatus.APPROVED

    job = db.query(Job).filter_by(kind=JobKind.EVIDENCE_CLEANUP).first()
    assert job is not None
    assert job.payload == {"application_id": app_obj.id}
    assert job.status == JobStatus.QUEUED
    # run_after ~30 days from now
    delta = job.run_after - datetime.now(UTC)
    assert timedelta(days=29) < delta < timedelta(days=31)


def test_reject_keeps_user_and_immediate_cleanup(db: Session, client: TestClient) -> None:
    admin = _make_user(db, role=UserRole.ADMIN)
    applicant = _make_user(db, role=UserRole.USER)
    region = Region(sido="경기", sigungu="양평군", slug="yp-rej")
    db.add(region)
    db.commit()
    app_obj = BadgeApplication(
        user_id=applicant.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
    )
    db.add(app_obj)
    db.commit()

    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.post(
        f"/admin/badge-queue/{app_obj.id}/reject",
        data={"note": "증빙 불충분"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    db.refresh(applicant)
    assert applicant.badge_level == BadgeLevel.INTERESTED  # unchanged
    db.refresh(app_obj)
    assert app_obj.status == BadgeApplicationStatus.REJECTED

    job = db.query(Job).filter_by(kind=JobKind.EVIDENCE_CLEANUP).first()
    assert job is not None
    # immediate (run_after in the past or near now)
    assert job.run_after <= datetime.now(UTC) + timedelta(seconds=2)


def test_approve_already_approved_returns_400(db: Session, client: TestClient) -> None:
    admin = _make_user(db, role=UserRole.ADMIN)
    applicant = _make_user(db, role=UserRole.USER)
    region = Region(sido="경기", sigungu="양평군", slug="yp-twice")
    db.add(region)
    db.commit()
    app_obj = BadgeApplication(
        user_id=applicant.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
        status=BadgeApplicationStatus.APPROVED,
    )
    db.add(app_obj)
    db.commit()
    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.post(f"/admin/badge-queue/{app_obj.id}/approve")
    assert r.status_code == 400
```

- [ ] **Step 3: 전체 ruff + pytest**
Expected: `128 passed` (125 + 3).

- [ ] **Step 4: Commit**

```bash
git add app/routers/admin.py app/tests/integration/test_admin_badge_routes.py
git commit -m "feat(routes): admin approve/reject with audit, notification, and cleanup scheduling"
```

---

## Task 8: workers/handlers/evidence_cleanup.py — 30일 자동 삭제 핸들러

**Files:**
- Create: `app/workers/handlers/evidence_cleanup.py`
- Modify: `app/workers/handlers/__init__.py` (import_handlers 에 evidence_cleanup 추가)
- Create: `app/tests/integration/test_evidence_cleanup_handler.py`

PRD §6.7 + §8.1 — 승인·반려 시 enqueue 된 EVIDENCE_CLEANUP 잡이 실행되면 BadgeEvidence 행과 실제 파일 삭제. application_id 가 payload.

- [ ] **Step 1: 핸들러 작성**

`app/workers/handlers/evidence_cleanup.py`:

```python
"""evidence_cleanup handler — delete evidence files + DB rows for a given application_id.

Triggered:
- 30 days after approve (PRD §8.1: 승인 30일 후 자동 삭제)
- Immediately after reject

Payload: {"application_id": int}
"""
from typing import Any

import structlog

from app.db.session import SessionLocal
from app.models import BadgeEvidence
from app.models._enums import JobKind
from app.services import evidence_storage
from app.workers.handlers import register

log = structlog.get_logger(__name__)


@register(JobKind.EVIDENCE_CLEANUP)
def handle_evidence_cleanup(payload: dict[str, Any]) -> None:
    application_id = payload.get("application_id")
    if not isinstance(application_id, int):
        raise ValueError(f"application_id required in payload, got {payload!r}")

    with SessionLocal() as db:
        evidences = (
            db.query(BadgeEvidence).filter_by(application_id=application_id).all()
        )
        rows_deleted = 0
        for e in evidences:
            db.delete(e)
            rows_deleted += 1
        files_deleted = evidence_storage.delete_all_for_application(application_id)
        db.commit()

    log.info(
        "handler.evidence_cleanup.done",
        application_id=application_id,
        rows_deleted=rows_deleted,
        files_deleted=files_deleted,
    )
```

- [ ] **Step 2: 핸들러 레지스트리 갱신**

`app/workers/handlers/__init__.py` 의 `import_handlers()` 함수 본문 import 라인에 `evidence_cleanup` 추가:

```python
def import_handlers() -> None:
    from app.workers.handlers import (  # noqa: F401
        evidence_cleanup,
        image_resize,
        notification,
    )
```

- [ ] **Step 3: 테스트**

`app/tests/integration/test_evidence_cleanup_handler.py`:

```python
import io
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BadgeApplication, BadgeEvidence, Region, User
from app.models._enums import (
    BadgeRequestedLevel,
    EvidenceType,
)
from app.services import evidence_storage
from app.workers.handlers import dispatch, import_handlers
from app.workers.handlers.evidence_cleanup import handle_evidence_cleanup


@pytest.fixture(autouse=True)
def _isolate_evidence_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDENCE_BASE_PATH", str(tmp_path / "evidence"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _make_application_with_files(db: Session) -> int:
    ts = int(datetime.now(UTC).timestamp() * 1_000_000)
    user = User(email=f"t{ts}@x.com", username=f"u{ts}", display_name="t", password_hash="x")
    region = Region(sido="경기", sigungu="양평군", slug=f"yp-{ts}")
    db.add_all([user, region])
    db.flush()
    app_obj = BadgeApplication(
        user_id=user.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=region.id,
    )
    db.add(app_obj)
    db.flush()

    # Real files
    p1 = evidence_storage.store(
        application_id=app_obj.id,
        filename="bill.jpg",
        stream=io.BytesIO(b"a"),
        now_year=2026,
        now_month=5,
    )
    p2 = evidence_storage.store(
        application_id=app_obj.id,
        filename="contract.pdf",
        stream=io.BytesIO(b"b"),
        now_year=2026,
        now_month=5,
    )
    db.add_all([
        BadgeEvidence(application_id=app_obj.id, evidence_type=EvidenceType.UTILITY_BILL, file_path=p1),
        BadgeEvidence(application_id=app_obj.id, evidence_type=EvidenceType.CONTRACT, file_path=p2),
    ])
    db.commit()
    return app_obj.id


def test_handler_deletes_files_and_rows(db: Session) -> None:
    app_id = _make_application_with_files(db)
    handle_evidence_cleanup({"application_id": app_id})
    db.expire_all()
    remaining = db.query(BadgeEvidence).filter_by(application_id=app_id).all()
    assert remaining == []


def test_handler_idempotent(db: Session) -> None:
    app_id = _make_application_with_files(db)
    handle_evidence_cleanup({"application_id": app_id})
    # Second call should not raise — files+rows already gone
    handle_evidence_cleanup({"application_id": app_id})


def test_handler_invalid_payload() -> None:
    with pytest.raises(ValueError, match="application_id required"):
        handle_evidence_cleanup({})


def test_dispatch_via_registry(db: Session) -> None:
    import_handlers()
    app_id = _make_application_with_files(db)
    from app.models._enums import JobKind
    dispatch(JobKind.EVIDENCE_CLEANUP, {"application_id": app_id})
    db.expire_all()
    assert db.query(BadgeEvidence).filter_by(application_id=app_id).count() == 0
```

- [ ] **Step 4: 전체 ruff + pytest**
Expected: `132 passed` (128 + 4).

- [ ] **Step 5: Commit**

```bash
git add app/workers/handlers/evidence_cleanup.py app/workers/handlers/__init__.py app/tests/integration/test_evidence_cleanup_handler.py
git commit -m "feat(workers): add evidence_cleanup handler with file+row deletion and idempotency"
```

---

## Task 9: 홈 nav 갱신 + e2e 통합 — 배지 워크플로우

**Files:**
- Modify: `app/templates/components/nav.html` (배지 링크 추가)
- Modify: `app/templates/pages/home.html` (admin 사용자에게 큐 링크 노출)
- Create: `app/tests/integration/test_badge_workflow_e2e.py`

전체 흐름이 한번의 시나리오로 작동하는지 검증 — 가입 → region 신청 → 관리자 승인 → resident 신청(증빙 업로드) → 관리자 승인 → User.badge_level=RESIDENT → cleanup 잡 dispatch → 파일·행 삭제.

- [ ] **Step 1: nav 컴포넌트 갱신**

`app/templates/components/nav.html` 의 로그인 사용자 영역에 배지 링크 추가. 기존 nav 구조에 따라 적절한 위치(예: `{% if request.session.user_id %}` 블록):

```jinja2
{# 기존 사용자 nav 안에서 #}
<a href="/me/badge" class="...">내 배지</a>
{% if user.role.value == "admin" %}
  <a href="/admin/badge-queue" class="...">배지 큐</a>
{% endif %}
```

> 실제 nav.html 의 구조를 보고 적절한 위치에 삽입. context processor 가 user 를 노출 안 한다면 request.session 으로 user_id 만 확인 후 router 에서 user 를 template context로 전달.

- [ ] **Step 2: e2e 테스트**

`app/tests/integration/test_badge_workflow_e2e.py`:

```python
import io
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from itsdangerous import URLSafeSerializer
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BadgeApplication, BadgeEvidence, Region, User
from app.models._enums import BadgeApplicationStatus, JobKind
from app.models.user import BadgeLevel, UserRole
from app.workers.handlers import dispatch, import_handlers


@pytest.fixture(autouse=True)
def _isolate_evidence_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDENCE_BASE_PATH", str(tmp_path / "evidence"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _login_cookie(user_id: int) -> str:
    s = URLSafeSerializer(get_settings().app_secret_key, salt="starlette.sessions")
    return s.dumps({"user_id": user_id})


def test_full_badge_workflow(db: Session, client: TestClient) -> None:
    # Seed admin + region
    ts = int(datetime.now(UTC).timestamp() * 1_000_000)
    admin = User(
        email=f"adm{ts}@x.com",
        username=f"adm{ts}",
        display_name="관리자",
        password_hash="x",
        role=UserRole.ADMIN,
    )
    region = Region(sido="경기", sigungu="양평군", slug=f"yp-e2e-{ts}")
    db.add_all([admin, region])
    db.commit()

    # User signup via auth route
    resp = client.post(
        "/auth/signup",
        data={
            "email": f"u{ts}@x.com",
            "username": f"u{ts}",
            "display_name": "신청자",
            "password": "Password!123",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    user = db.query(User).filter_by(email=f"u{ts}@x.com").one()
    assert user.badge_level == BadgeLevel.INTERESTED

    # Step 1: user applies for resident with evidence
    client.cookies.set("nestory_session", _login_cookie(user.id))
    r = client.post(
        "/me/badge/resident",
        data={"region_id": region.id},
        files={"utility_bill": ("bill.jpg", io.BytesIO(b"fake-evidence"), "image/jpeg")},
        follow_redirects=False,
    )
    assert r.status_code == 303
    app_obj = db.query(BadgeApplication).filter_by(user_id=user.id).one()
    assert app_obj.status == BadgeApplicationStatus.PENDING
    evidences = db.query(BadgeEvidence).filter_by(application_id=app_obj.id).all()
    assert len(evidences) == 1

    # Step 2: admin approves
    client.cookies.set("nestory_session", _login_cookie(admin.id))
    r = client.post(
        f"/admin/badge-queue/{app_obj.id}/approve",
        data={"note": "OK"},
        follow_redirects=False,
    )
    assert r.status_code == 303

    db.refresh(user)
    db.refresh(app_obj)
    assert user.badge_level == BadgeLevel.RESIDENT
    assert user.primary_region_id == region.id
    assert app_obj.status == BadgeApplicationStatus.APPROVED

    # Step 3: simulate worker dispatching the cleanup job
    import_handlers()
    dispatch(JobKind.EVIDENCE_CLEANUP, {"application_id": app_obj.id})
    db.expire_all()

    assert db.query(BadgeEvidence).filter_by(application_id=app_obj.id).count() == 0
```

- [ ] **Step 3: 전체 ruff + pytest**
Expected: `133 passed` (132 + 1).

- [ ] **Step 4: Commit**

```bash
git add app/templates/components/nav.html app/templates/pages/home.html app/tests/integration/test_badge_workflow_e2e.py
git commit -m "feat(ui): add badge nav links and full e2e workflow test"
```

---

## Self-Review (작성 후 점검)

### 1. Spec coverage

| PRD 항목 | Task |
|---|---|
| §2.2 권한 매트릭스 (require_login·badge·admin) | Task 1 |
| §4.3 권한 매트릭스 (페이지 단위) | Task 1·4·6 |
| §5.4 배지 상태 머신 (전이 함수) | Task 2 |
| §5.5 증빙 4종 + 비공개 저장소 | Task 3·5 |
| §6.2 deps.py 표준 가드 | Task 1 |
| §6.4 증빙 파일 path 레이아웃 | Task 3 |
| §6.7 EVIDENCE_CLEANUP 잡 | Task 7·8 |
| §8.1 30일 자동 삭제 | Task 7·8 |
| §1.5.4 Pillar V `require_resident_in_region` | Task 1 |
| §5.4.1 ex_resident 가드 차단 | Task 1 (`_BADGE_RANK[EX_RESIDENT] = -1`) |

PRD §5.4.1의 재검증 자동 일배치(연 1회)는 P1.2 범위 외 — Phase 2 maintenance 잡으로 deferred.

### 2. Placeholder scan

- 모든 step에 실제 코드·명령·기대 출력 포함
- "TBD"·"TODO"·"...similar" 없음
- 각 task 5–6 step 동일 골격

### 3. 타입·이름 일관성

- 가드 이름: `require_user`·`require_admin`·`require_badge`·`require_resident_in_region` — Task 1 정의를 후속 task에서 동일 import
- enum: `_enums.BadgeRequestedLevel`·`BadgeApplicationStatus`·`EvidenceType`·`JobKind` 일관 사용
- 라우트 prefix: `/me`·`/admin` 일관
- 템플릿 위치: `pages/me_badge.html`·`pages/admin_badge_queue.html`·`pages/admin_badge_detail.html` 일관

### 4. 잠정 가정 검증 시점

- OI-3 (증빙 4종): Task 5에서 4종 다 포함 — Phase 1 말 OI-3 결정 시 삭제·추가는 enum + 폼 input 만 수정
- 30일 보존: `EVIDENCE_RETENTION_DAYS` 상수로 admin.py 에 분리 — 변경 용이

### 5. P1.3 진입점

- 라우트 + 폼 + 템플릿 패턴 확립 → P1.3 의 `/write/review`·`/write/plan` 도 동일 패턴 따라가면 됨
- 이미지 업로드 path는 evidence_storage 에서 구현됐지만 EXIF 제거·리사이즈는 P1.3 image pipeline 에서 추가 (별 모듈)
- HTMX 도입은 P1.3에서 — 댓글·좋아요·스크랩이 첫 사용 사례

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-06-nestory-phase1-2-badge-system-and-guards.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — 각 Task를 fresh subagent로 dispatch, Task 사이에 spec+quality 리뷰. 메인 컨텍스트 보호·빠른 반복.

**2. Inline Execution** — 이 세션에서 executing-plans 스킬로 batch 실행 + 체크포인트.

**Which approach?**
