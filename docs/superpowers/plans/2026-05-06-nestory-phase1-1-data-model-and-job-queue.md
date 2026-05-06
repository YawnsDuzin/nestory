# Nestory Phase 1.1 — Data Model + Job Queue Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 1 본격 시작 전 모든 도메인 모델 (Post·Journey·badge·post_validations·user_interest_regions·images·comments·tags·라이트 상호작용·notifications·reports·audit·announcements)과 PostgreSQL 기반 영속화 작업 큐(`jobs` 테이블 + LISTEN/NOTIFY 워커)를 한 번에 정착시킨다. 종료 시 후속 sub-plan(P1.2~P1.5)이 즉시 라우트·UI 작업에만 집중할 수 있다.

**Architecture:** SQLAlchemy 2.x `Mapped[T]` + `mapped_column(...)` 스타일을 Phase 0의 user/region 모델과 동일하게 유지. PostgreSQL 16 enum은 `values_callable=lambda x: [e.value for e in x]` 패턴으로 SQLAlchemy enum과 PG 값 매칭. JSONB `metadata` 는 Pydantic Discriminated Union (`extra='forbid'`)으로 검증. 작업 큐는 `SELECT ... FOR UPDATE SKIP LOCKED` + `LISTEN/NOTIFY` + 폴링 fallback을 단일 워커 프로세스(`app.workers.runner`)로 구동. systemd `nestory-worker.service` 별도 unit.

**Tech Stack:** Python 3.12, SQLAlchemy 2.x + Alembic, psycopg 3 (`LISTEN/NOTIFY`·`notifies()` API), PostgreSQL 16 (JSONB·enum·SKIP LOCKED·advisory locks), Pydantic v2 (Discriminated Union), pytest + factory-boy, structlog, systemd.

---

## P1.1 잠정 가정 (sub-plan 내 확정 필요)

이 계획은 아래 기본값을 **잠정 가정**으로 진행한다. P1.1 종료 전 재확인하고, 최종 결정과 다르면 해당 태스크 결과물을 조정한다.

| OI | 잠정 가정 | 영향 범위 |
|---|---|---|
| OI-3 | 증빙 파일 유형 4종 모두 (`utility_bill`·`contract`·`building_cert`·`geo_selfie`) — enum만 정의, 허용 조합 결정은 P1.2 | Task 12 |
| OI-11 | Post.metadata 템플릿 v1 = PRD §5.3.1/5.3.2 정의 — 파일럿 거주자 인터뷰는 Phase 1 말 OI-11 결정에서 추가 필드 보강 | Task 7 |
| OI-16 | post_validations 어뷰징 방어 N (시군 거주자 임계값) — 모델만 정의, 실제 메트릭 노출 로직은 P1.2/P1.3 | Task 8 |

---

## 파일 구조 개요

P1.1 종료 시 저장소에 추가/변경되는 파일:

```
nestory/
├── app/
│   ├── models/
│   │   ├── __init__.py                      # 갱신 (모든 신규 모델 re-export)
│   │   ├── _enums.py                        # 신규: 도메인 enum 모음
│   │   ├── user.py                          # 갱신: ex_resident enum 확장 + 신규 컬럼
│   │   ├── region.py                        # (Phase 0, 변경 없음)
│   │   ├── interest_region.py               # 신규
│   │   ├── image.py                         # 신규
│   │   ├── journey.py                       # 신규
│   │   ├── post.py                          # 신규
│   │   ├── post_validation.py               # 신규
│   │   ├── comment.py                       # 신규
│   │   ├── tag.py                           # 신규 (tags + post_tags)
│   │   ├── interaction.py                   # 신규 (post_likes, post_scraps, user_follows, journey_follows)
│   │   ├── badge_application.py             # 신규 (badge_applications + badge_evidence)
│   │   ├── notification.py                  # 신규
│   │   ├── moderation.py                    # 신규 (report + audit_log + announcement)
│   │   └── job.py                           # 신규
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── post_metadata.py                 # 신규: Pydantic Discriminated Union
│   │
│   ├── workers/
│   │   ├── __init__.py                      # 신규
│   │   ├── queue.py                         # 신규: enqueue/dequeue/mark_*/retry
│   │   ├── runner.py                        # 신규: 메인 루프 + LISTEN/NOTIFY + signal
│   │   └── handlers/
│   │       ├── __init__.py                  # 신규: 레지스트리 + dispatch
│   │       ├── image_resize.py              # 신규: P1.3 stub
│   │       └── notification.py              # 신규: P1.5 stub
│   │
│   ├── tests/
│   │   ├── conftest.py                      # 갱신: 자동 TRUNCATE (모든 테이블 동적)
│   │   ├── factories/                       # 신규
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── region.py
│   │   │   ├── post.py
│   │   │   └── job.py
│   │   ├── integration/
│   │   │   ├── test_user_model.py           # 갱신 (ex_resident 등)
│   │   │   ├── test_image_model.py          # 신규
│   │   │   ├── test_journey_model.py        # 신규
│   │   │   ├── test_post_model.py           # 신규
│   │   │   ├── test_post_metadata_schema.py # 신규
│   │   │   ├── test_post_validation_model.py
│   │   │   ├── test_comment_model.py
│   │   │   ├── test_tag_model.py
│   │   │   ├── test_interaction_model.py
│   │   │   ├── test_badge_application_model.py
│   │   │   ├── test_notification_model.py
│   │   │   ├── test_moderation_model.py
│   │   │   ├── test_job_model.py
│   │   │   ├── test_job_queue.py            # queue.py enqueue/dequeue
│   │   │   └── test_worker_e2e.py           # runner round-trip
│   │
│   └── db/migrations/versions/              # ~10개 신규 revision 파일 (Task별 1개)
│
├── deploy/
│   └── systemd/
│       └── nestory-worker.service           # 신규
│
├── docker-compose.test.yml                  # 갱신: worker 서비스 추가
├── docker-compose.local.yml                 # 갱신: worker 서비스 추가 (선택)
└── pyproject.toml                           # (변경 없음 — 기존 의존성 충분)
```

---

## Task 1: 공통 enum 모음 + conftest 자동 TRUNCATE

**Files:**
- Create: `app/models/_enums.py`
- Modify: `app/tests/conftest.py:17-23`

P1.1 전체에서 사용할 도메인 enum을 한 모듈에 모은다. 또한 conftest의 TRUNCATE 픽스처를 하드코딩된 `users, regions` 에서 SQLAlchemy 메타데이터로부터 모든 테이블을 동적으로 수집하도록 개선 (핸드오프 메모의 "테스트 TRUNCATE 자동화" 기술 부채 해결). 이렇게 하면 후속 Task에서 conftest 수정 없이 모델만 추가하면 된다.

- [ ] **Step 1: enum 모음 모듈 작성**

`app/models/_enums.py`:

```python
import enum


class PostType(str, enum.Enum):
    REVIEW = "review"
    JOURNEY_EPISODE = "journey_episode"
    QUESTION = "question"
    ANSWER = "answer"
    PLAN = "plan"


class PostStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    HIDDEN = "hidden"


class JourneyStatus(str, enum.Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class CommentStatus(str, enum.Enum):
    VISIBLE = "visible"
    HIDDEN = "hidden"


class ImageStatus(str, enum.Enum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class BadgeApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class BadgeRequestedLevel(str, enum.Enum):
    REGION_VERIFIED = "region_verified"
    RESIDENT = "resident"


class EvidenceType(str, enum.Enum):
    UTILITY_BILL = "utility_bill"
    CONTRACT = "contract"
    BUILDING_CERT = "building_cert"
    GEO_SELFIE = "geo_selfie"


class ValidationVote(str, enum.Enum):
    CONFIRM = "confirm"
    DISPUTE = "dispute"


class NotificationType(str, enum.Enum):
    BADGE_APPROVED = "badge_approved"
    BADGE_REJECTED = "badge_rejected"
    POST_COMMENT = "post_comment"
    POST_LIKED = "post_liked"
    JOURNEY_NEW_EPISODE = "journey_new_episode"
    QUESTION_ANSWERED = "question_answered"
    REVALIDATION_PROMPT = "revalidation_prompt"
    TIMELAPSE_REMIND = "timelapse_remind"
    SYSTEM = "system"


class ReportReason(str, enum.Enum):
    SPAM = "spam"
    AD = "ad"
    OFFENSIVE = "offensive"
    PRIVACY = "privacy"
    PEER_DISPUTE = "peer_dispute"
    OTHER = "other"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class AuditAction(str, enum.Enum):
    BADGE_APPROVED = "badge_approved"
    BADGE_REJECTED = "badge_rejected"
    CONTENT_HIDDEN = "content_hidden"
    USER_BANNED = "user_banned"
    REPORT_RESOLVED = "report_resolved"
    ANNOUNCEMENT_PUBLISHED = "announcement_published"


class JobKind(str, enum.Enum):
    IMAGE_RESIZE = "image_resize"
    NOTIFICATION = "notification"
    REVALIDATION_CHECK = "revalidation_check"
    TIMELAPSE_REMIND = "timelapse_remind"
    EVIDENCE_CLEANUP = "evidence_cleanup"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DEAD = "dead"
```

- [ ] **Step 2: conftest 자동 TRUNCATE 픽스처 갱신**

`app/tests/conftest.py:17-23` 의 `_cleanup_db` 픽스처를 다음으로 교체:

```python
@pytest.fixture(autouse=True)
def _cleanup_db():
    """모든 테스트 후 모든 테이블 TRUNCATE. SQLAlchemy 메타데이터 기반 동적 수집."""
    yield
    from app.db.base import Base
    table_names = [t.name for t in Base.metadata.sorted_tables if t.name != "alembic_version"]
    if not table_names:
        return
    with SessionLocal() as session:
        joined = ", ".join(table_names)
        session.execute(text(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE"))
        session.commit()
```

또한 `app/tests/conftest.py` 상단 import 직전에 모델 모듈을 import 해서 메타데이터를 등록한다 (이는 Task 20 까지 추가됨에 따라 갱신될 수 있음 — 일단 Phase 0 모델만 import):

```python
import app.models  # noqa: F401  # Base.metadata에 모든 모델 등록
```

- [ ] **Step 3: ruff + 기존 테스트 통과 확인**

Run: `ruff check app/ && pytest app/tests/ -q`
Expected: 38 passed (Phase 0 baseline 유지). _enums.py는 아직 import 안 됨 → 사용 안 됨 → ruff 통과.

- [ ] **Step 4: Commit**

```bash
git add app/models/_enums.py app/tests/conftest.py
git commit -m "feat(models): add domain enum module and dynamic test truncate fixture"
```

---

## Task 2: User 모델 v1.1 갱신 (ex_resident · 재검증 컬럼 · anonymized_at)

