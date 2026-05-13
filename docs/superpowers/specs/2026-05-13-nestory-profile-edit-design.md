# Nestory — 사용자 프로필 편집 기능 설계 (Tier A+B)

**작성일**: 2026-05-13
**대상 단계**: P1.5 동시 진행 또는 직전. 데이터 모델 4개 컬럼 추가 + service·routes·templates 신규.
**관련 PRD**: §6.4 [B5] User 모델, §1.5 4축(특히 V축 — 작성자 신뢰감 강화), §11 알림(P1.5 OI-12)
**관련 메모리**: `project_nestory_handoff.md`, `feedback_consistency_first.md`
**관련 코드**:
- [user.py](../../app/models/user.py) User 모델
- [me.py](../../app/routers/me.py) 기존 /me/badge 라우터
- [images.py](../../app/routers/images.py) `/htmx/image/upload` 이미지 업로드 + `/img/{id}/{variant}` 서빙
- [_avatar.html](../../app/templates/components/_avatar.html) 이니셜 아바타 macro
- [auth.py](../../app/services/auth.py) hash_password / create_user_with_password

## 0. 핵심 결정 요약

| 항목 | 결정 |
|---|---|
| 적용 범위 | Tier A (사진·display_name·bio) + Tier B (username 30일 throttle, 비밀번호, 관심 지역, 알림 설정 4종) |
| Tier C (이메일·탈퇴·OAuth 추가·GDPR export) | 본 spec 범위 X — 별도 plan |
| 데이터 모델 변경 | User 컬럼 4개 추가 (`avatar_image_id`·`username_changed_at`·`notify_email_enabled`·`notify_kakao_enabled`). 별도 테이블 없음 |
| 이미지 파이프라인 | P1.3 `images_service.upload_image` 재사용. 신규 라우트 `POST /me/profile/avatar`가 service 호출 후 `User.avatar_image_id` 설정 |
| 라우트 prefix | 기존 `/me` (me.py 확장) — 새 `/profile`·`/profile/avatar`·`/profile/avatar/delete`·`/profile/username`·`/profile/password` |
| Username 변경 throttle | **30일 1회** (slack/discord 표준) |
| 카카오 가입자 비번 변경 | `password_hash IS NULL` → 403 + 안내 메시지 |
| 알림 설정 위치 | 통합 (단일 `/me/profile` 폼) — 별도 `/me/notifications` 분리는 추후 옵션 |
| CSRF | 본 spec 미적용 — 기존 라우트들과 동일. P1.5+에서 일괄 도입 시 함께 적용 |
| 네이티브 재사용 | services 레이어 도메인 예외(`UsernameThrottledError` 등) — JSON API 변환 시 그대로 매핑 |

## 1. 배경 및 동기

### 1.1 현재 상태

- User 모델에 사진 컬럼 없음 — 모든 곳에서 이니셜 아바타([_avatar.html](../../app/templates/components/_avatar.html))만 표시
- 본인 프로필 편집 라우트 부재 — `/me/badge` (배지 신청)만 존재
- bio·display_name 컬럼은 있으나 회원가입 시 입력 후 수정 UI 없음
- 알림 수신 동의는 P1.5 알림 시스템 진입 시점에 사용자 컨센트가 필요한데 현재 컬럼·UI 없음

### 1.2 왜 지금 도입?

- **PRD V축(Peer Validation) 강화**: 작성자 사진·자기소개가 후기·답변의 신뢰감과 직결. 이니셜만 노출되는 현재 UX는 "익명 글" 인상으로 V축 약화.
- **P1.5 진입 전 알림 동의 컬럼 필요**: OI-12 카카오 알림톡 발송 가드. 컬럼 없이 P1.5 시작 시 마이그레이션·동의 UX를 동시에 짜야 하는데 본 spec에서 미리 컬럼만 확보하면 P1.5 작업 단순화.
- **회원가입 후 정보 수정 부재는 표준 SaaS 결격**: 이메일 가입자가 display_name·bio 오타 수정 못함, username·비번 변경도 불가 — 사용자 첫 신뢰 손상.

### 1.3 왜 Tier A+B (Tier C 제외)

