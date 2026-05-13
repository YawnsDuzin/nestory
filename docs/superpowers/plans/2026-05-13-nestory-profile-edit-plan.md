# Profile Edit (Tier A+B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사용자가 자신의 프로필(사진·display_name·bio·관심지역·알림 설정)과 계정(username·비밀번호)을 편집할 수 있는 `/me/profile` 화면 그룹을 추가. PRD V축(Peer Validation) 강화 + P1.5 알림 동의 컬럼 사전 확보.

**Architecture:** User 모델에 4개 컬럼(`avatar_image_id`·`username_changed_at`·`notify_email_enabled`·`notify_kakao_enabled`) 추가, `app/services/profile.py`에 5개 service 함수 + 4개 도메인 예외 정의, `app/routers/me.py`에 8개 라우트 확장(4 GET + 4 POST), `app/templates/pages/me/profile/`에 5개 템플릿 신규. 사진 업로드는 P1.3 `images_service.upload_image` 그대로 재사용. 카카오 가입자(`password_hash IS NULL`)는 비번 변경 라우트에서 분기 처리.

**Tech Stack:** Python 3.12, FastAPI, Jinja2, SQLAlchemy 2.x, alembic, pytest + factory-boy, argon2 (auth), PIL (P1.3 image pipeline). PostgreSQL 16 (host port 5433 — Docker 또는 사용자 host config).

**관련 spec**: [docs/superpowers/specs/2026-05-13-nestory-profile-edit-design.md](../specs/2026-05-13-nestory-profile-edit-design.md)

---

## File Structure

| 파일 | 동작 | 책임 |
|---|---|---|
| `app/models/user.py` | Modify | 4 신규 Mapped 컬럼 추가 |
| `app/db/migrations/versions/<rev>_add_profile_edit_columns_to_users.py` | Create | alembic autogenerate (parent: `f493042da765`) |
| `app/services/profile.py` | Create | 5 service 함수 + `ProfileError` base + `UsernameTakenError`·`UsernameThrottledError`·`PasswordChangeNotAllowed`·`AvatarOwnershipError` |
| `app/schemas/profile.py` | Create | `ProfileRead` Pydantic 응답 스키마 (네이티브 JSON API 대비) |
| `app/templates/components/_avatar.html` | Modify | 사진/이니셜 분기 추가 (`<img>` if `avatar_image_id`, else 기존 이니셜) |
| `app/routers/me.py` | Modify | 8 신규 라우트 (`/profile`·`/profile/avatar`·`/profile/avatar/delete`·`/profile/username`·`/profile/password` × GET/POST) |
| `app/templates/pages/me/profile/edit.html` | Create | 메인 편집 페이지 (4 섹션 + 사진 + flash) |
| `app/templates/pages/me/profile/_avatar_card.html` | Create | 사진 표시 + 업로드/제거 버튼 partial |
| `app/templates/pages/me/profile/_basic_form.html` | Create | display_name·bio·region·알림 설정 form partial |
| `app/templates/pages/me/profile/username.html` | Create | 사용자명 변경 페이지 (throttle 안내) |
| `app/templates/pages/me/profile/password.html` | Create | 비번 변경 페이지 (카카오 분기) |
| `app/tests/unit/test_profile_service.py` | Create | 5 service 함수 unit 테스트 (~14 cases) |
| `app/tests/integration/test_me_profile_routes.py` | Create | 8 라우트 integration 테스트 (~12 cases) |