**Files:**
- Modify: `app/models/user.py`
- Create: `app/db/migrations/versions/<rev>_user_v1_1_columns.py` (Alembic autogenerate)
- Modify: `app/tests/integration/test_user_model.py`

PRD §5.1 v1.1 — `BadgeLevel` enum에 `EX_RESIDENT` 추가, `resident_revalidated_at`·`ex_resident_at`·`anonymized_at` 컬럼 추가. 기존 enum 변경(추가)은 Postgres에서 `ALTER TYPE ... ADD VALUE` 로 처리.

- [ ] **Step 1: User 모델 갱신**

`app/models/user.py` 의 `BadgeLevel` enum에 `EX_RESIDENT` 추가, User 클래스에 컬럼 3개 추가:

```python
class BadgeLevel(str, enum.Enum):
    INTERESTED = "interested"
    REGION_VERIFIED = "region_verified"
    RESIDENT = "resident"
    EX_RESIDENT = "ex_resident"


class User(Base):
    # ... 기존 필드 유지 ...
    resident_revalidated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ex_resident_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    anonymized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

- [ ] **Step 2: Alembic 마이그레이션 생성·수동 보강**

Run: `alembic revision --autogenerate -m "user v1.1 columns"`

생성된 파일을 열고 `upgrade()` 시작에 enum value 추가를 명시 (autogenerate가 enum 추가를 항상 잡지 못함):

```python
def upgrade() -> None:
    op.execute("ALTER TYPE badge_level ADD VALUE IF NOT EXISTS 'ex_resident'")
    op.add_column("users", sa.Column("resident_revalidated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("ex_resident_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "anonymized_at")
    op.drop_column("users", "ex_resident_at")
    op.drop_column("users", "resident_revalidated_at")
    # enum value 제거는 PG에서 비표준 — downgrade 생략 (P1.1 한정)
```

- [ ] **Step 3: 마이그레이션 적용 + 테스트**

Run: `alembic upgrade head`
Expected: revision applied without error.

`app/tests/integration/test_user_model.py` 끝에 추가:

```python
def test_user_v1_1_columns_default_null(db: Session) -> None:
    user = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    db.add(user)
    db.flush()
    assert user.resident_revalidated_at is None
    assert user.ex_resident_at is None
    assert user.anonymized_at is None


def test_user_can_be_set_to_ex_resident(db: Session) -> None:
    user = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
        badge_level=BadgeLevel.EX_RESIDENT,
        ex_resident_at=datetime.now(UTC),
    )
    db.add(user)
    db.flush()
    assert user.badge_level == BadgeLevel.EX_RESIDENT
```

Run: `pytest app/tests/integration/test_user_model.py -v`
Expected: 3 passed (1 existing + 2 new).

- [ ] **Step 4: ruff + 전체 pytest 통과 확인**

Run: `ruff check app/ && pytest app/tests/ -q`

- [ ] **Step 5: Commit**

```bash
git add app/models/user.py app/db/migrations/versions/ app/tests/integration/test_user_model.py
git commit -m "feat(models): add ex_resident state and revalidation/anonymized columns to User"
```

---

## Task 3: user_interest_regions 테이블 (B5)

**Files:**
- Create: `app/models/interest_region.py`
- Modify: `app/models/__init__.py`
- Create: `app/db/migrations/versions/<rev>_add_user_interest_regions.py`
- Create: `app/tests/integration/test_interest_region_model.py`

PRD §5.1 v1.1 — Match Wizard 결과 저장 + 다중 관심 시군 알림용 M:N 테이블.

- [ ] **Step 1: 모델 작성**

`app/models/interest_region.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, PrimaryKeyConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserInterestRegion(Base):
    __tablename__ = "user_interest_regions"
    __table_args__ = (PrimaryKeyConstraint("user_id", "region_id"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="CASCADE"), index=True)
    priority: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

`app/models/__init__.py` 갱신:

```python
from app.models.interest_region import UserInterestRegion
from app.models.region import Region
from app.models.user import BadgeLevel, User, UserRole

__all__ = ["BadgeLevel", "Region", "User", "UserInterestRegion", "UserRole"]
```

- [ ] **Step 2: Alembic 마이그레이션 + upgrade**

Run: `alembic revision --autogenerate -m "add user_interest_regions"` → `alembic upgrade head`

- [ ] **Step 3: 통합 테스트**

`app/tests/integration/test_interest_region_model.py`:

```python
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Region, User, UserInterestRegion


def _make_user(db: Session) -> User:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    db.add(u)
    db.flush()
    return u


def _make_region(db: Session, slug: str) -> Region:
    r = Region(sido="경기", sigungu="양평군", slug=slug)
    db.add(r)
    db.flush()
    return r


def test_user_can_have_multiple_interest_regions(db: Session) -> None:
    u = _make_user(db)
    r1 = _make_region(db, "yangpyeong-test")
    r2 = _make_region(db, "gapyeong-test")
    db.add(UserInterestRegion(user_id=u.id, region_id=r1.id, priority=1))
    db.add(UserInterestRegion(user_id=u.id, region_id=r2.id, priority=2))
    db.flush()

    rows = db.query(UserInterestRegion).filter_by(user_id=u.id).order_by(UserInterestRegion.priority).all()
    assert [r.region_id for r in rows] == [r1.id, r2.id]


def test_duplicate_user_region_pair_rejected(db: Session) -> None:
    import pytest
    from sqlalchemy.exc import IntegrityError

    u = _make_user(db)
    r = _make_region(db, "yangpyeong-test")
    db.add(UserInterestRegion(user_id=u.id, region_id=r.id, priority=1))
    db.flush()
    db.add(UserInterestRegion(user_id=u.id, region_id=r.id, priority=2))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()
```

Run: `pytest app/tests/integration/test_interest_region_model.py -v`
Expected: 2 passed.

- [ ] **Step 4: ruff + 전체 pytest**

Run: `ruff check app/ && pytest app/tests/ -q`

- [ ] **Step 5: Commit**

```bash
git add app/models/interest_region.py app/models/__init__.py app/db/migrations/versions/ app/tests/integration/test_interest_region_model.py
git commit -m "feat(models): add user_interest_regions M:N table for multi-region prospects"
```

---

## Task 4: Image 모델

**Files:**
- Create: `app/models/image.py`
- Modify: `app/models/__init__.py`
- Create: `app/db/migrations/versions/<rev>_add_images.py`
- Create: `app/tests/integration/test_image_model.py`

PRD §5.1 — 원본·thumb·medium·webp 4 경로 + status enum + post_id (nullable, 업로드 후 즉시 post에 첨부 안 됨).

- [ ] **Step 1: 모델 작성**