- Tier C(이메일 변경·탈퇴·GDPR export)는 보안·법규 요구사항이 큼 → 별도 spec에서 신중 설계
- Tier A는 V축 즉시 강화, Tier B는 정상 SaaS 수준 — 두 묶음이 합쳐서 ~3-5일 분량
- 카카오 가입자도 OAuth 계정으로 같은 편집 화면 사용 (비번 섹션만 hidden) — 분기 단순

## 2. 범위

### 2.1 In-scope

- User 모델 4개 컬럼 추가 + alembic 마이그레이션 1개
- `app/services/profile.py` 신규 — 5개 service 함수 + 4개 도메인 예외
- `app/routers/me.py` 확장 — 8개 라우트 (4 GET + 4 POST)
- `app/templates/pages/me/profile/` 신규 — `edit.html` + 4 partial
- `app/templates/components/_avatar.html` macro에 사진 분기 추가 (img tag with object-cover, fallback 이니셜)
- Pydantic Read 스키마 `app/schemas/profile.py` (네이티브 JSON API 대비)
- 테스트:
  - Unit `test_profile_service.py` — 5 service 함수 happy + 5 edge case
  - Integration `test_me_profile_routes.py` — 4 화면 GET + POST happy + 401 비로그인 + 카카오 비번 403
  - Migration test — 기존 패턴 (마이그레이션 적용 후 컬럼 존재 확인)

### 2.2 Out of scope

- **이메일 변경** (verify token 발송 + confirm 플로우 — 별도 spec)
- **계정 탈퇴 (anonymize)** (`anonymized_at` 컬럼은 이미 있으나 관련 워크플로 별도)
- **OAuth 연결 추가/해제** (이메일 + 카카오 동시 보유 — 별도)
- **GDPR data export**
- **Garbage collection of orphaned avatar Image rows** (이전 사진 교체 시 이전 Image 행은 그대로 유지 — P2 cleanup job)
- **Avatar crop/rotate UI** (업로드 그대로 사용; 사용자가 사전 편집)
- **2FA / Social account linking**
- **이메일 인증 상태 표시** (이미 가입 시 검증되었다고 가정)

## 3. 데이터 모델

### 3.1 User 모델 신규 컬럼 4개