**spec과 중복 확인된 사실**:
- `images_service.upload_image(db, owner, file)` 시그니처 [app/services/images.py:134](../../app/services/images.py#L134) — owner_id 자동 설정
- `auth.hash_password` / `auth.verify_password` [app/services/auth.py:22-28](../../app/services/auth.py#L22) — 그대로 사용
- 현재 alembic head: `f493042da765`
- Flash helper 모듈 없음 — `request.session["flash"]` 직접 사용 (spec §15 Open Q 권고)

---

## Pre-flight: 환경 점검

- [ ] **Step 1: Postgres + alembic head 확인**

Run: `uv run alembic current 2>&1 | tail -1`
Expected: `f493042da765 (head)`. 다른 head라면 brand-new 마이그레이션이 추가되었으므로 plan의 parent revision 갱신 필요.

- [ ] **Step 2: 베이스라인 pytest 통과 확인**

Run: `uv run pytest app/tests/ -q --tb=no`
Expected: 554 PASS / 2 pre-existing failures (`test_feed_pagination_query_param`, `test_hub_pagination_query_param`). 추가 실패 발생 시 본 plan과 무관해도 먼저 보고.

- [ ] **Step 3: 현재 브랜치 + uncommitted 확인**

Run: `git status --short && git branch --show-current`
Expected: branch `dev`. 사용자의 in-progress 변경(예: `M CLAUDE.md`)은 건드리지 말 것.

---

## Task 1: User 모델 4 컬럼 추가 + alembic 마이그레이션

**Files:**
- Modify: `app/models/user.py`
- Create: `app/db/migrations/versions/<rev>_add_profile_edit_columns_to_users.py` (alembic autogenerate)

- [ ] **Step 1: User 모델 컬럼 추가**

[app/models/user.py](../../app/models/user.py) 의 `User` 클래스에 다음 4개 필드 추가. `last_login_at` 다음 줄(line 58 부근)이 자연스러운 위치 — 이미 `from datetime import datetime` 와 `DateTime`/`ForeignKey` 등 imports 있음. **`Boolean` 은 없으므로 sqlalchemy import에 추가**:

```python
from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
```

User 클래스 본문 (`last_login_at` 뒤, `created_at` 앞 위치 권고):

```python
    avatar_image_id: Mapped[int | None] = mapped_column(
        ForeignKey("images.id", ondelete="SET NULL"), nullable=True, index=True
    )
    username_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notify_email_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    notify_kakao_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
```

- [ ] **Step 2: alembic autogenerate 마이그레이션 생성**

Run: `uv run alembic revision --autogenerate -m "add profile edit columns to users"`
Expected: `app/db/migrations/versions/<random>_add_profile_edit_columns_to_users.py` 파일 생성. 출력에서 "Detected added column"/"Detected added foreign key" 라인 확인.

- [ ] **Step 3: autogenerate 결과 검증 + 보정**

생성된 마이그레이션 파일을 열어 `def upgrade()` 본문이 다음 형태인지 확인 (정확한 line 순서·index 이름은 alembic이 자동 결정):

```python
def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_image_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("username_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users",
        sa.Column("notify_email_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("notify_kakao_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index(op.f("ix_users_avatar_image_id"), "users", ["avatar_image_id"], unique=False)
    op.create_foreign_key(None, "users", "images", ["avatar_image_id"], ["id"], ondelete="SET NULL")
```

`def downgrade()` 본문이 역순 + drop 형태인지 확인 (drop_constraint·drop_index·drop_column).

검증 항목:
- ① `def upgrade()` 본문이 `pass` 아님 (CLAUDE.md "마이그레이션 패턴" 규약)
- ② `import sqlalchemy as sa` 라인 존재
- ③ FK ON DELETE SET NULL 설정됨
- ④ `notify_*` 두 컬럼 모두 `server_default` + `nullable=False`

만약 autogenerate가 한 가지라도 누락하면 직접 수정 (보통 누락 없음).

- [ ] **Step 4: ruff fix (UP007 등)**

Run: `uv run ruff check --fix app/db/migrations/versions/`
Expected: `Found N error(s) (N fixed, ...)` 또는 `All checks passed!`. 마이그레이션 디렉토리 per-file-ignores가 일부 룰만 무시함.

- [ ] **Step 5: 마이그레이션 적용 + 컬럼 확인**

Run: `uv run alembic upgrade head` 후 `docker exec nestory-postgres-local psql -U nestory -d nestory -c "\d users" | grep -E "avatar_image_id|username_changed_at|notify_email|notify_kakao"`

(사용자 환경이 host Postgres 5432인 경우 `psql -h localhost -p 5432 -U nestory -d nestory -c "\d users"`로 대체)

Expected: 4개 컬럼 모두 출력. 타입·nullable·default 확인.

- [ ] **Step 6: alembic chain 무결성**

Run: `uv run alembic history --verbose | head -10`
Expected: 신규 revision이 `f493042da765` 를 down_revision으로 가지며 head로 표시. branching 없음.

- [ ] **Step 7: Lint**

Run: `uv run ruff check app/models/user.py app/db/migrations/versions/`
Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
git add app/models/user.py app/db/migrations/versions/
git commit -m "feat(models): add profile edit columns to users (avatar/username_changed_at/notify_*)"
```

---

## Task 2: 도메인 예외 + Service 스켈레톤 + Pydantic ProfileRead

**Files:**
- Create: `app/services/profile.py`
- Create: `app/schemas/profile.py`

본 task는 후속 Task 3-6에서 채울 service의 빈 함수 + 4개 예외 + Pydantic 스키마만 정의 (TDD를 위한 placeholder 함수 본문은 `raise NotImplementedError`).

- [ ] **Step 1: `app/schemas/profile.py` 생성**

```python
"""Pydantic schemas for profile read/write — used by HTML form routes today,
JSON API tomorrow. See spec §4.3."""
from pydantic import BaseModel, ConfigDict


class ProfileRead(BaseModel):
    """User profile snapshot. Used by GET /me/profile JSON API in P2+."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    bio: str | None
    avatar_image_id: int | None
    primary_region_id: int | None
    notify_email_enabled: bool
    notify_kakao_enabled: bool
```

- [ ] **Step 2: `app/services/profile.py` 생성**

```python
"""User profile editing — display_name/bio/region/avatar/username/password.
See spec/2026-05-13-nestory-profile-edit-design.md."""
from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Image, Region, User
from app.services import auth

USERNAME_CHANGE_THROTTLE_DAYS = 30
USERNAME_PATTERN = re.compile(r"^[a-z0-9_-]{3,32}$")
PASSWORD_MIN_LENGTH = 8
DISPLAY_NAME_MAX = 64
BIO_MAX = 500


class ProfileError(Exception):
    """Base exception for profile service errors."""


class UsernameTakenError(ProfileError):
    def __init__(self, username: str):
        self.username = username
        super().__init__(f"이미 사용 중인 사용자명입니다: {username}")


class UsernameThrottledError(ProfileError):
    """Username changed within last 30 days."""

    def __init__(self, days_remaining: int):
        self.days_remaining = days_remaining
        super().__init__(f"사용자명 변경은 {days_remaining}일 후 가능합니다")


class PasswordChangeNotAllowed(ProfileError):
    """Kakao OAuth users have no password to change."""

    def __init__(self):
        super().__init__("카카오 계정은 비밀번호 변경이 불가합니다")


class AvatarOwnershipError(ProfileError):
    """User attempted to set avatar to an Image they don't own."""

    def __init__(self):
        super().__init__("본인 소유 이미지가 아닙니다")


def update_profile_basic(
    db: Session,
    user: User,
    *,
    display_name: str,
    bio: str | None,
    primary_region_id: int | None,
    notify_email_enabled: bool,
    notify_kakao_enabled: bool,
) -> User:
    """Update display_name/bio/region/notify settings. flush only — caller commits."""
    raise NotImplementedError


def set_avatar(db: Session, user: User, image: Image) -> User:
    """Set user.avatar_image_id. Raises AvatarOwnershipError if image.owner_id != user.id."""
    raise NotImplementedError


def clear_avatar(db: Session, user: User) -> User:
    """Set user.avatar_image_id to None. Old Image row is preserved (orphan GC = P2)."""
    raise NotImplementedError


def change_username(db: Session, user: User, *, new_username: str) -> User:
    """Validate + apply new username. Raises UsernameThrottledError, UsernameTakenError, ProfileError."""
    raise NotImplementedError


def change_password(
    db: Session, user: User, *, current_password: str, new_password: str
) -> User:
    """Verify current + apply new hash. Raises PasswordChangeNotAllowed (kakao), ProfileError."""
    raise NotImplementedError


__all__ = [
    "AvatarOwnershipError",
    "BIO_MAX",
    "DISPLAY_NAME_MAX",
    "PASSWORD_MIN_LENGTH",
    "PasswordChangeNotAllowed",
    "ProfileError",
    "USERNAME_CHANGE_THROTTLE_DAYS",
    "USERNAME_PATTERN",
    "UsernameTakenError",
    "UsernameThrottledError",
    "change_password",
    "change_username",
    "clear_avatar",
    "set_avatar",
    "update_profile_basic",
]
```

(`ProfileRead`는 `app/schemas/profile.py`에서만 정의·export — services/profile.py의 `__all__`에 포함 X.)

- [ ] **Step 3: 임포트 가능 확인**

Run: `uv run python -c "from app.services import profile; from app.schemas.profile import ProfileRead; print('OK', dir(profile)[:5])"`
Expected: `OK [...]` 출력. import 에러 없음.

- [ ] **Step 4: Lint**

Run: `uv run ruff check app/services/profile.py app/schemas/profile.py`
Expected: `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add app/services/profile.py app/schemas/profile.py
git commit -m "feat(profile): add service skeleton + 4 domain exceptions + ProfileRead schema"
```

---

## Task 3: `update_profile_basic` 구현 (TDD)

**Files:**
- Create: `app/tests/unit/test_profile_service.py`
- Modify: `app/services/profile.py`

- [ ] **Step 1: Write the failing tests**

신규 파일 `app/tests/unit/test_profile_service.py`:

```python
"""Unit tests for app.services.profile — uses real DB session via factories."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.services import profile
from app.tests.factories import RegionFactory, UserFactory


def test_update_profile_basic_happy(db: Session) -> None:
    region = RegionFactory(slug="profile-basic-region")
    user = UserFactory(display_name="원래이름", bio=None)
    db.flush()

    updated = profile.update_profile_basic(
        db, user,
        display_name="  새 이름  ",  # trimmed
        bio="자기소개입니다",
        primary_region_id=region.id,
        notify_email_enabled=False,
        notify_kakao_enabled=True,
    )

    assert updated.display_name == "새 이름"
    assert updated.bio == "자기소개입니다"
    assert updated.primary_region_id == region.id
    assert updated.notify_email_enabled is False
    assert updated.notify_kakao_enabled is True


def test_update_profile_basic_allows_none_bio_and_region(db: Session) -> None:
    user = UserFactory(display_name="초기이름")
    db.flush()
    updated = profile.update_profile_basic(
        db, user,
        display_name="이름",
        bio=None,
        primary_region_id=None,
        notify_email_enabled=True,
        notify_kakao_enabled=False,
    )
    assert updated.bio is None
    assert updated.primary_region_id is None


def test_update_profile_basic_rejects_blank_display_name(db: Session) -> None:
    user = UserFactory(display_name="기존")
    db.flush()
    with pytest.raises(profile.ProfileError):
        profile.update_profile_basic(
            db, user,
            display_name="   ",
            bio=None,
            primary_region_id=None,
            notify_email_enabled=True,
            notify_kakao_enabled=False,
        )


def test_update_profile_basic_rejects_too_long_display_name(db: Session) -> None:
    user = UserFactory()
    db.flush()
    with pytest.raises(profile.ProfileError):
        profile.update_profile_basic(
            db, user,
            display_name="가" * 65,  # > DISPLAY_NAME_MAX (64)
            bio=None,
            primary_region_id=None,
            notify_email_enabled=True,
            notify_kakao_enabled=False,
        )


def test_update_profile_basic_rejects_too_long_bio(db: Session) -> None:
    user = UserFactory()
    db.flush()
    with pytest.raises(profile.ProfileError):
        profile.update_profile_basic(
            db, user,
            display_name="이름",
            bio="가" * 501,  # > BIO_MAX (500)
            primary_region_id=None,
            notify_email_enabled=True,
            notify_kakao_enabled=False,
        )


def test_update_profile_basic_rejects_invalid_region(db: Session) -> None:
    user = UserFactory()
    db.flush()
    with pytest.raises(profile.ProfileError):
        profile.update_profile_basic(
            db, user,
            display_name="이름",
            bio=None,
            primary_region_id=999_999,  # 존재하지 않는 region
            notify_email_enabled=True,
            notify_kakao_enabled=False,
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/unit/test_profile_service.py -v`
Expected: 6개 모두 `NotImplementedError` FAIL.

- [ ] **Step 3: Implement `update_profile_basic`**

`app/services/profile.py` 의 `update_profile_basic` 본문 교체:

```python
def update_profile_basic(
    db: Session,
    user: User,
    *,
    display_name: str,
    bio: str | None,
    primary_region_id: int | None,
    notify_email_enabled: bool,
    notify_kakao_enabled: bool,
) -> User:
    """Update display_name/bio/region/notify settings. flush only — caller commits."""
    name = display_name.strip()
    if not name:
        raise ProfileError("표시 이름을 입력해 주세요")
    if len(name) > DISPLAY_NAME_MAX:
        raise ProfileError(f"표시 이름은 {DISPLAY_NAME_MAX}자 이하")

    bio_value: str | None = None
    if bio is not None:
        bio_stripped = bio.strip()
        if len(bio_stripped) > BIO_MAX:
            raise ProfileError(f"자기소개는 {BIO_MAX}자 이하")
        bio_value = bio_stripped or None  # 빈 문자열은 None으로 정규화

    region_id: int | None = None
    if primary_region_id is not None:
        region = db.get(Region, primary_region_id)
        if region is None:
            raise ProfileError("유효하지 않은 지역")
        region_id = region.id

    user.display_name = name
    user.bio = bio_value
    user.primary_region_id = region_id
    user.notify_email_enabled = bool(notify_email_enabled)
    user.notify_kakao_enabled = bool(notify_kakao_enabled)
    db.flush()
    return user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest app/tests/unit/test_profile_service.py -v`
Expected: 6개 모두 PASS.

- [ ] **Step 5: Lint**

Run: `uv run ruff check app/services/profile.py app/tests/unit/test_profile_service.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add app/services/profile.py app/tests/unit/test_profile_service.py
git commit -m "feat(profile): implement update_profile_basic + unit tests"
```

---

## Task 4: `set_avatar` + `clear_avatar` 구현 (TDD)

**Files:**
- Modify: `app/services/profile.py`
- Modify: `app/tests/unit/test_profile_service.py`

- [ ] **Step 1: Write the failing tests**

`app/tests/unit/test_profile_service.py` 끝에 추가:

```python
from app.tests.factories import ImageFactory


def test_set_avatar_happy(db: Session) -> None:
    user = UserFactory()
    image = ImageFactory(owner=user)
    db.flush()

    updated = profile.set_avatar(db, user, image)
    assert updated.avatar_image_id == image.id


def test_set_avatar_rejects_other_users_image(db: Session) -> None:
    owner = UserFactory()
    intruder = UserFactory()
    image = ImageFactory(owner=owner)
    db.flush()

    with pytest.raises(profile.AvatarOwnershipError):
        profile.set_avatar(db, intruder, image)


def test_clear_avatar_when_set(db: Session) -> None:
    user = UserFactory()
    image = ImageFactory(owner=user)
    db.flush()
    user.avatar_image_id = image.id
    db.flush()

    updated = profile.clear_avatar(db, user)
    assert updated.avatar_image_id is None


def test_clear_avatar_when_already_none(db: Session) -> None:
    user = UserFactory()
    db.flush()
    updated = profile.clear_avatar(db, user)
    assert updated.avatar_image_id is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/unit/test_profile_service.py -k "avatar" -v`
Expected: 4개 모두 `NotImplementedError` FAIL.

- [ ] **Step 3: Implement `set_avatar` + `clear_avatar`**

`app/services/profile.py` 함수 본문 교체:

```python
def set_avatar(db: Session, user: User, image: Image) -> User:
    """Set user.avatar_image_id. Raises AvatarOwnershipError if image.owner_id != user.id."""
    if image.owner_id != user.id:
        raise AvatarOwnershipError()
    user.avatar_image_id = image.id
    db.flush()
    return user


def clear_avatar(db: Session, user: User) -> User:
    """Set user.avatar_image_id to None. Old Image row is preserved (orphan GC = P2)."""
    user.avatar_image_id = None
    db.flush()
    return user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest app/tests/unit/test_profile_service.py -v`
Expected: 10개 (Task 3의 6개 + 본 task 4개) 모두 PASS.

- [ ] **Step 5: Lint**

Run: `uv run ruff check app/services/profile.py app/tests/unit/test_profile_service.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add app/services/profile.py app/tests/unit/test_profile_service.py
git commit -m "feat(profile): implement set_avatar/clear_avatar with ownership check"
```

---

## Task 5: `change_username` 구현 (TDD — throttle/dup/pattern)

**Files:**
- Modify: `app/services/profile.py`
- Modify: `app/tests/unit/test_profile_service.py`

- [ ] **Step 1: Write the failing tests**

`app/tests/unit/test_profile_service.py` 끝에 추가:

```python
def test_change_username_happy(db: Session) -> None:
    user = UserFactory(username="oldname")
    db.flush()
    before = datetime.now(UTC)
    updated = profile.change_username(db, user, new_username="newname")
    assert updated.username == "newname"
    assert updated.username_changed_at is not None
    assert updated.username_changed_at >= before


def test_change_username_normalizes_to_lowercase(db: Session) -> None:
    user = UserFactory(username="oldname")
    db.flush()
    updated = profile.change_username(db, user, new_username="  NewName  ")
    assert updated.username == "newname"


def test_change_username_no_op_when_same(db: Session) -> None:
    """Same username (after normalization) — no-op, no throttle update."""
    user = UserFactory(username="samename", username_changed_at=None)
    db.flush()
    updated = profile.change_username(db, user, new_username="SameName")
    assert updated.username == "samename"
    assert updated.username_changed_at is None  # not touched


def test_change_username_rejects_invalid_pattern(db: Session) -> None:
    user = UserFactory()
    db.flush()
    for bad in ("ab", "Has-UPPER", "with spaces", "한글이름", "a" * 33):
        with pytest.raises(profile.ProfileError):
            profile.change_username(db, user, new_username=bad)


def test_change_username_rejects_duplicate(db: Session) -> None:
    UserFactory(username="taken")
    user = UserFactory(username="mine")
    db.flush()
    with pytest.raises(profile.UsernameTakenError):
        profile.change_username(db, user, new_username="taken")


def test_change_username_within_throttle_window_rejected(db: Session) -> None:
    user = UserFactory(
        username="oldname",
        username_changed_at=datetime.now(UTC) - timedelta(days=10),
    )
    db.flush()
    with pytest.raises(profile.UsernameThrottledError) as exc_info:
        profile.change_username(db, user, new_username="newname")
    # 30 - 10 = 20 days remaining (allow ±1 day for test execution drift)
    assert 19 <= exc_info.value.days_remaining <= 21


def test_change_username_after_throttle_window_allowed(db: Session) -> None:
    user = UserFactory(
        username="oldname",
        username_changed_at=datetime.now(UTC) - timedelta(days=31),
    )
    db.flush()
    updated = profile.change_username(db, user, new_username="newname")
    assert updated.username == "newname"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/unit/test_profile_service.py -k "username" -v`
Expected: 7개 모두 `NotImplementedError` FAIL.

- [ ] **Step 3: Implement `change_username`**

`app/services/profile.py` 의 `change_username` 함수 본문 교체:

```python
def change_username(db: Session, user: User, *, new_username: str) -> User:
    """Validate + apply new username. Raises UsernameThrottledError, UsernameTakenError, ProfileError."""
    normalized = new_username.strip().lower()
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise ProfileError(
            "사용자명은 3-32자, 영소문자·숫자·_·- 만 사용할 수 있습니다"
        )
    if normalized == user.username:
        return user  # no-op — throttle 미적용
    if user.username_changed_at is not None:
        elapsed = (datetime.now(UTC) - user.username_changed_at).days
        if elapsed < USERNAME_CHANGE_THROTTLE_DAYS:
            raise UsernameThrottledError(USERNAME_CHANGE_THROTTLE_DAYS - elapsed)
    exists = db.scalar(select(User.id).where(User.username == normalized))
    if exists is not None:
        raise UsernameTakenError(normalized)
    user.username = normalized
    user.username_changed_at = datetime.now(UTC)
    db.flush()
    return user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest app/tests/unit/test_profile_service.py -v`
Expected: 17개 (Task 3-4 + 본 task 7개) 모두 PASS.

- [ ] **Step 5: Lint**

Run: `uv run ruff check app/services/profile.py app/tests/unit/test_profile_service.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add app/services/profile.py app/tests/unit/test_profile_service.py
git commit -m "feat(profile): implement change_username with 30-day throttle"
```

---

## Task 6: `change_password` 구현 (TDD — kakao guard, current verify, length)

**Files:**
- Modify: `app/services/profile.py`
- Modify: `app/tests/unit/test_profile_service.py`

- [ ] **Step 1: Write the failing tests**

`app/tests/unit/test_profile_service.py` 끝에 추가:

```python
from app.services import auth as auth_service


def test_change_password_happy(db: Session) -> None:
    user = UserFactory(password_hash=auth_service.hash_password("oldPassword!"))
    db.flush()
    updated = profile.change_password(
        db, user,
        current_password="oldPassword!",
        new_password="newPassword!",
    )
    assert auth_service.verify_password("newPassword!", updated.password_hash) is True
    assert auth_service.verify_password("oldPassword!", updated.password_hash) is False


def test_change_password_rejects_kakao_user(db: Session) -> None:
    """Kakao OAuth user has password_hash=None — change must be denied."""
    user = UserFactory(password_hash=None, kakao_id="kakao_abc123")
    db.flush()
    with pytest.raises(profile.PasswordChangeNotAllowed):
        profile.change_password(
            db, user,
            current_password="anything",
            new_password="newPassword!",
        )


def test_change_password_rejects_wrong_current(db: Session) -> None:
    user = UserFactory(password_hash=auth_service.hash_password("realPassword"))
    db.flush()
    with pytest.raises(profile.ProfileError):
        profile.change_password(
            db, user,
            current_password="wrongPassword",
            new_password="newPassword!",
        )


def test_change_password_rejects_short_new(db: Session) -> None:
    user = UserFactory(password_hash=auth_service.hash_password("realPassword"))
    db.flush()
    with pytest.raises(profile.ProfileError):
        profile.change_password(
            db, user,
            current_password="realPassword",
            new_password="short",  # < PASSWORD_MIN_LENGTH (8)
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest app/tests/unit/test_profile_service.py -k "password" -v`
Expected: 4개 모두 `NotImplementedError` FAIL.

- [ ] **Step 3: Implement `change_password`**

`app/services/profile.py` 의 `change_password` 함수 본문 교체:

```python
def change_password(
    db: Session, user: User, *, current_password: str, new_password: str
) -> User:
    """Verify current + apply new hash. Raises PasswordChangeNotAllowed (kakao), ProfileError."""
    if user.password_hash is None:
        raise PasswordChangeNotAllowed()
    if not auth.verify_password(current_password, user.password_hash):
        raise ProfileError("현재 비밀번호가 일치하지 않습니다")
    if len(new_password) < PASSWORD_MIN_LENGTH:
        raise ProfileError(f"비밀번호는 최소 {PASSWORD_MIN_LENGTH}자 이상")
    user.password_hash = auth.hash_password(new_password)
    db.flush()
    return user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest app/tests/unit/test_profile_service.py -v`
Expected: 21개 (Task 3-5 + 본 task 4개) 모두 PASS.

- [ ] **Step 5: Lint**

Run: `uv run ruff check app/services/profile.py app/tests/unit/test_profile_service.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add app/services/profile.py app/tests/unit/test_profile_service.py
git commit -m "feat(profile): implement change_password with kakao guard + current verify"
```

---

## Task 7: `_avatar.html` macro 사진 분기 추가

**Files:**
- Modify: `app/templates/components/_avatar.html`

- [ ] **Step 1: Replace macro body**

[app/templates/components/_avatar.html](../../app/templates/components/_avatar.html) 파일 전체를 다음으로 교체:

```jinja
{# Threads-style 동그란 아바타. 사진 있으면 <img>, 없으면 이니셜.
   사용:
   {% from "components/_avatar.html" import avatar %}
   {{ avatar(post.author, 40) }}
   유저 없을 때(익명·삭제)도 안전. #}
{% macro avatar(user, size=40) -%}
  {% set classes = {
    28: "h-7 w-7 text-xs",
    32: "h-8 w-8 text-sm",
    36: "h-9 w-9 text-sm",
    40: "h-10 w-10 text-sm",
    44: "h-11 w-11 text-base",
    48: "h-12 w-12 text-base",
    56: "h-14 w-14 text-lg",
  }.get(size, "h-10 w-10 text-sm") %}
  {% if user and user.avatar_image_id %}
    <img src="/img/{{ user.avatar_image_id }}/medium"
         alt=""
         loading="lazy"
         class="inline-flex shrink-0 rounded-full object-cover bg-stone-100 {{ classes }}">
  {% else %}
    {% set letter = (user.username[:1] | upper) if user and user.username else "?" %}
    <span class="inline-flex shrink-0 items-center justify-center rounded-full bg-emerald-600 font-semibold text-white {{ classes }}"
          aria-hidden="true">{{ letter }}</span>
  {% endif %}
{%- endmacro %}
```

- [ ] **Step 2: Jinja syntax 검증**

Run: `uv run python -c "from app.templating import templates; templates.get_template('components/_avatar.html'); print('OK')"`
Expected: `OK` 출력. (Jinja parse 성공.)

- [ ] **Step 3: 회귀 — macro 사용 페이지 렌더 sanity**

Run: `uv run python -c "from app.templating import templates; templates.get_template('pages/home.html'); templates.get_template('partials/post_card.html'); print('OK')"`
Expected: `OK` (avatar macro를 import하는 다른 템플릿들도 정상 parse).

- [ ] **Step 4: Lint**

Run: `uv run ruff check app/templates/`
Expected: `All checks passed!` (templates에 .py 없음, noop이지만 안전).

- [ ] **Step 5: Commit**

```bash
git add app/templates/components/_avatar.html
git commit -m "feat(ui): _avatar macro renders user.avatar_image_id when set, else initial"
```

---

## Task 8: 4 GET 라우트 + 5 템플릿 (edit · _avatar_card · _basic_form · username · password)

**Files:**
- Modify: `app/routers/me.py`
- Create: `app/templates/pages/me/profile/edit.html`
- Create: `app/templates/pages/me/profile/_avatar_card.html`
- Create: `app/templates/pages/me/profile/_basic_form.html`
- Create: `app/templates/pages/me/profile/username.html`
- Create: `app/templates/pages/me/profile/password.html`

본 task는 GET 라우트만 (기능 동작 안 함, 폼 표시만). POST는 Task 9.

- [ ] **Step 1: 4 GET 라우트 추가**

[app/routers/me.py](../../app/routers/me.py) 파일 끝에 추가 (기존 `/badge*` 라우트 뒤):

```python
from app.services import regions as regions_service  # 이미 import됨 — 재사용 OK


@router.get("/profile", response_class=HTMLResponse)
def profile_edit_page(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    regions = regions_service.list_all_for_dropdown(db)
    return templates.TemplateResponse(
        request,
        "pages/me/profile/edit.html",
        {"current_user": user, "regions": regions},
    )


@router.get("/profile/username", response_class=HTMLResponse)
def profile_username_page(
    request: Request,
    user: User = Depends(require_user),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "pages/me/profile/username.html",
        {"current_user": user},
    )


@router.get("/profile/password", response_class=HTMLResponse)
def profile_password_page(
    request: Request,
    user: User = Depends(require_user),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "pages/me/profile/password.html",
        {"current_user": user},
    )
```

(Note: avatar 는 별도 GET 페이지 없음 — `edit.html` 안의 `_avatar_card.html` partial 로 통합 표시. avatar GET 라우트 불필요.)

- [ ] **Step 2: `edit.html` 템플릿 생성**

```jinja
{% extends "base.html" %}
{% block title %}프로필 편집 · Nestory{% endblock %}
{% block content %}
<div class="space-y-6 max-w-2xl mx-auto py-8 px-4">
  <h1 class="text-2xl font-bold text-stone-900">프로필 편집</h1>

  {% set _flash = request.session.pop("flash", None) %}
  {% if _flash %}
    <div class="rounded bg-emerald-50 p-3 text-emerald-800 text-sm">{{ _flash }}</div>
  {% endif %}

  <section class="space-y-3 border-b border-stone-200 pb-6">
    <h2 class="font-semibold text-stone-900">프로필 사진</h2>
    {% include "pages/me/profile/_avatar_card.html" %}
  </section>

  <section class="space-y-3 border-b border-stone-200 pb-6">
    <h2 class="font-semibold text-stone-900">기본 정보</h2>
    {% include "pages/me/profile/_basic_form.html" %}
  </section>

  <section class="space-y-3 border-b border-stone-200 pb-6">
    <h2 class="font-semibold text-stone-900">사용자명</h2>
    <p class="text-sm text-stone-600">현재 — <code class="rounded bg-stone-100 px-1.5 py-0.5">@{{ current_user.username }}</code></p>
    <a href="/me/profile/username" class="text-sm text-emerald-700 hover:underline">변경하기 →</a>
  </section>

  <section class="space-y-3">
    <h2 class="font-semibold text-stone-900">비밀번호</h2>
    {% if current_user.password_hash %}
      <a href="/me/profile/password" class="text-sm text-emerald-700 hover:underline">변경하기 →</a>
    {% else %}
      <p class="text-sm text-stone-500">카카오 계정으로 가입하셨습니다 — 비밀번호 미사용</p>
    {% endif %}
  </section>
</div>
{% endblock %}
```

- [ ] **Step 3: `_avatar_card.html` partial 생성**

```jinja
{% from "components/_avatar.html" import avatar %}

<div class="flex items-center gap-4">
  {{ avatar(current_user, 56) }}

  <div class="flex flex-col gap-2">
    <form action="/me/profile/avatar" method="post" enctype="multipart/form-data" class="flex items-center gap-2">
      <input type="file" name="image" accept="image/jpeg,image/png,image/webp" required
             class="text-sm">
      <button type="submit" class="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-700">
        사진 변경
      </button>
    </form>

    {% if current_user.avatar_image_id %}
      <form action="/me/profile/avatar/delete" method="post">
        <button type="submit" class="text-sm text-stone-500 hover:underline">사진 제거</button>
      </form>
    {% endif %}
  </div>
</div>
```

- [ ] **Step 4: `_basic_form.html` partial 생성**

```jinja
<form action="/me/profile" method="post" class="space-y-4">
  <label class="block">
    <span class="text-sm text-stone-700">표시 이름</span>
    <input type="text" name="display_name" value="{{ current_user.display_name }}"
           required maxlength="64"
           class="mt-1 w-full rounded border border-stone-300 px-3 py-2 focus:border-emerald-500 focus:outline-none">
  </label>

  <label class="block">
    <span class="text-sm text-stone-700">자기소개 <span class="text-stone-400">(500자 이내)</span></span>
    <textarea name="bio" rows="4" maxlength="500"
              class="mt-1 w-full rounded border border-stone-300 px-3 py-2 focus:border-emerald-500 focus:outline-none">{{ current_user.bio or "" }}</textarea>
  </label>

  <label class="block">
    <span class="text-sm text-stone-700">관심 시군 <span class="text-stone-400">(선택)</span></span>
    <select name="primary_region_id"
            class="mt-1 w-full rounded border border-stone-300 px-3 py-2 focus:border-emerald-500 focus:outline-none">
      <option value="">선택 안 함</option>
      {% for region in regions %}
        <option value="{{ region.id }}"
                {% if current_user.primary_region_id == region.id %}selected{% endif %}>
          {{ region.sido }} {{ region.sigungu }}
        </option>
      {% endfor %}
    </select>
  </label>

  <fieldset class="space-y-2">
    <legend class="text-sm font-medium text-stone-700">알림 수신</legend>
    <label class="flex items-center gap-2">
      <input type="checkbox" name="notify_email_enabled" value="1"
             {% if current_user.notify_email_enabled %}checked{% endif %}>
      <span class="text-sm">이메일</span>
    </label>
    <label class="flex items-center gap-2">
      <input type="checkbox" name="notify_kakao_enabled" value="1"
             {% if current_user.notify_kakao_enabled %}checked{% endif %}>
      <span class="text-sm">카카오 알림톡 <span class="text-stone-400">(별도 비용 발생 가능)</span></span>
    </label>
  </fieldset>

  <button type="submit" class="rounded bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700">
    저장
  </button>
</form>
```

- [ ] **Step 5: `username.html` 페이지 생성**

```jinja
{% extends "base.html" %}
{% block title %}사용자명 변경 · Nestory{% endblock %}
{% block content %}
<div class="max-w-md mx-auto py-8 px-4 space-y-4">
  <h1 class="text-2xl font-bold text-stone-900">사용자명 변경</h1>

  {% set _flash = request.session.pop("flash", None) %}
  {% if _flash %}
    <div class="rounded bg-amber-50 p-3 text-amber-800 text-sm">{{ _flash }}</div>
  {% endif %}

  {% set last = current_user.username_changed_at %}
  {% if last %}
    {% set elapsed_days = (now() - last).days %}
    {% set remaining = 30 - elapsed_days %}
    {% if remaining > 0 %}
      <div class="rounded bg-amber-50 p-3 text-amber-800 text-sm">
        마지막 변경 후 {{ elapsed_days }}일 경과 — {{ remaining }}일 후 변경 가능합니다.
      </div>
    {% endif %}
  {% endif %}

  <form action="/me/profile/username" method="post" class="space-y-3">
    <label class="block">
      <span class="text-sm text-stone-700">새 사용자명 <span class="text-stone-400">(3-32자, 영소문자·숫자·_·-)</span></span>
      <input type="text" name="new_username"
             pattern="[a-z0-9_\-]{3,32}" required
             value="{{ current_user.username }}"
             class="mt-1 w-full rounded border border-stone-300 px-3 py-2 lowercase focus:border-emerald-500 focus:outline-none">
    </label>
    <div class="flex items-center gap-3">
      <button type="submit" class="rounded bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700">
        변경
      </button>
      <a href="/me/profile" class="text-sm text-stone-500 hover:underline">취소</a>
    </div>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 6: `password.html` 페이지 생성**

```jinja
{% extends "base.html" %}
{% block title %}비밀번호 변경 · Nestory{% endblock %}
{% block content %}
<div class="max-w-md mx-auto py-8 px-4 space-y-4">
  <h1 class="text-2xl font-bold text-stone-900">비밀번호 변경</h1>

  {% set _flash = request.session.pop("flash", None) %}
  {% if _flash %}
    <div class="rounded bg-amber-50 p-3 text-amber-800 text-sm">{{ _flash }}</div>
  {% endif %}

  {% if not current_user.password_hash %}
    <div class="rounded bg-stone-50 p-4 text-stone-700 text-sm">
      카카오 계정으로 가입하셨습니다. 비밀번호는 카카오에서 관리합니다.
      <div class="mt-2">
        <a href="/me/profile" class="text-emerald-700 hover:underline">← 프로필로 돌아가기</a>
      </div>
    </div>
  {% else %}
    <form action="/me/profile/password" method="post" class="space-y-3">
      <label class="block">
        <span class="text-sm text-stone-700">현재 비밀번호</span>
        <input type="password" name="current_password" required
               class="mt-1 w-full rounded border border-stone-300 px-3 py-2 focus:border-emerald-500 focus:outline-none">
      </label>
      <label class="block">
        <span class="text-sm text-stone-700">새 비밀번호 <span class="text-stone-400">(최소 8자)</span></span>
        <input type="password" name="new_password" minlength="8" required
               class="mt-1 w-full rounded border border-stone-300 px-3 py-2 focus:border-emerald-500 focus:outline-none">
      </label>
      <div class="flex items-center gap-3">
        <button type="submit" class="rounded bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700">
          변경
        </button>
        <a href="/me/profile" class="text-sm text-stone-500 hover:underline">취소</a>
      </div>
    </form>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 7: Jinja syntax 검증 (4 페이지 + 2 partial)**

Run:
```
uv run python -c "
from app.templating import templates
for t in ['pages/me/profile/edit.html', 'pages/me/profile/_avatar_card.html', 'pages/me/profile/_basic_form.html', 'pages/me/profile/username.html', 'pages/me/profile/password.html']:
    templates.get_template(t)
print('OK')
"
```
Expected: `OK`

- [ ] **Step 8: Lint**

Run: `uv run ruff check app/routers/me.py`
Expected: `All checks passed!`

- [ ] **Step 9: Commit**

```bash
git add app/routers/me.py app/templates/pages/me/profile/
git commit -m "feat(me): GET routes + templates for profile/avatar/username/password"
```

---

## Task 9: 4 POST 라우트 + flash 패턴 + 검증 wiring

**Files:**
- Modify: `app/routers/me.py`

- [ ] **Step 1: import 보강**

[app/routers/me.py](../../app/routers/me.py) 상단 import 블록에 다음 라인을 추가 (기존 `from app.services import badges, evidence_storage` 옆에 정렬):

```python
from app.services import images as images_service
from app.services import profile
from app.services.profile import (
    AvatarOwnershipError,
    PasswordChangeNotAllowed,
    ProfileError,
    UsernameTakenError,
    UsernameThrottledError,
)
```

(P2 JSON API에서 `ProfileRead` 응답 스키마를 쓰게 되면 그때 추가. 본 task에서는 import 안 함 — ruff F401 회피.)

- [ ] **Step 2: 4 POST 라우트 추가**

[app/routers/me.py](../../app/routers/me.py) 파일 끝(GET 라우트 뒤)에 추가:

```python
@router.post("/profile")
def profile_save(
    request: Request,
    display_name: Annotated[str, Form()],
    bio: Annotated[str, Form()] = "",
    primary_region_id: Annotated[str, Form()] = "",
    notify_email_enabled: Annotated[str, Form()] = "",
    notify_kakao_enabled: Annotated[str, Form()] = "",
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    region_id_int: int | None = None
    if primary_region_id.strip():
        try:
            region_id_int = int(primary_region_id)
        except ValueError:
            request.session["flash"] = "유효하지 않은 지역"
            return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)
    try:
        profile.update_profile_basic(
            db, user,
            display_name=display_name,
            bio=bio if bio.strip() else None,
            primary_region_id=region_id_int,
            notify_email_enabled=bool(notify_email_enabled),
            notify_kakao_enabled=bool(notify_kakao_enabled),
        )
        db.commit()
    except ProfileError as e:
        request.session["flash"] = str(e)
        return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)
    request.session["flash"] = "저장되었습니다"
    return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/avatar")
async def profile_avatar_upload(
    request: Request,
    image: Annotated[UploadFile, File()],
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        img = images_service.upload_image(db, user, image)
        profile.set_avatar(db, user, img)
        db.commit()
    except HTTPException:
        # images_service가 던지는 HTTPException은 그대로 raise — 글로벌 핸들러
        db.rollback()
        raise
    except (AvatarOwnershipError, ProfileError) as e:
        db.rollback()
        request.session["flash"] = str(e)
        return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)
    request.session["flash"] = "사진이 변경되었습니다"
    return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/avatar/delete")
def profile_avatar_delete(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    profile.clear_avatar(db, user)
    db.commit()
    request.session["flash"] = "사진이 제거되었습니다"
    return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/username")
def profile_username_change(
    request: Request,
    new_username: Annotated[str, Form()],
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        profile.change_username(db, user, new_username=new_username)
        db.commit()
    except UsernameThrottledError as e:
        request.session["flash"] = f"사용자명 변경은 {e.days_remaining}일 후 가능합니다"
        return RedirectResponse("/me/profile/username", status_code=status.HTTP_303_SEE_OTHER)
    except UsernameTakenError:
        request.session["flash"] = "이미 사용 중인 사용자명입니다"
        return RedirectResponse("/me/profile/username", status_code=status.HTTP_303_SEE_OTHER)
    except ProfileError as e:
        request.session["flash"] = str(e)
        return RedirectResponse("/me/profile/username", status_code=status.HTTP_303_SEE_OTHER)
    request.session["flash"] = "사용자명이 변경되었습니다"
    return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/profile/password")
def profile_password_change(
    request: Request,
    current_password: Annotated[str, Form()],
    new_password: Annotated[str, Form()],
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        profile.change_password(
            db, user,
            current_password=current_password,
            new_password=new_password,
        )
        db.commit()
    except PasswordChangeNotAllowed:
        # 카카오 가입자 — UI에서 폼 미노출이지만 직접 POST 시도 방어
        raise HTTPException(status.HTTP_403_FORBIDDEN, "카카오 계정은 비밀번호 변경 불가")
    except ProfileError as e:
        request.session["flash"] = str(e)
        return RedirectResponse("/me/profile/password", status_code=status.HTTP_303_SEE_OTHER)
    request.session["flash"] = "비밀번호가 변경되었습니다"
    return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)
```

- [ ] **Step 3: Sanity check — uvicorn 임포트**

Run: `uv run python -c "from app.main import app; routes = [r.path for r in app.routes if hasattr(r, 'path')]; print('me/profile routes:', sorted([r for r in routes if '/me/profile' in r]))"`
Expected: 출력에 `/me/profile`, `/me/profile/avatar`, `/me/profile/avatar/delete`, `/me/profile/username`, `/me/profile/password` 모두 포함.

- [ ] **Step 4: Lint**

Run: `uv run ruff check app/routers/me.py`
Expected: `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add app/routers/me.py
git commit -m "feat(me): POST routes for profile/avatar/username/password with flash + validation"
```

---

## Task 10: Integration tests (`test_me_profile_routes.py`)

**Files:**
- Create: `app/tests/integration/test_me_profile_routes.py`

- [ ] **Step 1: Write integration tests**

신규 파일 `app/tests/integration/test_me_profile_routes.py`:

```python
"""Integration tests for /me/profile* routes — TestClient + factory-boy."""
from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from PIL import Image as PILImage
from sqlalchemy.orm import Session

from app.services import auth as auth_service
from app.tests.factories import RegionFactory, UserFactory


def _png_bytes(size: tuple[int, int] = (80, 80)) -> bytes:
    """Generate a small valid PNG for upload tests."""
    buf = io.BytesIO()
    PILImage.new("RGB", size, color=(120, 200, 130)).save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# 1. Anonymous access — every /me/profile* should redirect or 401
# ---------------------------------------------------------------------------


def test_anonymous_get_profile_redirects_or_401(client: TestClient) -> None:
    r = client.get("/me/profile", follow_redirects=False)
    assert r.status_code in (302, 303, 307, 401)


# ---------------------------------------------------------------------------
# 2. GET /me/profile — logged-in user sees form prefilled
# ---------------------------------------------------------------------------


def test_logged_in_get_profile_renders_form(client: TestClient, db: Session, login) -> None:
    user = UserFactory(display_name="홍길동", bio="자기소개")
    db.commit()
    login(user.id)

    r = client.get("/me/profile")
    assert r.status_code == 200
    assert "프로필 편집" in r.text
    assert "홍길동" in r.text
    assert "자기소개" in r.text


# ---------------------------------------------------------------------------
# 3. POST /me/profile happy + invalid region
# ---------------------------------------------------------------------------


def test_post_profile_happy_saves_basic_fields(client: TestClient, db: Session, login) -> None:
    region = RegionFactory(slug="profile-route-region")
    user = UserFactory(display_name="원래", bio=None)
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile",
        data={
            "display_name": "새이름",
            "bio": "새 자기소개",
            "primary_region_id": str(region.id),
            "notify_email_enabled": "1",
            "notify_kakao_enabled": "1",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(user)
    assert user.display_name == "새이름"
    assert user.bio == "새 자기소개"
    assert user.primary_region_id == region.id
    assert user.notify_email_enabled is True
    assert user.notify_kakao_enabled is True


def test_post_profile_unchecked_notify_becomes_false(
    client: TestClient, db: Session, login
) -> None:
    """체크박스 미전송 시 False로 저장 (HTML form 표준)."""
    user = UserFactory(notify_email_enabled=True, notify_kakao_enabled=True)
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile",
        data={
            "display_name": user.display_name,
            "bio": "",
            "primary_region_id": "",
            # notify_* 필드 의도적 미전송
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(user)
    assert user.notify_email_enabled is False
    assert user.notify_kakao_enabled is False


def test_post_profile_invalid_region_flashes(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile",
        data={
            "display_name": user.display_name,
            "bio": "",
            "primary_region_id": "999999",
            "notify_email_enabled": "1",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    # flash 메시지가 다음 GET 페이지에 노출
    follow = client.get("/me/profile")
    assert "유효하지 않은 지역" in follow.text


# ---------------------------------------------------------------------------
# 4. POST /me/profile/avatar — multipart upload sets avatar_image_id
# ---------------------------------------------------------------------------


def test_post_avatar_upload_sets_avatar_image_id(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory()
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile/avatar",
        files={"image": ("avatar.png", _png_bytes(), "image/png")},
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(user)
    assert user.avatar_image_id is not None


# ---------------------------------------------------------------------------
# 5. POST /me/profile/avatar/delete — clears avatar_image_id
# ---------------------------------------------------------------------------


def test_post_avatar_delete_clears_avatar(client: TestClient, db: Session, login) -> None:
    from app.tests.factories import ImageFactory

    user = UserFactory()
    img = ImageFactory(owner=user)
    db.flush()
    user.avatar_image_id = img.id
    db.commit()
    login(user.id)

    r = client.post("/me/profile/avatar/delete", follow_redirects=False)
    assert r.status_code == 303
    db.refresh(user)
    assert user.avatar_image_id is None


# ---------------------------------------------------------------------------
# 6. GET /me/profile/username — throttle 안내 메시지
# ---------------------------------------------------------------------------


def test_get_username_page_shows_throttle_remaining(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory(
        username_changed_at=datetime.now(UTC) - timedelta(days=10)
    )
    db.commit()
    login(user.id)

    r = client.get("/me/profile/username")
    assert r.status_code == 200
    # 30 - 10 = 20 일 잔여 (test 실행 drift 허용)
    assert "일 후 변경 가능합니다" in r.text


# ---------------------------------------------------------------------------
# 7. POST /me/profile/username happy / duplicate / throttle
# ---------------------------------------------------------------------------


def test_post_username_happy_changes_and_redirects_to_profile(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory(username="oldname", username_changed_at=None)
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile/username",
        data={"new_username": "newname"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/me/profile"
    db.refresh(user)
    assert user.username == "newname"


def test_post_username_duplicate_flashes_and_stays_on_page(
    client: TestClient, db: Session, login
) -> None:
    UserFactory(username="taken")
    user = UserFactory(username="mine")
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile/username",
        data={"new_username": "taken"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/me/profile/username"
    follow = client.get("/me/profile/username")
    assert "이미 사용 중인 사용자명" in follow.text


def test_post_username_throttle_flashes_days_remaining(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory(
        username="oldname",
        username_changed_at=datetime.now(UTC) - timedelta(days=5),
    )
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile/username",
        data={"new_username": "newname"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == "/me/profile/username"
    follow = client.get("/me/profile/username")
    # 30 - 5 = 25 일 잔여
    assert "사용자명 변경은" in follow.text and "일 후 가능" in follow.text


# ---------------------------------------------------------------------------
# 8. GET /me/profile/password — 카카오 분기
# ---------------------------------------------------------------------------


def test_get_password_page_shows_form_for_email_user(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory(password_hash=auth_service.hash_password("pw1234567"))
    db.commit()
    login(user.id)

    r = client.get("/me/profile/password")
    assert r.status_code == 200
    assert 'name="current_password"' in r.text
    assert 'name="new_password"' in r.text


def test_get_password_page_shows_kakao_message_for_oauth_user(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory(password_hash=None, kakao_id="kakao_xyz")
    db.commit()
    login(user.id)

    r = client.get("/me/profile/password")
    assert r.status_code == 200
    assert "카카오 계정으로 가입하셨습니다" in r.text
    assert 'name="current_password"' not in r.text


# ---------------------------------------------------------------------------
# 9. POST /me/profile/password happy / wrong current / kakao 403
# ---------------------------------------------------------------------------


def test_post_password_happy_changes_hash(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory(password_hash=auth_service.hash_password("oldPassword"))
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile/password",
        data={"current_password": "oldPassword", "new_password": "newPassword"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    db.refresh(user)
    assert auth_service.verify_password("newPassword", user.password_hash) is True


def test_post_password_wrong_current_flashes(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory(password_hash=auth_service.hash_password("realPass1234"))
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile/password",
        data={"current_password": "wrongPass", "new_password": "newPassword"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    follow = client.get("/me/profile/password")
    assert "현재 비밀번호" in follow.text  # flash message contains "현재 비밀번호..."


def test_post_password_kakao_user_returns_403(
    client: TestClient, db: Session, login
) -> None:
    user = UserFactory(password_hash=None, kakao_id="kakao_zzz")
    db.commit()
    login(user.id)

    r = client.post(
        "/me/profile/password",
        data={"current_password": "anything", "new_password": "newPass1234"},
    )
    assert r.status_code == 403
```

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest app/tests/integration/test_me_profile_routes.py -v`
Expected: 모든 테스트 PASS (~13개). 만약 실패 시 정확한 에러 메시지로 디버그 (보통 import·factory 시그니처·flash 키 오타).

- [ ] **Step 3: 풀 회귀**

Run: `uv run pytest app/tests/ -q --tb=no`
Expected: 본 plan 추가 테스트 ~21 unit + ~13 integration = ~34 신규 테스트 모두 PASS. baseline 2개 pre-existing fail 외 추가 회귀 0.

- [ ] **Step 4: Lint**

Run: `uv run ruff check app/tests/integration/test_me_profile_routes.py`
Expected: `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add app/tests/integration/test_me_profile_routes.py
git commit -m "test(me): integration tests for /me/profile* routes (13 cases)"
```

---

## Task 11: 브라우저 manual QA + 최종 lint + 종결

**Files:** (no modifications — verification only)

- [ ] **Step 1: 개발 서버 가동**

Run: `uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` (background)
대기: 서버 ready 확인 (`curl -sf -o /dev/null http://localhost:8000/`).

- [ ] **Step 2: 로그인 + `/me/profile` 진입**

브라우저:
1. `http://localhost:8000/auth/login` — 데모 계정(`alice.yp@example.com` / `demo1234`) 또는 보유 계정으로 로그인
2. `http://localhost:8000/me/profile` 접속

체크:
- [ ] 페이지 200 + "프로필 편집" 헤더
- [ ] 사진 카드 — 이니셜 또는 기존 사진 표시
- [ ] 기본 정보 form — display_name·bio·region 모두 prefill 정확
- [ ] 알림 체크박스 — 현재 값 반영
- [ ] 사용자명 섹션 — `@username` 표시 + "변경하기" 링크
- [ ] 비밀번호 섹션 — 이메일 가입자면 "변경하기", 카카오 가입자면 안내 메시지

- [ ] **Step 3: 기본 정보 변경 + 저장**

폼에서 display_name·bio 수정 후 저장:
- [ ] 303 redirect 후 `/me/profile` 다시 표시
- [ ] flash 메시지 "저장되었습니다" 노출
- [ ] 새 값 반영 (display_name, bio, region, 알림 설정)

- [ ] **Step 4: 사진 업로드**

`_avatar_card.html`의 file input에서 작은 이미지(JPEG/PNG/WEBP, < 5MB) 선택 → "사진 변경" 클릭:
- [ ] 303 redirect + flash "사진이 변경되었습니다"
- [ ] 페이지 상단 아바타가 새 사진으로 교체 (브라우저 캐시 시 새로고침)
- [ ] base.html의 nav 영역(다른 페이지)도 새 아바타로 표시 (예: `/`, `/u/{username}`)

- [ ] **Step 5: 사진 제거**

"사진 제거" 버튼 클릭:
- [ ] 303 redirect + flash "사진이 제거되었습니다"
- [ ] 아바타가 이니셜로 fallback

- [ ] **Step 6: 사용자명 변경 throttle**

1. `/me/profile/username` 진입 — throttle 안내 노출 여부 (이전 변경 30일 이내인지에 따라)
2. 변경 시도 — 30일 이내면 amber 메시지 "사용자명 변경은 N일 후 가능합니다", 아니면 성공
3. 중복 시도 (이미 존재하는 username) — "이미 사용 중인 사용자명입니다"

- [ ] **Step 7: 비밀번호 변경 (이메일 가입자)**

1. `/me/profile/password` — 폼 정상 노출
2. 현재 비번 틀림 → flash "현재 비밀번호가 일치하지 않습니다"
3. 정상 변경 → flash "비밀번호가 변경되었습니다", 같은 세션 유지
4. 로그아웃 → 신규 비번으로 재로그인 가능 확인

- [ ] **Step 8: 카카오 가입자 비번 페이지**

카카오 가입 계정으로 로그인 후:
- [ ] `/me/profile/password` 진입 → 안내 메시지만, form 미렌더
- [ ] (선택) curl로 직접 POST 시도 → 403 응답

- [ ] **Step 9: 로그아웃 회귀**

로그아웃 후 `/me/profile` 접속:
- [ ] 302/303/401 — 로그인 페이지로 redirect 또는 401 응답

- [ ] **Step 10: Backend log 확인**

uvicorn 로그 1분 관찰:
- [ ] 500 에러 없음
- [ ] Jinja UndefinedError 없음
- [ ] DeprecationWarning 외 신규 warning 없음

- [ ] **Step 11: 최종 풀 lint**

Run: `uv run ruff check app/`
Expected: `All checks passed!`

- [ ] **Step 12: 최종 풀 회귀**

Run: `uv run pytest app/tests/ -q --tb=no`
Expected: baseline 2 fail + 회귀 0. 본 plan 추가 테스트 ~34개 모두 PASS.

- [ ] **Step 13: 백그라운드 uvicorn 종료**

Bash run_in_background로 시작했다면 TaskStop으로 종료. 또는 PowerShell `Get-Process | Where-Object {$_.ProcessName -like '*uvicorn*' -or $_.ProcessName -eq 'python'} | Stop-Process` (8000 점유 PID만 정밀하게 — 다른 사용자 process 영향 주의).

- [ ] **Step 14: 최종 git status + commit chain 확인**

Run: `git status --short && git log --oneline -12`
Expected:
- working tree clean (사용자 in-progress 변경 외)
- 최근 commit chain이 본 plan의 task 1-10에 1:1 대응 (10 commit 또는 합쳐진 commit)

push 는 사용자 승인 후 별도 단계 (본 plan에 미포함).

---

## DoD (spec §12와 1:1 매칭)

| spec §12 항목 | Plan task | 검증 방법 |
|---|---|---|
| 마이그레이션 적용 후 4 컬럼 존재 | Task 1 | Step 5 psql `\d users` |
| `app/services/profile.py` 5 service + 4 예외 | Task 2-6 | `pytest unit/test_profile_service.py` ~21 PASS |
| `app/routers/me.py` 8 신규 라우트 | Task 8-9 | `pytest integration/test_me_profile_routes.py` ~13 PASS |
| 5 신규 템플릿 | Task 8 | Jinja parse OK + manual QA |
| `_avatar.html` 사진/이니셜 분기 | Task 7 | manual QA Step 4·5 |
| 비로그인 401 또는 redirect | Task 9 | integration test 1 |
| 사진 업로드 → 즉시 표시 | Task 9 | manual QA Step 4 |
| Username 30일 throttle | Task 5·9 | unit test + integration test 7 |
| 카카오 가입자 password 폼 미노출 + POST 403 | Task 9 | integration test 8·9 |
| pytest 회귀 0 | 모든 task | manual QA Step 12 |
| ruff lint clean | 모든 task | manual QA Step 11 |
| 4 화면 manual QA | Task 11 | Step 2-9 |

---

## Rollback

각 task 가 commit 단위로 분리되어 임의 시점으로 `git revert` 가능. 마이그레이션 도입(Task 1)은 `uv run alembic downgrade -1` 로 4 컬럼 DROP 후 commit revert. 사진 데이터(uploaded Image rows)는 `clear_avatar` 호출만 사라지면 자동 보존 (orphan GC P2).

---

## Out of plan (spec §15 Open Q — 모두 권고대로 진행)

- Flash helper module: `request.session["flash"]` 직접 사용 (별도 helper P2)
- Avatar URL cache busting: 기존 max-age 정책 유지 (timestamp 추가 P2)
- Bio markdown: plain text only
- 비번 변경 후 세션 처리: 그대로 유지 (강제 재로그인 X)
- 사진 max size: 기존 `images_service` 10MB 제한 그대로

본 plan에서 별도 task 추가 없음.