`app/models/image.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enums import ImageStatus


class Image(Base):
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    post_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id", ondelete="SET NULL"), nullable=True, index=True
    )

    file_path_orig: Mapped[str] = mapped_column(String(512))
    file_path_thumb: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_path_medium: Mapped[str | None] = mapped_column(String(512), nullable=True)
    file_path_webp: Mapped[str | None] = mapped_column(String(512), nullable=True)

    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    order_idx: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    status: Mapped[ImageStatus] = mapped_column(
        Enum(ImageStatus, name="image_status", values_callable=lambda x: [e.value for e in x]),
        default=ImageStatus.PROCESSING,
        server_default=ImageStatus.PROCESSING.value,
    )

    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

> **NOTE**: `post_id` FK가 `posts` 테이블을 참조하지만 Post 모델은 Task 6에서 추가됨. Alembic 마이그레이션 생성 시 `images` 테이블이 `posts` 보다 먼저 생성되면 FK 제약이 깨지므로 — 이 Task에서는 `post_id` 컬럼만 만들고 **FK 제약은 Task 6의 Post 마이그레이션에서 추가**한다. 아래 Step 2 마이그레이션 스크립트에서 FK 부분 제거.

- [ ] **Step 2: 마이그레이션 작성 (FK 보류)**

Run: `alembic revision --autogenerate -m "add images"` 후 생성된 파일에서 `post_id` 의 ForeignKeyConstraint 라인을 **삭제**하고 컬럼만 남긴다. (Task 6에서 ALTER TABLE ADD CONSTRAINT 로 추가)

수정된 `upgrade()` 예시:

```python
def upgrade() -> None:
    op.create_table(
        "images",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=True),
        sa.Column("file_path_orig", sa.String(512), nullable=False),
        sa.Column("file_path_thumb", sa.String(512), nullable=True),
        sa.Column("file_path_medium", sa.String(512), nullable=True),
        sa.Column("file_path_webp", sa.String(512), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("alt_text", sa.String(255), nullable=True),
        sa.Column("order_idx", sa.Integer(), server_default="0", nullable=False),
        sa.Column("status", sa.Enum("processing", "ready", "failed", name="image_status"),
                  server_default="processing", nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_images_owner_id", "images", ["owner_id"])
    op.create_index("ix_images_post_id", "images", ["post_id"])


def downgrade() -> None:
    op.drop_index("ix_images_post_id", table_name="images")
    op.drop_index("ix_images_owner_id", table_name="images")
    op.drop_table("images")
    op.execute("DROP TYPE image_status")
```

Run: `alembic upgrade head`

- [ ] **Step 3: __init__ + 통합 테스트**

`app/models/__init__.py` 에 `Image` re-export.

`app/tests/integration/test_image_model.py`:

```python
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Image, User
from app.models._enums import ImageStatus


def _make_user(db: Session) -> User:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    db.add(u)
    db.flush()
    return u


def test_create_image_defaults_to_processing(db: Session) -> None:
    u = _make_user(db)
    img = Image(owner_id=u.id, file_path_orig="/media/orig/2026/05/abc.jpg")
    db.add(img)
    db.flush()

    assert img.id is not None
    assert img.status == ImageStatus.PROCESSING
    assert img.order_idx == 0
    assert img.uploaded_at is not None
    assert img.post_id is None


def test_image_can_have_all_size_paths(db: Session) -> None:
    u = _make_user(db)
    img = Image(
        owner_id=u.id,
        file_path_orig="/media/orig/x.jpg",
        file_path_thumb="/media/thumb/x.jpg",
        file_path_medium="/media/medium/x.jpg",
        file_path_webp="/media/webp/x.webp",
        status=ImageStatus.READY,
        width=1920,
        height=1080,
    )
    db.add(img)
    db.flush()
    assert img.status == ImageStatus.READY
    assert img.file_path_webp.endswith(".webp")
```

Run: `pytest app/tests/integration/test_image_model.py -v`
Expected: 2 passed.

- [ ] **Step 4: ruff + 전체 pytest**

- [ ] **Step 5: Commit**

```bash
git add app/models/image.py app/models/__init__.py app/db/migrations/versions/ app/tests/integration/test_image_model.py
git commit -m "feat(models): add Image model with 4-path storage and processing status"
```

---

## Task 5: Journey 모델

**Files:**
- Create: `app/models/journey.py`
- Modify: `app/models/__init__.py`
- Create: `app/db/migrations/versions/<rev>_add_journeys.py`
- Create: `app/tests/integration/test_journey_model.py`

PRD §5.1 — Journey 컨테이너 (cover_image_id FK는 images 참조). Post.journey_id FK는 Task 6에서.

- [ ] **Step 1: 모델 작성**

`app/models/journey.py`:

```python
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enums import JourneyStatus


class Journey(Base):
    __tablename__ = "journeys"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="RESTRICT"), index=True)

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_image_id: Mapped[int | None] = mapped_column(
        ForeignKey("images.id", ondelete="SET NULL"), nullable=True
    )

    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[JourneyStatus] = mapped_column(
        Enum(JourneyStatus, name="journey_status", values_callable=lambda x: [e.value for e in x]),
        default=JourneyStatus.IN_PROGRESS,
        server_default=JourneyStatus.IN_PROGRESS.value,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: 마이그레이션 + upgrade**

Run: `alembic revision --autogenerate -m "add journeys"` → `alembic upgrade head`

- [ ] **Step 3: __init__ + 통합 테스트**

`app/models/__init__.py` 에 `Journey, JourneyStatus` 추가 export.

`app/tests/integration/test_journey_model.py`:

```python
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.models import Journey, Region, User
from app.models._enums import JourneyStatus


def _seed(db: Session) -> tuple[User, Region]:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    r = Region(sido="경기", sigungu="양평군", slug=f"yp-{u.username}")
    db.add_all([u, r])
    db.flush()
    return u, r


def test_create_journey_defaults_in_progress(db: Session) -> None:
    u, r = _seed(db)
    j = Journey(author_id=u.id, region_id=r.id, title="우리 집 짓기")
    db.add(j)
    db.flush()

    assert j.id is not None
    assert j.status == JourneyStatus.IN_PROGRESS
    assert j.created_at is not None
    assert j.deleted_at is None


def test_journey_with_start_date_and_completed(db: Session) -> None:
    u, r = _seed(db)
    j = Journey(
        author_id=u.id,
        region_id=r.id,
        title="3년차 회고",
        start_date=date(2023, 4, 1),
        status=JourneyStatus.COMPLETED,
    )
    db.add(j)
    db.flush()
    assert j.start_date == date(2023, 4, 1)
    assert j.status == JourneyStatus.COMPLETED
```

Run: `pytest app/tests/integration/test_journey_model.py -v`

- [ ] **Step 4: ruff + 전체 pytest**

- [ ] **Step 5: Commit**

```bash
git add app/models/journey.py app/models/__init__.py app/db/migrations/versions/ app/tests/integration/test_journey_model.py
git commit -m "feat(models): add Journey container with status and cover image"
```

---

## Task 6: Post 모델 (type discriminator) + Image post_id FK 연결

**Files:**
- Create: `app/models/post.py`
- Modify: `app/models/__init__.py`
- Create: `app/db/migrations/versions/<rev>_add_posts_and_image_fk.py`
- Create: `app/tests/integration/test_post_model.py`

PRD §5.1 — 단일 통합 콘텐츠 테이블 (review/journey_episode/question/answer/plan). 인덱스 4종 + JSONB metadata GIN. Task 4에서 보류한 `images.post_id` FK 제약을 이 마이그레이션에서 추가.

- [ ] **Step 1: 모델 작성**

`app/models/post.py`:

```python
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime, Enum, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enums import PostStatus, PostType


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        Index("ix_posts_region_published", "region_id", "published_at"),
        Index("ix_posts_journey_episode", "journey_id", "episode_no"),
        Index("ix_posts_author_published", "author_id", "published_at"),
        Index("ix_posts_type_status_published", "type", "status", "published_at"),
        Index("ix_posts_metadata_gin", "metadata_", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="RESTRICT"))
    journey_id: Mapped[int | None] = mapped_column(
        ForeignKey("journeys.id", ondelete="SET NULL"), nullable=True
    )
    parent_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("posts.id", ondelete="SET NULL"), nullable=True
    )

    type: Mapped[PostType] = mapped_column(
        Enum(PostType, name="post_type", values_callable=lambda x: [e.value for e in x])
    )
    episode_no: Mapped[int | None] = mapped_column(Integer, nullable=True)

    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, server_default="{}")

    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus, name="post_status", values_callable=lambda x: [e.value for e in x]),
        default=PostStatus.DRAFT,
        server_default=PostStatus.DRAFT.value,
    )
    view_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

> **NOTE**: 컬럼 속성 이름은 `metadata_` (Python attribute) 이지만 DB 컬럼 이름은 `metadata` (mapping 첫 인자). SQLAlchemy `Base.metadata` 와 충돌 회피.

- [ ] **Step 2: 마이그레이션 작성**

Run: `alembic revision --autogenerate -m "add posts and link images.post_id fk"` 

생성된 마이그레이션의 `upgrade()` 끝에 Task 4에서 보류한 FK 제약 추가:

```python
def upgrade() -> None:
    # autogenerate가 만든 posts 테이블 생성, 인덱스 등 그대로 유지
    # ... (생략) ...

    # Task 4에서 보류한 images.post_id FK
    op.create_foreign_key(
        "fk_images_post_id_posts",
        "images",
        "posts",
        ["post_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_images_post_id_posts", "images", type_="foreignkey")
    # ... posts drop ...
```

Run: `alembic upgrade head`

- [ ] **Step 3: __init__ + 통합 테스트**

`app/models/__init__.py` 에 `Post, PostType, PostStatus` 추가.

`app/tests/integration/test_post_model.py`:

```python
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Post, Region, User
from app.models._enums import PostStatus, PostType


def _seed(db: Session) -> tuple[User, Region]:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    r = Region(sido="경기", sigungu="양평군", slug=f"yp-{u.username}")
    db.add_all([u, r])
    db.flush()
    return u, r


def test_create_review_post_with_metadata(db: Session) -> None:
    u, r = _seed(db)
    p = Post(
        author_id=u.id,
        region_id=r.id,
        type=PostType.REVIEW,
        title="1년차 후기",
        body="단열이 가장 후회됨",
        metadata_={"satisfaction_overall": 4, "regrets": ["단열"]},
    )
    db.add(p)
    db.flush()
    assert p.id is not None
    assert p.status == PostStatus.DRAFT
    assert p.view_count == 0
    assert p.metadata_["satisfaction_overall"] == 4


def test_plan_post_type(db: Session) -> None:
    u, r = _seed(db)
    p = Post(
        author_id=u.id,
        region_id=r.id,
        type=PostType.PLAN,
        title="우리 가족 정착 계획",
        body="2027년 양평 입주 검토",
        metadata_={"target_move_year": 2027, "open_to_advice": True},
    )
    db.add(p)
    db.flush()
    assert p.type == PostType.PLAN


def test_question_with_parent_link(db: Session) -> None:
    u, r = _seed(db)
    q = Post(author_id=u.id, region_id=r.id, type=PostType.QUESTION, title="Q", body="?")
    db.add(q)
    db.flush()
    a = Post(
        author_id=u.id,
        region_id=r.id,
        type=PostType.ANSWER,
        parent_post_id=q.id,
        title="A",
        body="!",
    )
    db.add(a)
    db.flush()
    assert a.parent_post_id == q.id
```

Run: `pytest app/tests/integration/test_post_model.py -v`
Expected: 3 passed.

- [ ] **Step 4: ruff + 전체 pytest**

- [ ] **Step 5: Commit**

```bash
git add app/models/post.py app/models/__init__.py app/db/migrations/versions/ app/tests/integration/test_post_model.py
git commit -m "feat(models): add Post unified content table with type discriminator and JSONB metadata"
```

---

## Task 7: Pydantic Discriminated Union (Post.metadata 검증)

**Files:**
- Create: `app/schemas/__init__.py`
- Create: `app/schemas/post_metadata.py`
- Create: `app/tests/integration/test_post_metadata_schema.py`

PRD §5.3 v1.1 [A3] — `Post.metadata` JSONB의 자유 입력을 막고 Pydantic 모델로 강제. type별 5개 모델 + Discriminated Union 통합. 모든 쓰기 경로(P1.3+)는 이 스키마 통과 후에만 DB 저장.

- [ ] **Step 1: 스키마 모듈 작성**

`app/schemas/__init__.py` (빈 파일).

`app/schemas/post_metadata.py`:

```python
"""Pydantic Discriminated Union for Post.metadata validation.

Enforces schema integrity per Post.type. Used by all write routes
in P1.3+ (write_review, write_plan, journey episode, Q&A).

Reference: PRD §5.3 v1.1 [A3].
"""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, PositiveInt


class _Forbid(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------- Pillar C 공통 sub-schema ----------

class RegretItem(_Forbid):
    category: Literal["land", "design", "build", "move", "life", "region"]
    cost_krw_band: Literal["<100", "100-500", "500-2000", "2000+"]
    time_months_band: Literal["<1", "1-3", "3-6", "6+"]
    free_text: str | None = Field(default=None, max_length=300)


class BudgetBreakdown(_Forbid):
    land: int = 0
    construction: int = 0
    etc: int = 0


class BuilderInfo(_Forbid):
    name: str
    verified: bool = False


class JourneyEpMeta(_Forbid):
    phase: Literal["터", "건축", "입주", "1년차", "3년차"]
    period_label: str = Field(max_length=40)


# ---------- Type별 메타데이터 ----------

class ReviewMetadata(_Forbid):
    type_tag: Literal["review"] = Field(alias="__post_type__", default="review")

    house_type: Literal["단독", "타운하우스", "듀플렉스"]
    size_pyeong: PositiveInt
    land_size_pyeong: PositiveInt | None = None
    budget_total_manwon: PositiveInt | None = None
    budget_breakdown: BudgetBreakdown | None = None
    move_in_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    construction_period_months: PositiveInt | None = None
    satisfaction_overall: int = Field(ge=1, le=5)
    regrets: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)
    builder_info: BuilderInfo | None = None
    regret_items: list[RegretItem] = Field(default_factory=list)
    review_year_offset: int = Field(ge=0, le=10, default=1)


class JourneyEpisodeMetadata(_Forbid):
    type_tag: Literal["journey_episode"] = Field(alias="__post_type__", default="journey_episode")
    journey_ep_meta: JourneyEpMeta


class QuestionMetadata(_Forbid):
    type_tag: Literal["question"] = Field(alias="__post_type__", default="question")
    tags: list[str] = Field(default_factory=list, max_length=10)


class AnswerMetadata(_Forbid):
    type_tag: Literal["answer"] = Field(alias="__post_type__", default="answer")


class PlanMetadata(_Forbid):
    type_tag: Literal["plan"] = Field(alias="__post_type__", default="plan")
    interest_regions: list[int] = Field(default_factory=list, max_length=10)
    target_move_year: int = Field(ge=2026, le=2050)
    household_size: PositiveInt = 1
    budget_total_manwon_band: Literal[
        "<5000", "5000-10000", "10000-20000", "20000-40000", "40000+"
    ]
    must_have: list[str] = Field(default_factory=list, max_length=10)
    nice_to_have: list[str] = Field(default_factory=list, max_length=10)
    concerns: list[str] = Field(default_factory=list, max_length=10)
    construction_intent: Literal["self_build", "buy_existing", "rent_first", "undecided"]
    open_to_advice: bool = True


PostMetadata = Annotated[
    ReviewMetadata | JourneyEpisodeMetadata | QuestionMetadata | AnswerMetadata | PlanMetadata,
    Field(discriminator="type_tag"),
]
```

- [ ] **Step 2: 단위·통합 테스트**

`app/tests/integration/test_post_metadata_schema.py`:

```python
import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.post_metadata import (
    PlanMetadata,
    PostMetadata,
    ReviewMetadata,
)

post_meta_adapter = TypeAdapter(PostMetadata)


def test_review_metadata_minimal_valid() -> None:
    m = ReviewMetadata(
        __post_type__="review",
        house_type="단독",
        size_pyeong=32,
        satisfaction_overall=4,
    )
    assert m.satisfaction_overall == 4
    assert m.review_year_offset == 1


def test_review_rejects_extra_field() -> None:
    with pytest.raises(ValidationError) as exc:
        ReviewMetadata(
            __post_type__="review",
            house_type="단독",
            size_pyeong=32,
            satisfaction_overall=4,
            evil_field="injection",
        )
    assert "evil_field" in str(exc.value)


def test_review_rejects_invalid_satisfaction() -> None:
    with pytest.raises(ValidationError):
        ReviewMetadata(
            __post_type__="review",
            house_type="단독",
            size_pyeong=32,
            satisfaction_overall=99,
        )


def test_plan_metadata_minimal_valid() -> None:
    m = PlanMetadata(
        __post_type__="plan",
        target_move_year=2027,
        budget_total_manwon_band="10000-20000",
        construction_intent="undecided",
    )
    assert m.target_move_year == 2027


def test_discriminator_routes_to_correct_schema() -> None:
    parsed = post_meta_adapter.validate_python({
        "__post_type__": "plan",
        "target_move_year": 2027,
        "budget_total_manwon_band": "10000-20000",
        "construction_intent": "undecided",
    })
    assert isinstance(parsed, PlanMetadata)


def test_regret_item_band_validation() -> None:
    m = ReviewMetadata(
        __post_type__="review",
        house_type="단독",
        size_pyeong=32,
        satisfaction_overall=3,
        regret_items=[
            {
                "category": "land",
                "cost_krw_band": "500-2000",
                "time_months_band": "1-3",
                "free_text": "진입로 포장 추가 비용",
            }
        ],
    )
    assert m.regret_items[0].category == "land"

    with pytest.raises(ValidationError):
        ReviewMetadata(
            __post_type__="review",
            house_type="단독",
            size_pyeong=32,
            satisfaction_overall=3,
            regret_items=[{"category": "INVALID", "cost_krw_band": "<100", "time_months_band": "<1"}],
        )
```

Run: `pytest app/tests/integration/test_post_metadata_schema.py -v`
Expected: 6 passed.

- [ ] **Step 3: ruff + 전체 pytest**

- [ ] **Step 4: Commit**

```bash
git add app/schemas/ app/tests/integration/test_post_metadata_schema.py
git commit -m "feat(schemas): add Pydantic Discriminated Union for Post.metadata validation"
```

---

## Task 8: post_validations (Pillar V)

**Files:**
- Create: `app/models/post_validation.py`
- Modify: `app/models/__init__.py`
- Create: `app/db/migrations/versions/<rev>_add_post_validations.py`
- Create: `app/tests/integration/test_post_validation_model.py`

PRD §1.5.4 v1.1 [C1] — 같은 시군 거주자의 cross-validation. UNIQUE(post_id, validator_user_id).

- [ ] **Step 1: 모델 작성**

`app/models/post_validation.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enums import ValidationVote


class PostValidation(Base):
    __tablename__ = "post_validations"
    __table_args__ = (
        UniqueConstraint("post_id", "validator_user_id", name="uq_post_validations_post_validator"),
        Index("ix_post_validations_post_vote", "post_id", "vote"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    validator_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    vote: Mapped[ValidationVote] = mapped_column(
        Enum(ValidationVote, name="validation_vote", values_callable=lambda x: [e.value for e in x])
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: 마이그레이션 + upgrade**

Run: `alembic revision --autogenerate -m "add post_validations"` → `alembic upgrade head`

- [ ] **Step 3: 통합 테스트**

`app/models/__init__.py` 에 `PostValidation` 추가.

`app/tests/integration/test_post_validation_model.py`:

```python
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Post, PostValidation, Region, User
from app.models._enums import PostType, ValidationVote


def _seed_post(db: Session) -> tuple[User, Post]:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    r = Region(sido="경기", sigungu="양평군", slug=f"yp-{u.username}")
    db.add_all([u, r])
    db.flush()
    p = Post(author_id=u.id, region_id=r.id, type=PostType.REVIEW, title="후기", body="...")
    db.add(p)
    db.flush()
    return u, p


def test_create_confirm_validation(db: Session) -> None:
    u, p = _seed_post(db)
    v = PostValidation(post_id=p.id, validator_user_id=u.id, vote=ValidationVote.CONFIRM)
    db.add(v)
    db.flush()
    assert v.id is not None
    assert v.vote == ValidationVote.CONFIRM


def test_duplicate_validator_per_post_rejected(db: Session) -> None:
    u, p = _seed_post(db)
    db.add(PostValidation(post_id=p.id, validator_user_id=u.id, vote=ValidationVote.CONFIRM))
    db.flush()
    db.add(PostValidation(post_id=p.id, validator_user_id=u.id, vote=ValidationVote.DISPUTE))
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_dispute_with_note(db: Session) -> None:
    u, p = _seed_post(db)
    v = PostValidation(
        post_id=p.id,
        validator_user_id=u.id,
        vote=ValidationVote.DISPUTE,
        note="시공사명 일치하지 않음",
    )
    db.add(v)
    db.flush()
    assert v.note == "시공사명 일치하지 않음"
```

Run: `pytest app/tests/integration/test_post_validation_model.py -v`

- [ ] **Step 4: ruff + 전체 pytest**

- [ ] **Step 5: Commit**

```bash
git add app/models/post_validation.py app/models/__init__.py app/db/migrations/versions/ app/tests/integration/test_post_validation_model.py
git commit -m "feat(models): add PostValidation table for Pillar V cross-validation"
```

---

## Task 9: Comment 모델 (스레디드)

**Files:**
- Create: `app/models/comment.py`
- Modify: `app/models/__init__.py`
- Create: `app/db/migrations/versions/<rev>_add_comments.py`
- Create: `app/tests/integration/test_comment_model.py`

PRD §5.1 — `parent_id` 자가참조로 스레디드 댓글 + soft delete.

- [ ] **Step 1: 모델 작성**

`app/models/comment.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enums import CommentStatus


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), nullable=True
    )

    body: Mapped[str] = mapped_column(Text)
    status: Mapped[CommentStatus] = mapped_column(
        Enum(CommentStatus, name="comment_status", values_callable=lambda x: [e.value for e in x]),
        default=CommentStatus.VISIBLE,
        server_default=CommentStatus.VISIBLE.value,
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: 마이그레이션 + upgrade**

Run: `alembic revision --autogenerate -m "add comments"` → `alembic upgrade head`

- [ ] **Step 3: __init__ + 통합 테스트**

`app/tests/integration/test_comment_model.py`:

```python
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Comment, Post, Region, User
from app.models._enums import CommentStatus, PostType


def _seed(db: Session) -> tuple[User, Post]:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    r = Region(sido="경기", sigungu="양평군", slug=f"yp-{u.username}")
    db.add_all([u, r])
    db.flush()
    p = Post(author_id=u.id, region_id=r.id, type=PostType.REVIEW, title="t", body="b")
    db.add(p)
    db.flush()
    return u, p


def test_create_top_level_comment(db: Session) -> None:
    u, p = _seed(db)
    c = Comment(post_id=p.id, author_id=u.id, body="좋은 후기네요")
    db.add(c)
    db.flush()
    assert c.id is not None
    assert c.parent_id is None
    assert c.status == CommentStatus.VISIBLE


def test_threaded_reply(db: Session) -> None:
    u, p = _seed(db)
    parent = Comment(post_id=p.id, author_id=u.id, body="원댓글")
    db.add(parent)
    db.flush()
    reply = Comment(post_id=p.id, author_id=u.id, parent_id=parent.id, body="답글")
    db.add(reply)
    db.flush()
    assert reply.parent_id == parent.id


def test_soft_delete_comment(db: Session) -> None:
    u, p = _seed(db)
    c = Comment(post_id=p.id, author_id=u.id, body="x")
    db.add(c)
    db.flush()
    c.deleted_at = datetime.now(UTC)
    db.flush()
    assert c.deleted_at is not None
```

Run: `pytest app/tests/integration/test_comment_model.py -v`

- [ ] **Step 4: ruff + 전체 pytest**

- [ ] **Step 5: Commit**

```bash
git add app/models/comment.py app/models/__init__.py app/db/migrations/versions/ app/tests/integration/test_comment_model.py
git commit -m "feat(models): add Comment threaded with soft delete"
```

---

## Task 10: Tags + post_tags

**Files:**
- Create: `app/models/tag.py`
- Modify: `app/models/__init__.py`
- Create: `app/db/migrations/versions/<rev>_add_tags.py`
- Create: `app/tests/integration/test_tag_model.py`

PRD §5.1 — Tag + post_tags M:N. tag.name UNIQUE, slug UNIQUE.

- [ ] **Step 1: 모델 작성**

`app/models/tag.py`:

```python
from sqlalchemy import Column, ForeignKey, PrimaryKeyConstraint, String, Table
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), nullable=False),
    PrimaryKeyConstraint("post_id", "tag_id"),
)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
```

- [ ] **Step 2: 마이그레이션 + upgrade**

Run: `alembic revision --autogenerate -m "add tags and post_tags"` → `alembic upgrade head`

- [ ] **Step 3: __init__ + 통합 테스트**

`app/models/__init__.py` 에 `Tag` 추가 (post_tags는 Table 객체, export 불필요).

`app/tests/integration/test_tag_model.py`:

```python
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Post, Region, Tag, User
from app.models._enums import PostType
from app.models.tag import post_tags


def _seed_post(db: Session) -> Post:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    r = Region(sido="경기", sigungu="양평군", slug=f"yp-{u.username}")
    db.add_all([u, r])
    db.flush()
    p = Post(author_id=u.id, region_id=r.id, type=PostType.REVIEW, title="t", body="b")
    db.add(p)
    db.flush()
    return p


def test_create_tag_unique_name(db: Session) -> None:
    db.add(Tag(name="단열", slug="insulation"))
    db.flush()
    with pytest.raises(IntegrityError):
        db.add(Tag(name="단열", slug="insulation-2"))
        db.flush()
    db.rollback()


def test_attach_tag_to_post(db: Session) -> None:
    p = _seed_post(db)
    t = Tag(name="후회", slug="regret")
    db.add(t)
    db.flush()
    db.execute(post_tags.insert().values(post_id=p.id, tag_id=t.id))
    db.flush()

    rows = db.execute(post_tags.select().where(post_tags.c.post_id == p.id)).all()
    assert len(rows) == 1
```

Run: `pytest app/tests/integration/test_tag_model.py -v`

- [ ] **Step 4: ruff + 전체 pytest**

- [ ] **Step 5: Commit**

```bash
git add app/models/tag.py app/models/__init__.py app/db/migrations/versions/ app/tests/integration/test_tag_model.py
git commit -m "feat(models): add Tag and post_tags M:N junction"
```

---

## Task 11: 라이트 상호작용 (post_likes · post_scraps · user_follows · journey_follows)

**Files:**
- Create: `app/models/interaction.py`
- Modify: `app/models/__init__.py`
- Create: `app/db/migrations/versions/<rev>_add_interactions.py`
- Create: `app/tests/integration/test_interaction_model.py`

PRD §5.1 — 4종 라이트 테이블, 모두 (a, b, created_at) 패턴. PK=(a, b) UNIQUE. 한 모델 파일에 묶어서 일관성 유지.

- [ ] **Step 1: 모델 작성**

`app/models/interaction.py`:

```python
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, PrimaryKeyConstraint, Table, func

from app.db.base import Base


def _interaction_table(name: str, left: str, right: str) -> Table:
    return Table(
        name,
        Base.metadata,
        Column(left, ForeignKey("users.id" if left == "follower_id" or left == "user_id"
                                else f"{left[:-3]}s.id", ondelete="CASCADE"), nullable=False),
        Column(right, ForeignKey(f"{right[:-3]}s.id" if not right.endswith("user_id")
                                  else "users.id", ondelete="CASCADE"), nullable=False),
        Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
        PrimaryKeyConstraint(left, right),
    )


# 명시적 정의로 가독성 우선 — 헬퍼 사용 안 함
post_likes = Table(
    "post_likes",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("post_id", "user_id"),
)

post_scraps = Table(
    "post_scraps",
    Base.metadata,
    Column("post_id", ForeignKey("posts.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("post_id", "user_id"),
)

user_follows = Table(
    "user_follows",
    Base.metadata,
    Column("follower_id", ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("following_id", ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("follower_id", "following_id"),
)

journey_follows = Table(
    "journey_follows",
    Base.metadata,
    Column("journey_id", ForeignKey("journeys.id", ondelete="CASCADE"), nullable=False),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("journey_id", "user_id"),
)
```

> **NOTE**: 헬퍼 함수 정의는 가독성 명료를 위해 사용하지 않고 4개 Table을 명시적으로 작성. 일관성 ≠ 추상화. 4개라 명시적 정의가 유지보수 더 쉬움.

- [ ] **Step 2: 마이그레이션 + upgrade**

Run: `alembic revision --autogenerate -m "add interaction tables"` → `alembic upgrade head`

- [ ] **Step 3: __init__ + 통합 테스트**

`app/models/__init__.py` 에 `from app.models.interaction import journey_follows, post_likes, post_scraps, user_follows` 추가 (Table 객체이므로 __all__엔 포함하되 클래스 export와 분리해 정리).

`app/tests/integration/test_interaction_model.py`:

```python
from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Journey, Post, Region, User
from app.models._enums import PostType
from app.models.interaction import journey_follows, post_likes, post_scraps, user_follows


def _seed(db: Session) -> tuple[User, Region, Post]:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    r = Region(sido="경기", sigungu="양평군", slug=f"yp-{u.username}")
    db.add_all([u, r])
    db.flush()
    p = Post(author_id=u.id, region_id=r.id, type=PostType.REVIEW, title="t", body="b")
    db.add(p)
    db.flush()
    return u, r, p


def test_post_like_unique_per_user(db: Session) -> None:
    u, _, p = _seed(db)
    db.execute(post_likes.insert().values(post_id=p.id, user_id=u.id))
    db.flush()
    with pytest.raises(IntegrityError):
        db.execute(post_likes.insert().values(post_id=p.id, user_id=u.id))
        db.flush()
    db.rollback()


def test_post_scrap_separate_table(db: Session) -> None:
    u, _, p = _seed(db)
    db.execute(post_scraps.insert().values(post_id=p.id, user_id=u.id))
    db.flush()
    rows = db.execute(post_scraps.select().where(post_scraps.c.user_id == u.id)).all()
    assert len(rows) == 1


def test_user_follow_self_allowed_or_not_app_layer(db: Session) -> None:
    """DB 레벨엔 self-follow 제약 없음 — app 계층에서 막을 것 (P1.5)."""
    u, _, _ = _seed(db)
    db.execute(user_follows.insert().values(follower_id=u.id, following_id=u.id))
    db.flush()
    rows = db.execute(user_follows.select().where(user_follows.c.follower_id == u.id)).all()
    assert len(rows) == 1


def test_journey_follow(db: Session) -> None:
    u, r, _ = _seed(db)
    j = Journey(author_id=u.id, region_id=r.id, title="J")
    db.add(j)
    db.flush()
    db.execute(journey_follows.insert().values(journey_id=j.id, user_id=u.id))
    db.flush()
    rows = db.execute(journey_follows.select()).all()
    assert len(rows) == 1
```

Run: `pytest app/tests/integration/test_interaction_model.py -v`
Expected: 4 passed.

- [ ] **Step 4: ruff + 전체 pytest**

- [ ] **Step 5: Commit**

```bash
git add app/models/interaction.py app/models/__init__.py app/db/migrations/versions/ app/tests/integration/test_interaction_model.py
git commit -m "feat(models): add lite interaction tables (likes, scraps, user/journey follows)"
```

---

## Task 12: BadgeApplication + BadgeEvidence

**Files:**
- Create: `app/models/badge_application.py`
- Modify: `app/models/__init__.py`
- Create: `app/db/migrations/versions/<rev>_add_badge_applications.py`
- Create: `app/tests/integration/test_badge_application_model.py`

PRD §5.1 — 신청 큐 + 증빙 파일. evidence는 비공개 디렉토리 (path만 저장) + 30일 후 자동 삭제 잡 트리거 컬럼.

- [ ] **Step 1: 모델 작성**

`app/models/badge_application.py`:

```python
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enums import (
    BadgeApplicationStatus,
    BadgeRequestedLevel,
    EvidenceType,
)


class BadgeApplication(Base):
    __tablename__ = "badge_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    requested_level: Mapped[BadgeRequestedLevel] = mapped_column(
        Enum(BadgeRequestedLevel, name="badge_requested_level",
             values_callable=lambda x: [e.value for e in x])
    )
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="RESTRICT"))
    status: Mapped[BadgeApplicationStatus] = mapped_column(
        Enum(BadgeApplicationStatus, name="badge_application_status",
             values_callable=lambda x: [e.value for e in x]),
        default=BadgeApplicationStatus.PENDING,
        server_default=BadgeApplicationStatus.PENDING.value,
        index=True,
    )
    reviewer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BadgeEvidence(Base):
    __tablename__ = "badge_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("badge_applications.id", ondelete="CASCADE"), index=True
    )
    evidence_type: Mapped[EvidenceType] = mapped_column(
        Enum(EvidenceType, name="evidence_type",
             values_callable=lambda x: [e.value for e in x])
    )
    file_path: Mapped[str] = mapped_column(String(512))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    scheduled_delete_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: 마이그레이션 + upgrade**

Run: `alembic revision --autogenerate -m "add badge applications and evidence"` → `alembic upgrade head`

- [ ] **Step 3: __init__ + 통합 테스트**

`app/tests/integration/test_badge_application_model.py`:

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import BadgeApplication, BadgeEvidence, Region, User
from app.models._enums import (
    BadgeApplicationStatus,
    BadgeRequestedLevel,
    EvidenceType,
)


def _seed(db: Session) -> tuple[User, Region]:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    r = Region(sido="경기", sigungu="양평군", slug=f"yp-{u.username}")
    db.add_all([u, r])
    db.flush()
    return u, r


def test_create_resident_application_pending(db: Session) -> None:
    u, r = _seed(db)
    app = BadgeApplication(
        user_id=u.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=r.id,
    )
    db.add(app)
    db.flush()
    assert app.status == BadgeApplicationStatus.PENDING
    assert app.applied_at is not None
    assert app.reviewed_at is None


def test_attach_evidence_with_scheduled_delete(db: Session) -> None:
    u, r = _seed(db)
    app = BadgeApplication(
        user_id=u.id,
        requested_level=BadgeRequestedLevel.RESIDENT,
        region_id=r.id,
    )
    db.add(app)
    db.flush()
    delete_at = datetime.now(UTC) + timedelta(days=30)
    e = BadgeEvidence(
        application_id=app.id,
        evidence_type=EvidenceType.UTILITY_BILL,
        file_path="/private/evidence/2026/05/abc.jpg",
        scheduled_delete_at=delete_at,
    )
    db.add(e)
    db.flush()
    assert e.evidence_type == EvidenceType.UTILITY_BILL
    assert e.scheduled_delete_at is not None
```

Run: `pytest app/tests/integration/test_badge_application_model.py -v`

- [ ] **Step 4: ruff + 전체 pytest**

- [ ] **Step 5: Commit**

```bash
git add app/models/badge_application.py app/models/__init__.py app/db/migrations/versions/ app/tests/integration/test_badge_application_model.py
git commit -m "feat(models): add BadgeApplication queue and BadgeEvidence private storage"
```

---

## Task 13: Notification 모델

**Files:**
- Create: `app/models/notification.py`
- Modify: `app/models/__init__.py`
- Create: `app/db/migrations/versions/<rev>_add_notifications.py`
- Create: `app/tests/integration/test_notification_model.py`

PRD §5.1 — 알림 큐. polymorphic target (target_type, target_id). 인앱 bell UI 우선, 카카오 알림톡은 P1.5에서 worker handler가 발송.

- [ ] **Step 1: 모델 작성**

`app/models/notification.py`:

```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enums import NotificationType


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_unread_created",
              "user_id", "is_read", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type",
             values_callable=lambda x: [e.value for e in x])
    )
    source_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: 마이그레이션 + upgrade**