```python
# app/models/user.py — 기존 클래스에 추가
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

### 3.2 알림 기본값 근거

- `notify_email_enabled=True` 기본값 — 가입 시 약관 수락에 포함 (가입 화면에 안내 문구 추가는 Tier C — 본 spec은 컬럼만)
- `notify_kakao_enabled=False` 기본값 — 카카오 알림톡은 명시적 opt-in (한국 정보통신망법 준수)

### 3.3 마이그레이션

`alembic revision --autogenerate -m "add_profile_edit_columns_to_users"`. 기대 출력:

```python
def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_image_id", sa.Integer(), nullable=True))
    op.create_foreign_key(None, "users", "images", ["avatar_image_id"], ["id"], ondelete="SET NULL")
    op.create_index(op.f("ix_users_avatar_image_id"), "users", ["avatar_image_id"], unique=False)
    op.add_column("users", sa.Column("username_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("notify_email_enabled", sa.Boolean(), nullable=False, server_default="true"))
    op.add_column("users", sa.Column("notify_kakao_enabled", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("users", "notify_kakao_enabled")
    op.drop_column("users", "notify_email_enabled")
    op.drop_column("users", "username_changed_at")
    op.drop_index(op.f("ix_users_avatar_image_id"), table_name="users")
    op.drop_constraint(None, "users", type_="foreignkey")  # autogenerate가 보통 이름 자동 부여
    op.drop_column("users", "avatar_image_id")
```

기존 행은 server_default 로 자동 채워짐 → 무중단.

### 3.4 Forward FK 우려 없음

`images` 테이블은 P1.3에서 이미 존재 — forward FK 패턴 미적용.

## 4. Service 레이어 (`app/services/profile.py` 신규)

### 4.1 도메인 예외

```python
# app/services/profile.py
class ProfileError(Exception):
    """Base for profile service errors."""


class UsernameTakenError(ProfileError):
    pass


class UsernameThrottledError(ProfileError):
    """Username changed within last 30 days."""
    def __init__(self, days_remaining: int):
        self.days_remaining = days_remaining
        super().__init__(f"username 변경은 {days_remaining}일 후 가능합니다")


class PasswordChangeNotAllowed(ProfileError):
    """Kakao OAuth users have no password to change."""


class AvatarOwnershipError(ProfileError):
    """User attempted to set avatar to an Image they don't own."""
```

### 4.2 함수 시그니처

```python
USERNAME_CHANGE_THROTTLE_DAYS = 30
USERNAME_PATTERN = re.compile(r"^[a-z0-9_-]{3,32}$")
PASSWORD_MIN_LENGTH = 8


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
    """display_name (1-64), bio (0-500), region (FK 검증), 알림 2개. flush only."""
    ...


def set_avatar(db: Session, user: User, image: Image) -> User:
    """avatar 설정. image.owner_id != user.id면 AvatarOwnershipError."""
    if image.owner_id != user.id:
        raise AvatarOwnershipError()
    user.avatar_image_id = image.id
    db.flush()
    return user


def clear_avatar(db: Session, user: User) -> User:
    """avatar 제거. (이전 Image 행은 보존 — orphan GC는 P2)."""
    user.avatar_image_id = None
    db.flush()
    return user


def change_username(db: Session, user: User, *, new_username: str) -> User:
    """30일 throttle + lowercase 정규식 + unique 검증."""
    new_username = new_username.strip().lower()
    if not USERNAME_PATTERN.fullmatch(new_username):
        raise ProfileError("사용자명 형식 오류 — 3-32자, 영소문자·숫자·_·- 만 허용")
    if new_username == user.username:
        return user  # no-op
    if user.username_changed_at is not None:
        elapsed = (datetime.now(UTC) - user.username_changed_at).days
        if elapsed < USERNAME_CHANGE_THROTTLE_DAYS:
            raise UsernameThrottledError(USERNAME_CHANGE_THROTTLE_DAYS - elapsed)
    exists = db.scalar(select(User.id).where(User.username == new_username))
    if exists is not None:
        raise UsernameTakenError(new_username)
    user.username = new_username
    user.username_changed_at = datetime.now(UTC)
    db.flush()
    return user


def change_password(
    db: Session, user: User, *, current_password: str, new_password: str
) -> User:
    """현재 비번 검증 → 신규 hash. 카카오 가입자(password_hash IS NULL)면 거부."""
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

라우트 함수가 `db.commit()` 책임 — service는 flush까지만 (트랜잭션 일관성).

### 4.3 왜 Pydantic 스키마 별도 정의?

`app/schemas/profile.py` — `ProfileBasicUpdate`·`UsernameChange`·`PasswordChange` 입력 스키마 + `ProfileRead` (id·username·display_name·bio·avatar_url·primary_region·notify_email_enabled·notify_kakao_enabled) 응답 스키마. 라우트는 Form 으로 받은 뒤 Pydantic으로 검증 → service 호출. 추후 JSON API (`/api/v1/me/profile`)는 `request_body=ProfileBasicUpdate`로 그대로 재사용.

## 5. 라우트 (`app/routers/me.py` 확장)

기존 `/me/badge*` 라우트는 변경 없음. `/me/profile` 계열 8개 추가.

| Method | Path | 역할 |
|---|---|---|
| GET | `/me/profile` | 편집 폼 페이지 (4 섹션 통합 — `edit.html` 렌더). 현재 값 prefill, region dropdown |
| POST | `/me/profile` | display_name·bio·primary_region_id·notify_email·notify_kakao 일괄 저장. 검증 실패 시 flash + form 재렌더. 성공 시 303 redirect to `/me/profile` |
| POST | `/me/profile/avatar` | multipart 사진 업로드. `images_service.upload_image` → `set_avatar`. JSON 응답 (htmx swap) 또는 redirect 303 |
| POST | `/me/profile/avatar/delete` | `clear_avatar` 호출. 303 redirect |
| GET | `/me/profile/username` | username 변경 폼 (`_username_form.html` partial 또는 separate page). `username_changed_at` 기반 잔여 일수 표시 |
| POST | `/me/profile/username` | `change_username` 호출. 예외 → flash. 성공 → 303 |
| GET | `/me/profile/password` | 비번 변경 폼. 카카오 가입자(password_hash IS NULL)는 안내 메시지 + 폼 미렌더. 200 응답 |
| POST | `/me/profile/password` | `change_password` 호출. 카카오면 403, 검증 실패 시 flash, 성공 시 세션 유지 + 303 |

모든 라우트 `Depends(require_user)` (비로그인 401). `me.py` 패턴 일관성.

### 5.1 Avatar upload 라우트 상세

```python
@router.post("/profile/avatar")
async def upload_avatar(
    image: UploadFile = File(...),
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    img = images_service.upload_image(db, user, image)  # owner_id 자동 설정
    profile.set_avatar(db, user, img)
    db.commit()
    return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)
```

기존 `/htmx/image/upload`를 거치지 않고 직접 multipart 받음 — 단일 round-trip + service에서 `set_avatar` 호출 시 owner 검증 자동 통과.

### 5.2 Username change 라우트 상세

```python
@router.post("/profile/username")
def change_username_route(
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
    return RedirectResponse("/me/profile", status_code=status.HTTP_303_SEE_OTHER)
```

flash 패턴은 기존 코드베이스 컨벤션 확인 필요 — 없으면 본 spec에서 처음 도입 (별도 helper `app/services/flash.py` 또는 직접 session에 set/pop). 결정: **session 직접 사용**, 별도 helper는 P2.

## 6. 템플릿

### 6.1 디렉토리

```
app/templates/pages/me/profile/
├── edit.html              # 메인 (4 섹션 통합)
├── _basic_form.html       # display_name·bio·region·알림 — htmx swap target
├── _avatar_card.html      # 현재 사진 + 업로드/제거 버튼
└── _flash.html            # session flash 메시지 표시 (선택 — 또는 base.html에 통합)

app/templates/pages/me/profile/username.html   # 별도 페이지 (단순 폼)
app/templates/pages/me/profile/password.html   # 별도 페이지 (카카오 분기)
```

### 6.2 `edit.html` 골격

```jinja
{% extends "base.html" %}
{% block content %}
<div class="space-y-6 max-w-2xl mx-auto py-8">
  <h1 class="text-2xl font-bold">프로필 편집</h1>

  {% set _flash = request.session.pop("flash", None) %}
  {% if _flash %}
    <div class="rounded bg-emerald-50 p-3 text-emerald-800 text-sm">{{ _flash }}</div>
  {% endif %}

  <section class="space-y-3 border-b border-stone-200 pb-6">
    <h2 class="font-semibold">프로필 사진</h2>
    {% include "pages/me/profile/_avatar_card.html" %}
  </section>

  <section class="space-y-3 border-b border-stone-200 pb-6">
    <h2 class="font-semibold">기본 정보</h2>
    {% include "pages/me/profile/_basic_form.html" %}
  </section>

  <section class="space-y-3 border-b border-stone-200 pb-6">
    <h2 class="font-semibold">사용자명</h2>
    <p class="text-sm text-stone-600">현재 — <code>@{{ current_user.username }}</code></p>
    <a href="/me/profile/username" class="text-emerald-700 hover:underline">변경하기 →</a>
  </section>

  <section class="space-y-3">
    <h2 class="font-semibold">비밀번호</h2>
    {% if current_user.password_hash %}
      <a href="/me/profile/password" class="text-emerald-700 hover:underline">변경하기 →</a>
    {% else %}
      <p class="text-sm text-stone-500">카카오 계정으로 가입하셨습니다 — 비밀번호 미사용</p>
    {% endif %}
  </section>
</div>
{% endblock %}
```

### 6.3 `_avatar_card.html`

```jinja
{% from "components/_avatar.html" import avatar %}

<div class="flex items-center gap-4">
  {{ avatar(current_user, 56) }}

  <div class="flex flex-col gap-2">
    <form action="/me/profile/avatar" method="post" enctype="multipart/form-data" class="flex items-center gap-2">
      <input type="file" name="image" accept="image/jpeg,image/png,image/webp" required
             class="text-sm">
      <button type="submit" class="rounded bg-emerald-600 px-3 py-1.5 text-sm text-white hover:bg-emerald-700">
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

### 6.4 `_basic_form.html`

```jinja
<form action="/me/profile" method="post" class="space-y-4">
  <label class="block">
    <span class="text-sm text-stone-700">표시 이름</span>
    <input type="text" name="display_name" value="{{ current_user.display_name }}"
           required maxlength="64"
           class="mt-1 w-full rounded border border-stone-300 px-3 py-2">
  </label>

  <label class="block">
    <span class="text-sm text-stone-700">자기소개 (500자 이내)</span>
    <textarea name="bio" rows="4" maxlength="500"
              class="mt-1 w-full rounded border border-stone-300 px-3 py-2">{{ current_user.bio or "" }}</textarea>
  </label>

  <label class="block">
    <span class="text-sm text-stone-700">관심 시군 (선택)</span>
    <select name="primary_region_id"
            class="mt-1 w-full rounded border border-stone-300 px-3 py-2">
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
      <span class="text-sm">카카오 알림톡 (별도 비용 발생 가능)</span>
    </label>
  </fieldset>

  <button type="submit" class="rounded bg-emerald-600 px-4 py-2 text-white hover:bg-emerald-700">
    저장
  </button>
</form>
```

체크박스가 비활성화되면 form에서 아예 전송 안 됨 → 라우트에서 `Form(False)` default 처리.

### 6.5 `username.html` (단순 페이지)

```jinja
{% extends "base.html" %}
{% block content %}
<div class="max-w-md mx-auto py-8 space-y-4">
  <h1 class="text-2xl font-bold">사용자명 변경</h1>

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
      <span class="text-sm text-stone-700">새 사용자명 (3-32자, 영소문자·숫자·_·-)</span>
      <input type="text" name="new_username" pattern="[a-z0-9_\-]{3,32}" required
             value="{{ current_user.username }}"
             class="mt-1 w-full rounded border border-stone-300 px-3 py-2 lowercase">
    </label>
    <button type="submit" class="rounded bg-emerald-600 px-4 py-2 text-white hover:bg-emerald-700">
      변경
    </button>
    <a href="/me/profile" class="text-sm text-stone-500 hover:underline ml-2">취소</a>
  </form>
</div>
{% endblock %}
```

### 6.6 `password.html` (카카오 분기)

```jinja
{% extends "base.html" %}
{% block content %}
<div class="max-w-md mx-auto py-8 space-y-4">
  <h1 class="text-2xl font-bold">비밀번호 변경</h1>

  {% if not current_user.password_hash %}
    <div class="rounded bg-stone-50 p-4 text-stone-700">
      카카오 계정으로 가입하셨습니다. 비밀번호는 카카오에서 관리합니다.
      <a href="/me/profile" class="text-emerald-700 hover:underline ml-2">← 프로필로</a>
    </div>
  {% else %}
    <form action="/me/profile/password" method="post" class="space-y-3">
      <label class="block">
        <span class="text-sm">현재 비밀번호</span>
        <input type="password" name="current_password" required
               class="mt-1 w-full rounded border border-stone-300 px-3 py-2">
      </label>
      <label class="block">
        <span class="text-sm">새 비밀번호 (최소 8자)</span>
        <input type="password" name="new_password" minlength="8" required
               class="mt-1 w-full rounded border border-stone-300 px-3 py-2">
      </label>
      <button type="submit" class="rounded bg-emerald-600 px-4 py-2 text-white hover:bg-emerald-700">
        변경
      </button>
    </form>
  {% endif %}
</div>
{% endblock %}
```

## 7. `_avatar.html` macro 분기

```jinja
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

크기별 Tailwind 클래스 매핑은 그대로 유지 — `<img>`/`<span>` 모두에 적용. 사진의 가로세로비를 보장하기 위해 `object-cover`. 로딩 전 `bg-stone-100` placeholder.

## 8. 검증 규칙 (단일 진실 원천 — service 레이어)

| 필드 | 규칙 | 예외 |
|---|---|---|
| `display_name` | trim 후 1-64자 | `ProfileError("표시 이름 1-64자")` |
| `bio` | None 허용, 0-500자 | `ProfileError("자기소개 500자 이내")` |
| `username` | trim+lowercase, `^[a-z0-9_-]{3,32}$`, unique | `ProfileError`/`UsernameTakenError` |
| `username` (throttle) | `now() - username_changed_at >= 30일` | `UsernameThrottledError(days_remaining)` |
| `password (current)` | bcrypt verify | `ProfileError("현재 비밀번호 불일치")` |
| `password (new)` | 최소 8자 | `ProfileError("비밀번호 최소 8자")` |
| `primary_region_id` | None 허용. 값 있으면 regions에 존재 | `ProfileError("유효하지 않은 지역")` |
| 이미지 | 기존 `images_service.upload_image` 검증 (MIME/size/width/height) | `images_service`의 ValueError |
| `notify_email_enabled` | bool — Form value="1" 또는 미전송 | (검증 불필요) |
| `notify_kakao_enabled` | bool — Form value="1" 또는 미전송 | (검증 불필요) |

template HTML5 attribute (required·maxlength·pattern·minlength)로 1차 클라이언트 검증, service 레이어에서 최종 검증 강제.

## 9. 권한·보안

- 모든 라우트 `Depends(require_user)` (비로그인 401 → 기존 deps.py 동작)
- 사진 업로드: `images_service.upload_image`가 `owner_id=user.id` 자동 설정 → `set_avatar`가 ownership 재검증 (방어적, 서비스 단독 호출 시 안전)
- 비밀번호 변경: 현재 비번 hash 재검증 (계정 탈취된 세션이 비번 바꿔서 락아웃 시키는 시나리오 방어 — 약하지만 표준 패턴)
- CSRF: 본 spec 미적용. 기존 라우트들과 같은 보안 수준. P1.5+에서 일괄 도입.
- 다른 사용자 프로필 편집은 라우트가 path에 username 받지 않음 (`/me/profile`은 항상 `current_user` 사용) → IDOR 불가능

## 10. 에러 처리

| 상황 | 처리 |
|---|---|
| display_name 빈 문자열 | 400 + flash "표시 이름 입력 필요" |
| bio > 500자 | 400 + flash |
| username 형식 위반 | 400 + flash |
| username throttle | 400 + flash with days_remaining |
| username 중복 | 400 + flash |
| 비번 현재값 불일치 | 400 + flash |
| 비번 < 8자 | 400 + flash |
| 카카오 가입자 비번 변경 시도 | 403 + flash "카카오 계정은 비밀번호 변경 불가" |
| 이미지 MIME/size 위반 | 400 + flash (images_service ValueError 캐치) |
| 잘못된 region_id | 400 + flash |
| 동시성 (다른 탭에서 username 변경 후) | DB unique 제약 위반 → IntegrityError → 400 |

flash는 모두 `request.session["flash"] = "..."` 단발 메시지. 다음 GET에서 pop & 표시.

## 11. 테스트

### 11.1 Service unit (`app/tests/unit/test_profile_service.py`)

- `update_profile_basic` happy + bio None / display_name 빈 문자열 거부 / region 존재 검증
- `set_avatar` happy + 다른 사용자 image 거부 (`AvatarOwnershipError`)
- `clear_avatar` happy
- `change_username` happy + throttle 28일/30일 boundary + duplicate 거부 + invalid pattern 거부
- `change_password` happy + current password 불일치 거부 + 카카오 가입자 거부 + 신규 < 8자 거부

총 ~12-15 테스트.

### 11.2 Route integration (`app/tests/integration/test_me_profile_routes.py`)

- GET `/me/profile` 비로그인 401 + 로그인 200 + form prefill 검증
- POST `/me/profile` happy + 잘못된 region 400 flash
- POST `/me/profile/avatar` multipart 업로드 → user.avatar_image_id 갱신 + Image row 생성
- POST `/me/profile/avatar/delete` → user.avatar_image_id NULL
- GET `/me/profile/username` 200 + throttle 잔여 일수 표시 검증
- POST `/me/profile/username` happy + duplicate 400 + throttle 400
- GET `/me/profile/password` 카카오 가입자 200 + 폼 미렌더 검증 + 이메일 가입자 200 + 폼 렌더 검증
- POST `/me/profile/password` happy (이메일 가입자) + 카카오 가입자 403 + 현재 비번 불일치 400

총 ~10-12 통합 테스트. factory-boy 우선:
- `UserFactory` (이메일 가입자, password_hash 채워짐) — 기본
- 카카오 가입자: `UserFactory(password_hash=None, kakao_id="kakao123")`
- 사진 테스트: `ImageFactory(owner=user, status=ImageStatus.READY)`

### 11.3 Migration test

기존 패턴 따라 — `app/tests/integration/test_migration_*.py`가 있으면 동일 형태로 새 컬럼 4개 존재 확인. (현재 마이그레이션 테스트 패턴 확인 후 결정)

### 11.4 Macro 테스트 (선택)

`_avatar.html` macro 변경은 통합 테스트로 자연 검증 — 별도 unit 테스트 불필요.

## 12. DoD (Definition of Done)

- alembic 마이그레이션 적용 후 user 테이블에 4개 컬럼 존재 (`uv run alembic upgrade head`)
- `app/services/profile.py` 5개 service + 4개 도메인 예외 정의
- `app/routers/me.py` 8개 신규 라우트 정상 동작 (200/303/400/403)
- `app/templates/pages/me/profile/` 5개 템플릿 (`edit.html` + 4 partial/page)
- `_avatar.html` macro 사진/이니셜 분기 적용
- 비로그인 사용자가 `/me/profile*` 접근 시 401 또는 로그인 페이지로 리다이렉트
- 사진 업로드 → 즉시 표시 (medium 변형 fallback to orig)
- username 변경 30일 throttle 작동 + flash 메시지 명확
- 카카오 가입자가 `/me/profile/password` 접근 시 폼 대신 안내 메시지 표시
- pytest baseline 회귀 0
- ruff lint clean
- 브라우저 manual QA — 4 화면(edit·avatar·username·password) 모두 정상

## 13. 마이그레이션 / 롤백

- 단일 alembic 마이그레이션 (4 컬럼 추가)
- 기존 user 행은 server_default로 자동 채워짐 → 무중단
- 다운그레이드 — 4 컬럼 DROP (notify_*는 데이터 손실, avatar_image_id는 사진 참조 끊김)
- 마이그레이션 실패 시 alembic downgrade 1단계로 복원

## 14. 구현 task 추정 + 분해

10-13 task. 대략적 분해 (Plan 단계에서 정밀화):

1. User 모델 4 컬럼 + alembic autogenerate + 마이그레이션 검증
2. `app/services/profile.py` + 4 도메인 예외 + ProfileError base
3. `update_profile_basic` 함수 + unit test (TDD)
4. `set_avatar` / `clear_avatar` 함수 + unit test
5. `change_username` 함수 + throttle/dup/pattern unit test
6. `change_password` 함수 + 카카오/현재 비번 검증 unit test
7. `app/routers/me.py` 4 GET 라우트 + edit·username·password·`_avatar_card` 템플릿
8. `app/routers/me.py` 4 POST 라우트 + flash 패턴 + 검증 wiring
9. `_avatar.html` macro 사진/이니셜 분기
10. Integration test `test_me_profile_routes.py` (10-12 cases)
11. Migration smoke test + 풀 회귀 + ruff
12. 브라우저 manual QA + 종결

## 15. Open Questions

| 항목 | 옵션 | 권고 |
|---|---|---|
| Flash helper module | (a) 별도 `app/services/flash.py` / (b) 라우트에서 `request.session["flash"]` 직접 | **(b)** 본 spec — 패턴이 4번 정도만 등장. helper는 P2 |
| Avatar 변경 후 표시 캐시 | (a) URL에 timestamp 쿼리 추가 / (b) browser 자연 갱신 신뢰 | **(b)** images.py가 이미 Cache-Control: public, max-age=86400 설정 — medium 변형이 새로 생성되면 ID도 동일하므로 캐시 미스 가능. 사용자가 새로고침 시 갱신. P2에서 timestamp 추가 검토 |
| Bio 마크다운 허용 | (a) plain text only / (b) 제한된 마크다운 (link·bold) | **(a)** plain text — XSS 부담 회피. 향후 도입 시 markdown_to_html filter 재사용 |
| 비번 변경 후 세션 처리 | (a) 그대로 유지 / (b) 강제 재로그인 | **(a)** 사용자가 직접 변경한 경우 재로그인 강제는 UX 손해. 의심 활동 감지 시점(P2)에서 도입 |
| 사진 업로드 max size | (a) 기존 `images_service` 제한(10MB) 그대로 / (b) 아바타용 별도(2MB) | **(a)** images_service 일관성 유지 — 사용자가 큰 파일 올려도 medium 변형이 thumb size로 줄어듦 |

5개 항목 모두 권고대로 진행하면 별도 결정 회의 불필요.

---

**다음 단계**: 본 spec 사용자 승인 후 `superpowers:writing-plans` 스킬로 implementation plan 작성 → `subagent-driven-development`로 실행.