Run: `alembic revision --autogenerate -m "add notifications"` → `alembic upgrade head`

- [ ] **Step 3: __init__ + 통합 테스트**

`app/tests/integration/test_notification_model.py`:

```python
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Notification, User
from app.models._enums import NotificationType


def _make_user(db: Session) -> User:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    db.add(u)
    db.flush()
    return u


def test_create_unread_notification(db: Session) -> None:
    u = _make_user(db)
    n = Notification(
        user_id=u.id,
        type=NotificationType.BADGE_APPROVED,
        target_type="badge_application",
        target_id=42,
    )
    db.add(n)
    db.flush()
    assert n.is_read is False
    assert n.target_type == "badge_application"


def test_mark_as_read(db: Session) -> None:
    u = _make_user(db)
    n = Notification(user_id=u.id, type=NotificationType.SYSTEM)
    db.add(n)
    db.flush()
    n.is_read = True
    db.flush()
    assert n.is_read is True
```

Run: `pytest app/tests/integration/test_notification_model.py -v`

- [ ] **Step 4: ruff + 전체 pytest**

- [ ] **Step 5: Commit**

```bash
git add app/models/notification.py app/models/__init__.py app/db/migrations/versions/ app/tests/integration/test_notification_model.py
git commit -m "feat(models): add Notification with polymorphic target and read state"
```

---

## Task 14: Report + AuditLog + Announcement (운영 묶음)

**Files:**
- Create: `app/models/moderation.py`
- Modify: `app/models/__init__.py`
- Create: `app/db/migrations/versions/<rev>_add_moderation.py`
- Create: `app/tests/integration/test_moderation_model.py`

PRD §5.1 — 3개 운영 모델을 한 모듈에 묶음 (의미적 응집, 한 마이그레이션). 일관성 우선 — 다른 묶음(interaction.py, tag.py)과 동일 패턴.

- [ ] **Step 1: 모델 작성**

`app/models/moderation.py`:

```python
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enums import AuditAction, ReportReason, ReportStatus


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[int] = mapped_column(Integer)
    reason: Mapped[ReportReason] = mapped_column(
        Enum(ReportReason, name="report_reason",
             values_callable=lambda x: [e.value for e in x])
    )
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status",
             values_callable=lambda x: [e.value for e in x]),
        default=ReportStatus.PENDING,
        server_default=ReportStatus.PENDING.value,
    )
    handled_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, name="audit_action",
             values_callable=lambda x: [e.value for e in x])
    )
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[int] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Announcement(Base):
    __tablename__ = "announcements"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: 마이그레이션 + upgrade**

Run: `alembic revision --autogenerate -m "add moderation models (report, audit, announcement)"` → `alembic upgrade head`

- [ ] **Step 3: __init__ + 통합 테스트**

`app/tests/integration/test_moderation_model.py`:

```python
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Announcement, AuditLog, Report, User
from app.models._enums import AuditAction, ReportReason, ReportStatus


def _make_user(db: Session) -> User:
    u = User(
        email=f"t{int(datetime.now(UTC).timestamp() * 1_000_000)}@example.com",
        username=f"u{int(datetime.now(UTC).timestamp() * 1_000_000)}",
        display_name="테스터",
        password_hash="x",
    )
    db.add(u)
    db.flush()
    return u


def test_create_report_pending(db: Session) -> None:
    u = _make_user(db)
    r = Report(
        reporter_id=u.id,
        target_type="post",
        target_id=999,
        reason=ReportReason.AD,
        detail="홍보성 내용 의심",
    )
    db.add(r)
    db.flush()
    assert r.status == ReportStatus.PENDING


def test_audit_log_action(db: Session) -> None:
    u = _make_user(db)
    a = AuditLog(
        actor_id=u.id,
        action=AuditAction.BADGE_APPROVED,
        target_type="badge_application",
        target_id=1,
    )
    db.add(a)
    db.flush()
    assert a.action == AuditAction.BADGE_APPROVED
    assert a.created_at is not None


def test_pinned_announcement(db: Session) -> None:
    u = _make_user(db)
    a = Announcement(
        author_id=u.id,
        title="베타 오픈 안내",
        body="2026-06-01부터 양평 시범 시작",
        pinned=True,
    )
    db.add(a)
    db.flush()
    assert a.pinned is True
```

Run: `pytest app/tests/integration/test_moderation_model.py -v`

- [ ] **Step 4: ruff + 전체 pytest**

- [ ] **Step 5: Commit**

```bash
git add app/models/moderation.py app/models/__init__.py app/db/migrations/versions/ app/tests/integration/test_moderation_model.py
git commit -m "feat(models): add moderation models (report, audit_log, announcement)"
```

---

## Task 15: Job 모델 (jobs 큐 테이블)

**Files:**
- Create: `app/models/job.py`
- Modify: `app/models/__init__.py`
- Create: `app/db/migrations/versions/<rev>_add_jobs.py`
- Create: `app/tests/integration/test_job_model.py`

PRD §6.7 v1.1 [A1] — 영속화 작업 큐의 핵심 테이블. status, attempts, run_after, locked_by, last_error.

- [ ] **Step 1: 모델 작성**

`app/models/job.py`:

```python
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enums import JobKind, JobStatus


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        Index("ix_jobs_status_run_after", "status", "run_after"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[JobKind] = mapped_column(
        Enum(JobKind, name="job_kind", values_callable=lambda x: [e.value for e in x])
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", values_callable=lambda x: [e.value for e in x]),
        default=JobStatus.QUEUED,
        server_default=JobStatus.QUEUED.value,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: 마이그레이션 + upgrade**

Run: `alembic revision --autogenerate -m "add jobs queue table"` → `alembic upgrade head`

- [ ] **Step 3: __init__ + 통합 테스트**

`app/tests/integration/test_job_model.py`:

```python
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Job
from app.models._enums import JobKind, JobStatus


def test_create_queued_job(db: Session) -> None:
    j = Job(
        kind=JobKind.IMAGE_RESIZE,
        payload={"image_id": 42, "source_path": "/media/orig/x.jpg"},
    )
    db.add(j)
    db.flush()
    assert j.status == JobStatus.QUEUED
    assert j.attempts == 0
    assert j.max_attempts == 5
    assert j.run_after is not None
    assert j.locked_at is None


def test_job_jsonb_payload_round_trip(db: Session) -> None:
    j = Job(
        kind=JobKind.NOTIFICATION,
        payload={"user_id": 1, "type": "badge_approved", "channel": "alimtalk"},
    )
    db.add(j)
    db.flush()
    db.expire(j)
    fetched = db.get(Job, j.id)
    assert fetched.payload["channel"] == "alimtalk"
```

Run: `pytest app/tests/integration/test_job_model.py -v`

- [ ] **Step 4: ruff + 전체 pytest**

- [ ] **Step 5: Commit**

```bash
git add app/models/job.py app/models/__init__.py app/db/migrations/versions/ app/tests/integration/test_job_model.py
git commit -m "feat(models): add Job queue table for PG-based background workers"
```

---

## Task 16: workers/queue.py — enqueue · dequeue · mark_*

**Files:**
- Create: `app/workers/__init__.py`
- Create: `app/workers/queue.py`
- Create: `app/tests/integration/test_job_queue.py`

PRD §6.7 v1.1 [A1] — `SELECT ... FOR UPDATE SKIP LOCKED` 동시성 안전 dequeue, 지수 백오프 retry, dead 상태 전환. NOTIFY 발송은 enqueue에서.

- [ ] **Step 1: queue 모듈 작성**

`app/workers/__init__.py` (빈 파일).

`app/workers/queue.py`:

```python
"""PostgreSQL-based job queue primitives.

Reference: PRD §6.7 v1.1 [A1].

- enqueue() inserts a row and emits NOTIFY on the `nestory_jobs` channel.
- dequeue() picks one queued job atomically using FOR UPDATE SKIP LOCKED.
- mark_succeeded()/mark_failed() finalize a running job; mark_failed implements
  exponential backoff and DEAD transition after max_attempts.
"""
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Job
from app.models._enums import JobKind, JobStatus

NOTIFY_CHANNEL = "nestory_jobs"


def enqueue(
    db: Session,
    kind: JobKind,
    payload: dict[str, Any],
    *,
    run_after: datetime | None = None,
    max_attempts: int = 5,
) -> Job:
    """Insert a queued job and emit NOTIFY. Caller must commit."""
    job = Job(
        kind=kind,
        payload=payload,
        run_after=run_after or datetime.now(UTC),
        max_attempts=max_attempts,
    )
    db.add(job)
    db.flush()
    # NOTIFY uses the kind value as the payload so workers can filter (optional).
    db.execute(text(f"NOTIFY {NOTIFY_CHANNEL}, :payload").bindparams(payload=kind.value))
    return job


def dequeue(db: Session, *, worker_id: str) -> Job | None:
    """Pick one queued job whose run_after has elapsed.

    Uses FOR UPDATE SKIP LOCKED for safe concurrent worker pickup.
    Returns None if queue is empty. Caller must commit on success/failure.
    """
    stmt = (
        select(Job)
        .where(
            Job.status == JobStatus.QUEUED,
            Job.run_after <= datetime.now(UTC),
        )
        .order_by(Job.run_after.asc(), Job.id.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = db.scalar(stmt)
    if job is None:
        return None
    job.status = JobStatus.RUNNING
    job.locked_at = datetime.now(UTC)
    job.locked_by = worker_id
    job.attempts += 1
    db.flush()
    return job


def mark_succeeded(db: Session, job: Job) -> None:
    job.status = JobStatus.SUCCEEDED
    job.completed_at = datetime.now(UTC)
    job.locked_at = None
    job.locked_by = None
    db.flush()


def mark_failed(db: Session, job: Job, error: str) -> None:
    """Failed job: re-queue with exponential backoff or mark DEAD if maxed out."""
    job.last_error = error[:5000]
    if job.attempts >= job.max_attempts:
        job.status = JobStatus.DEAD
        job.completed_at = datetime.now(UTC)
        job.locked_at = None
        job.locked_by = None
    else:
        backoff_seconds = 60 * (2 ** (job.attempts - 1))
        job.status = JobStatus.QUEUED
        job.run_after = datetime.now(UTC) + timedelta(seconds=backoff_seconds)
        job.locked_at = None
        job.locked_by = None
    db.flush()
```

- [ ] **Step 2: 통합 테스트**

`app/tests/integration/test_job_queue.py`:

```python
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Job
from app.models._enums import JobKind, JobStatus
from app.workers import queue


def test_enqueue_creates_queued_job(db: Session) -> None:
    j = queue.enqueue(db, JobKind.IMAGE_RESIZE, {"image_id": 1})
    db.commit()
    assert j.status == JobStatus.QUEUED
    assert j.payload == {"image_id": 1}


def test_dequeue_picks_oldest_due_job(db: Session) -> None:
    queue.enqueue(db, JobKind.IMAGE_RESIZE, {"image_id": 1})
    queue.enqueue(db, JobKind.NOTIFICATION, {"user_id": 1})
    db.commit()

    j = queue.dequeue(db, worker_id="test-worker")
    db.commit()
    assert j is not None
    assert j.status == JobStatus.RUNNING
    assert j.locked_by == "test-worker"
    assert j.attempts == 1


def test_dequeue_skips_future_run_after(db: Session) -> None:
    future = datetime.now(UTC) + timedelta(hours=1)
    queue.enqueue(db, JobKind.IMAGE_RESIZE, {"x": 1}, run_after=future)
    db.commit()
    assert queue.dequeue(db, worker_id="w1") is None


def test_dequeue_returns_none_for_empty_queue(db: Session) -> None:
    assert queue.dequeue(db, worker_id="w1") is None


def test_mark_succeeded(db: Session) -> None:
    queue.enqueue(db, JobKind.IMAGE_RESIZE, {})
    db.commit()
    j = queue.dequeue(db, worker_id="w1")
    queue.mark_succeeded(db, j)
    db.commit()
    assert j.status == JobStatus.SUCCEEDED
    assert j.completed_at is not None
    assert j.locked_by is None


def test_mark_failed_retry_with_backoff(db: Session) -> None:
    queue.enqueue(db, JobKind.IMAGE_RESIZE, {}, max_attempts=3)
    db.commit()
    j = queue.dequeue(db, worker_id="w1")
    before = datetime.now(UTC)
    queue.mark_failed(db, j, "boom")
    db.commit()
    assert j.status == JobStatus.QUEUED
    assert j.run_after > before  # backoff applied
    assert j.last_error == "boom"
    assert j.attempts == 1


def test_mark_failed_dead_after_max_attempts(db: Session) -> None:
    queue.enqueue(db, JobKind.IMAGE_RESIZE, {}, max_attempts=2)
    db.commit()

    # 1st attempt
    j = queue.dequeue(db, worker_id="w1")
    queue.mark_failed(db, j, "err1")
    db.commit()
    # Move run_after to past so it can be dequeued again immediately
    j.run_after = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    # 2nd attempt
    j2 = queue.dequeue(db, worker_id="w1")
    assert j2.id == j.id
    queue.mark_failed(db, j2, "err2")
    db.commit()
    assert j2.status == JobStatus.DEAD
    assert j2.completed_at is not None
    assert j2.attempts == 2
```

Run: `pytest app/tests/integration/test_job_queue.py -v`
Expected: 7 passed.

- [ ] **Step 3: ruff + 전체 pytest**

- [ ] **Step 4: Commit**

```bash
git add app/workers/__init__.py app/workers/queue.py app/tests/integration/test_job_queue.py
git commit -m "feat(workers): add PG-based job queue with SKIP LOCKED dequeue and backoff retry"
```

---

## Task 17: workers/handlers — 레지스트리 + stub 핸들러

**Files:**
- Create: `app/workers/handlers/__init__.py`
- Create: `app/workers/handlers/image_resize.py`
- Create: `app/workers/handlers/notification.py`
- Create: `app/tests/integration/test_handlers_registry.py`

PRD §6.7 — 핸들러 레지스트리 (kind → callable). P1.1엔 두 stub만 등록 (실제 로직은 P1.3·P1.5). 모든 핸들러는 `register(JobKind.X)` 데코레이터로 자동 등록.

- [ ] **Step 1: 레지스트리 + stub 핸들러 작성**

`app/workers/handlers/__init__.py`:

```python
"""Job handler registry.

Each handler module decorates its callable with `@register(JobKind.X)`.
`import_handlers()` imports all modules so decorators run.
`dispatch(kind, payload)` invokes the matching handler — raises if missing.
"""
from collections.abc import Callable
from typing import Any

import structlog

from app.models._enums import JobKind

log = structlog.get_logger(__name__)
Handler = Callable[[dict[str, Any]], None]
_REGISTRY: dict[JobKind, Handler] = {}


def register(kind: JobKind) -> Callable[[Handler], Handler]:
    def deco(fn: Handler) -> Handler:
        if kind in _REGISTRY:
            raise RuntimeError(f"Handler for {kind.value} already registered")
        _REGISTRY[kind] = fn
        return fn
    return deco


def dispatch(kind: JobKind, payload: dict[str, Any]) -> None:
    handler = _REGISTRY.get(kind)
    if handler is None:
        raise RuntimeError(f"No handler registered for {kind.value}")
    handler(payload)


def registered_kinds() -> set[JobKind]:
    return set(_REGISTRY.keys())


def import_handlers() -> None:
    """Import all handler modules so decorators register them."""
    from app.workers.handlers import image_resize, notification  # noqa: F401
```

`app/workers/handlers/image_resize.py`:

```python
"""image_resize handler — Phase 1.3에서 실제 Pillow 변환 구현. P1.1은 stub."""
from typing import Any

import structlog

from app.models._enums import JobKind
from app.workers.handlers import register

log = structlog.get_logger(__name__)


@register(JobKind.IMAGE_RESIZE)
def handle_image_resize(payload: dict[str, Any]) -> None:
    log.info("handler.image_resize.received", payload=payload)
```

`app/workers/handlers/notification.py`:

```python
"""notification handler — P1.5에서 실제 카카오 알림톡·이메일 발송 구현. P1.1은 stub."""
from typing import Any

import structlog

from app.models._enums import JobKind
from app.workers.handlers import register

log = structlog.get_logger(__name__)


@register(JobKind.NOTIFICATION)
def handle_notification(payload: dict[str, Any]) -> None:
    log.info("handler.notification.received", payload=payload)
```

- [ ] **Step 2: 통합 테스트**

`app/tests/integration/test_handlers_registry.py`:

```python
import pytest

from app.models._enums import JobKind
from app.workers.handlers import dispatch, import_handlers, registered_kinds


def test_import_handlers_registers_phase11_stubs() -> None:
    import_handlers()
    kinds = registered_kinds()
    assert JobKind.IMAGE_RESIZE in kinds
    assert JobKind.NOTIFICATION in kinds


def test_dispatch_invokes_registered_handler(caplog) -> None:
    import_handlers()
    # Should not raise; structlog goes to default logger.
    dispatch(JobKind.IMAGE_RESIZE, {"image_id": 99})


def test_dispatch_unknown_kind_raises() -> None:
    import_handlers()
    with pytest.raises(RuntimeError, match="No handler registered"):
        dispatch(JobKind.EVIDENCE_CLEANUP, {})
```

Run: `pytest app/tests/integration/test_handlers_registry.py -v`
Expected: 3 passed.

- [ ] **Step 3: ruff + 전체 pytest**

- [ ] **Step 4: Commit**

```bash
git add app/workers/handlers/ app/tests/integration/test_handlers_registry.py
git commit -m "feat(workers): add handler registry with image_resize and notification stubs"
```

---

## Task 18: workers/runner.py — 메인 루프 + LISTEN/NOTIFY + signal

**Files:**
- Create: `app/workers/runner.py`

PRD §6.7 v1.1 [A1] — 단일 워커 프로세스. 큐 비어있을 때 `LISTEN/NOTIFY` 로 즉시 깨우기 + 1초 폴링 fallback. SIGTERM/SIGINT graceful shutdown. e2e 테스트는 Task 20에서.

- [ ] **Step 1: runner 모듈 작성**

`app/workers/runner.py`:

```python
"""Background worker process — PG-based job queue.

- Imports all handler modules so they self-register.
- Picks one queued job at a time (FOR UPDATE SKIP LOCKED).
- When the queue is empty, blocks on LISTEN nestory_jobs with a polling timeout.
- Handles SIGTERM/SIGINT for graceful shutdown.

Run: `python -m app.workers.runner`
"""
from __future__ import annotations

import os
import signal
import socket
import time
from threading import Event

import psycopg
import structlog

from app.config import get_settings
from app.db.session import SessionLocal
from app.workers import queue
from app.workers.handlers import dispatch, import_handlers

log = structlog.get_logger(__name__)
WORKER_ID = f"{socket.gethostname()}-{os.getpid()}"
NOTIFY_CHANNEL = queue.NOTIFY_CHANNEL
POLL_INTERVAL_SECONDS = 1.0
SHUTDOWN = Event()


def _install_signal_handlers() -> None:
    def _handler(signum: int, _frame) -> None:  # noqa: ANN001 (frame is opaque)
        log.info("worker.shutdown_requested", signal=signum)
        SHUTDOWN.set()
    signal.signal(signal.SIGTERM, _handler)
    signal.signal(signal.SIGINT, _handler)


def process_one() -> bool:
    """Pick and run one job. Returns True if a job was processed, False if queue empty."""
    with SessionLocal() as db:
        job = queue.dequeue(db, worker_id=WORKER_ID)
        if job is None:
            return False

        kind = job.kind
        payload = dict(job.payload)
        try:
            dispatch(kind, payload)
        except Exception as exc:
            log.exception("worker.job_failed", job_id=job.id, kind=kind.value)
            queue.mark_failed(db, job, repr(exc))
            db.commit()
            return True

        queue.mark_succeeded(db, job)
        db.commit()
        log.info("worker.job_succeeded", job_id=job.id, kind=kind.value)
        return True


def _wait_for_notify(timeout: float) -> bool:
    """Block on LISTEN until NOTIFY arrives or timeout. Returns True if notified."""
    settings = get_settings()
    # psycopg 3 — autocommit required for LISTEN
    dsn = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute(f"LISTEN {NOTIFY_CHANNEL}")
            for _ in conn.notifies(timeout=timeout):
                return True
    except Exception:
        log.exception("worker.listen_error")
    return False


def run_loop() -> None:
    import_handlers()
    _install_signal_handlers()
    log.info("worker.start", worker_id=WORKER_ID)

    while not SHUTDOWN.is_set():
        try:
            processed = process_one()
        except Exception:
            log.exception("worker.process_one_error")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        if processed:
            continue
        # Queue empty — wait for NOTIFY or timeout, then loop.
        _wait_for_notify(POLL_INTERVAL_SECONDS)

    log.info("worker.stop", worker_id=WORKER_ID)


if __name__ == "__main__":  # pragma: no cover
    run_loop()
```

> **NOTE**: psycopg 3의 `connect()` 는 표준 PG URL (`postgresql://`) 을 요구. SQLAlchemy의 `postgresql+psycopg://` 접두사는 변환 필요. `get_settings().database_url` 형식에 따라 `_wait_for_notify` 의 변환 로직 조정.

- [ ] **Step 2: 모듈 단위 import 검증 (ruff·import 에러 없는지)**

Run: `python -c "from app.workers.runner import run_loop, process_one; print('ok')"`
Expected: `ok`

Run: `ruff check app/workers/`

- [ ] **Step 3: pytest 통과 (e2e는 Task 20)**

Run: `pytest app/tests/ -q`
Expected: 모든 기존 테스트 그대로 통과.

- [ ] **Step 4: Commit**

```bash
git add app/workers/runner.py
git commit -m "feat(workers): add runner with LISTEN/NOTIFY wait and graceful shutdown"
```

---

## Task 19: systemd unit + docker-compose worker 서비스

**Files:**
- Create: `deploy/systemd/nestory-worker.service`
- Modify: `docker-compose.test.yml`
- Modify: `docker-compose.local.yml` (있다면)

PRD §7.4 v1.1 — 워커 별도 systemd unit. 테스트 환경에도 worker 컨테이너 추가하여 e2e 검증 가능하게 함.

- [ ] **Step 1: systemd unit 작성**

`deploy/systemd/nestory-worker.service`:

```ini
[Unit]
Description=Nestory background job worker (PG-based queue)
After=network.target postgresql.service nestory.service
Wants=postgresql.service

[Service]
Type=simple
User=nestory
Group=nestory
WorkingDirectory=/opt/nestory
EnvironmentFile=/etc/nestory/env
ExecStart=/opt/nestory/.venv/bin/python -m app.workers.runner
Restart=on-failure
RestartSec=5s
KillSignal=SIGTERM
TimeoutStopSec=30s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=nestory-worker

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: docker-compose.test.yml 갱신**

기존 `docker-compose.test.yml` 의 services 섹션에 다음 추가 (app 서비스와 동일 빌드 컨텍스트 재사용):

```yaml
  worker:
    build: .
    command: ["python", "-m", "app.workers.runner"]
    environment:
      DATABASE_URL: postgresql+psycopg://nestory:nestory@postgres:5432/nestory_test
      APP_ENV: test
      SECRET_KEY: test-secret-key
    depends_on:
      postgres:
        condition: service_healthy
      app:
        condition: service_started
    restart: unless-stopped
```

(env 변수는 기존 `app` 서비스와 동일 키 사용. `docker-compose.local.yml` 에도 동일한 worker 서비스 추가 — 단, 로컬에선 폴링 1초가 일반적이라 추가 옵션 불필요.)

- [ ] **Step 3: docker compose build 검증**

Run: `docker compose -f docker-compose.test.yml build worker`
Expected: build success (app 이미지 재사용).

Run: `docker compose -f docker-compose.test.yml up -d`
Run: `docker compose -f docker-compose.test.yml logs worker --tail 20`
Expected: `worker.start worker_id=...` 로그 보임.

Run: `docker compose -f docker-compose.test.yml down`

- [ ] **Step 4: ruff + pytest (smoke)**

Run: `ruff check . && pytest app/tests/ -q`

- [ ] **Step 5: Commit**

```bash
git add deploy/systemd/nestory-worker.service docker-compose.test.yml docker-compose.local.yml
git commit -m "feat(deploy): add nestory-worker systemd unit and compose service"
```

---

## Task 20: e2e — alembic upgrade head + worker round-trip 통합 테스트

**Files:**
- Create: `app/tests/integration/test_worker_e2e.py`

전체 P1.1 데이터 모델·큐·워커가 하나의 파이프라인으로 작동하는지 검증. 실제 워커 프로세스 fork 대신 `process_one()` 을 직접 호출하여 결정적 테스트.

- [ ] **Step 1: e2e 통합 테스트 작성**

`app/tests/integration/test_worker_e2e.py`:

```python
"""End-to-end test: enqueue → dequeue → handler dispatch round-trip.

Calls process_one() directly rather than spawning the runner,
keeping the test deterministic and fast.
"""
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Job
from app.models._enums import JobKind, JobStatus
from app.workers import queue
from app.workers.handlers import import_handlers
from app.workers.runner import process_one


def test_enqueue_then_process_one_marks_succeeded(db: Session) -> None:
    import_handlers()
    queue.enqueue(db, JobKind.IMAGE_RESIZE, {"image_id": 1})
    db.commit()

    processed = process_one()
    assert processed is True

    # Re-fetch via fresh session to bypass identity map
    db.expire_all()
    job = db.query(Job).order_by(Job.id.desc()).first()
    assert job.status == JobStatus.SUCCEEDED
    assert job.completed_at is not None


def test_process_one_returns_false_for_empty_queue(db: Session) -> None:
    import_handlers()
    assert process_one() is False


def test_unknown_kind_marks_dead_eventually(db: Session) -> None:
    """Job with no registered handler — handler raises, job retries to DEAD."""
    import_handlers()
    j = queue.enqueue(db, JobKind.EVIDENCE_CLEANUP, {}, max_attempts=2)
    db.commit()

    # 1st attempt — fail (no handler), gets backoff
    process_one()
    db.expire_all()
    job = db.get(Job, j.id)
    assert job.status == JobStatus.QUEUED
    assert job.attempts == 1

    # Move run_after to past
    job.run_after = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()

    # 2nd attempt — fail again, transitions to DEAD
    process_one()
    db.expire_all()
    job = db.get(Job, j.id)
    assert job.status == JobStatus.DEAD
    assert job.attempts == 2
    assert job.last_error is not None


def test_alembic_head_creates_all_p11_tables(db: Session) -> None:
    """Sanity check — every P1.1 model is reachable as a SQL relation."""
    from sqlalchemy import inspect

    inspector = inspect(db.get_bind())
    tables = set(inspector.get_table_names())
    expected = {
        "users", "regions", "user_interest_regions",
        "images", "journeys", "posts", "post_validations",
        "comments", "tags", "post_tags",
        "post_likes", "post_scraps", "user_follows", "journey_follows",
        "badge_applications", "badge_evidence",
        "notifications", "reports", "audit_logs", "announcements",
        "jobs",
    }
    missing = expected - tables
    assert not missing, f"Missing tables: {missing}"
```

- [ ] **Step 2: 테스트 실행**

Run: `pytest app/tests/integration/test_worker_e2e.py -v`
Expected: 4 passed.

- [ ] **Step 3: 전체 ruff + pytest 회귀**

Run: `ruff check app/ && pytest app/tests/ -q`
Expected: 모든 P1.1 신규 테스트 + Phase 0 38 baseline 모두 통과.

- [ ] **Step 4: 마이그레이션 head 일관성 확인**

Run: `alembic upgrade head` (이미 head이면 no-op)
Run: `alembic current`
Run: `alembic history --verbose | head -30`
Expected: 단일 linear chain (revision 분기 없음).

- [ ] **Step 5: Commit**

```bash
git add app/tests/integration/test_worker_e2e.py
git commit -m "test: add e2e worker round-trip and P1.1 schema completeness check"
```

---

## Self-Review (작성 후 점검)

### 1. Spec coverage

PRD §5.1 (데이터 모델) 모든 엔티티 매핑:

| PRD 엔티티 | Task |
|---|---|
| users (v1.1 갱신) | Task 2 |
| user_interest_regions [v1.1] | Task 3 |
| regions | (Phase 0, 변경 없음) |
| images | Task 4 |
| journeys | Task 5 |
| posts (type=plan 포함) | Task 6 |
| Pydantic Discriminated Union [A3] | Task 7 |
| post_validations [v1.1 · C1] | Task 8 |
| comments | Task 9 |
| tags / post_tags | Task 10 |
| post_likes / post_scraps / user_follows / journey_follows | Task 11 |
| badge_applications / badge_evidence | Task 12 |
| notifications | Task 13 |
| reports / audit_logs / announcements | Task 14 |
| jobs [v1.1 · A1] | Task 15 |
| 작업 큐 워커 (queue/handlers/runner) | Task 16–18 |
| systemd nestory-worker.service | Task 19 |
| e2e + alembic head 검증 | Task 20 |

PRD §6.7 (작업 큐): SKIP LOCKED ✓ · LISTEN/NOTIFY ✓ · 백오프 + DEAD ✓ · 핸들러 레지스트리 ✓ · systemd 별도 unit ✓.

PRD §5.4.1 (재검증): 컬럼만 Task 2에 추가, 실제 transition 로직은 P1.2 (의도된 분리).

PRD §1.5.4 Pillar V: 모델만 Task 8, 메트릭 노출은 P1.3+ (의도된 분리).

### 2. Placeholder scan

- 모든 Step에 실제 코드·명령·기대 출력 포함
- "TBD"·"TODO"·"...similar to" 없음
- 각 Task의 5-step 구조 동일

### 3. Type/이름 일관성

- enum 이름: `_enums.py` 단일 모듈 (`PostType`·`JobKind` 등) → 모든 모델·테스트가 동일 import
- 컬럼 명명: `xxx_id` (FK), `xxx_at` (timestamp), `is_xxx` (bool)
- Mapper 패턴: `Mapped[T]` + `mapped_column(...)` Phase 0 패턴 그대로
- Enum 정의: `Enum(E, name="<snake>", values_callable=lambda x: [e.value for e in x])` + `server_default=E.X.value` 모든 enum 컬럼에 동일 적용
- soft delete: `deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)` Post·Journey·Comment 동일

### 4. 유지보수 측면 점검

- conftest TRUNCATE 자동화 (Task 1) → Task 2–20에서 conftest 수정 불필요
- 모든 모델 Task가 동일 5-step 구조 (모델→마이그레이션→테스트→ruff/pytest→commit)
- 운영 묶음 (interaction.py, moderation.py, badge_application.py) — 의미 응집 시 한 모듈에 묶음, 단순 패턴은 단일 모델 per 파일
- Alembic 마이그레이션은 Task당 1개 — `git log` 에서 추적 쉬움
- 커밋 prefix 일관: `feat(models):` / `feat(workers):` / `feat(deploy):` / `test:`
- Task 4↔6의 보류 FK 처리: 명시적 NOTE로 추적

### 5. 잔여 / 후속

- factory-boy 기반 `app/tests/factories/` — pyproject에 의존성은 있으나 P1.1엔 미도입. 각 테스트의 `_seed_*` 헬퍼가 중복. **P1.2 시작 전 별도 정비 Task 권장**: factories 도입 + 기존 _seed 함수 정리 (~5 step). 일관성 부채 명시적 기록.
- Repository 레이어: P1.1엔 미포함. 라우트가 본격 시작되는 P1.3에서 도메인별 repository 패턴 결정.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-06-nestory-phase1-1-data-model-and-job-queue.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — 각 Task를 fresh subagent로 dispatch, Task 사이에 리뷰. 빠른 반복·메인 컨텍스트 보호.

**2. Inline Execution** — 이 세션에서 executing-plans 스킬로 Task 그룹별 batch 실행 + 체크포인트.

**Which approach?**
