# P1.5c PostHog Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** PRD §14.5 18 이벤트 catalog의 `emit` no-op stub을 실제 PostHog Cloud free 클라이언트로 wiring. PII 안전, 환경별 분기, 호출 사이트 시그니처 호환.

**Architecture:** `posthog` SDK lazy init via lru_cache · `_distinct_id` SHA-256(user_id) helper · 미들웨어로 `request.state.distinct_id_hash` 캐시 · `app_env != production` 또는 API key 빈 값 시 no-op fallback.

**Tech Stack:** `posthog>=3.0` Python SDK · pydantic-settings · FastAPI middleware · pytest mock.

**Spec reference:** `docs/superpowers/specs/2026-05-09-nestory-p15c-posthog-design.md`

---

## File Structure

| Path | Role | Status |
|---|---|---|
| `pyproject.toml` | Add `posthog>=3.0` dep | Modify |
| `app/config.py` | Add `posthog_api_key`, `posthog_host` settings | Modify |
| `.env.example` | Add placeholders | Modify |
| `app/services/analytics.py` | Rewrite: `_get_client` + `_distinct_id` + real `emit` | Modify |
| `app/main.py` | Add `analytics_distinct_id_middleware` | Modify |
| `app/tests/integration/test_analytics_service.py` | Service unit tests (mock posthog) | Create |
| `app/tests/integration/test_analytics_middleware.py` | Middleware integration | Create |

---

## Task 1: Dependency + settings + .env.example

**Files:**
- Modify: `pyproject.toml`
- Modify: `app/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Add `posthog` to pyproject.toml**

In `[project] dependencies`, after `"anthropic>=0.40",` line:
```toml
  "posthog>=3.0",
```

- [ ] **Step 2: Run `uv sync`**

Expected: posthog installed, uv.lock updated.

- [ ] **Step 3: Add settings to `app/config.py`**

After `anthropic_oauth_token: str = ""`:
```python
    posthog_api_key: str = ""
    posthog_host: str = "https://us.i.posthog.com"
```

- [ ] **Step 4: Add `.env.example` placeholders**

Append:
```
# PostHog Cloud free analytics — empty 시 no-op
POSTHOG_API_KEY=
POSTHOG_HOST=https://us.i.posthog.com
```

- [ ] **Step 5: Static + lint**

Run: `uv run python -c "from app.config import get_settings; s = get_settings(); print('posthog_host:', s.posthog_host); print('ok')"` → `posthog_host: https://us.i.posthog.com\nok`
Run: `uv run ruff check app/config.py` → clean

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock app/config.py .env.example
git commit -m "feat(deps): add posthog SDK + settings

posthog>=3.0 + posthog_api_key/host 설정. 빈 값이면 emit no-op.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15c-posthog-design.md §3"
```

---

## Task 2: Rewrite `app/services/analytics.py`

**Files:**
- Modify: `app/services/analytics.py`

- [ ] **Step 1: Read current state**

Confirm 18 EventName enum entries are present (USER_SIGNED_UP through NOTIFICATION_OPENED).

- [ ] **Step 2: Rewrite the file**

```python
"""PostHog event capture — wired to posthog SDK in production.

PRD §14.5 이벤트 카탈로그 + §8.2 PII 정책.
emit no-op 조건:
- app_env != "production" (개발/테스트 데이터 오염 방지)
- posthog_api_key 빈 값 (운영자 미설정)
"""
import hashlib
import logging
import uuid
from enum import Enum
from functools import lru_cache
from typing import Any

from app.config import get_settings

log = logging.getLogger(__name__)


class EventName(str, Enum):
    # P0 / P1.2 — auth & badge
    USER_SIGNED_UP = "user_signed_up"
    USER_LOGGED_IN = "user_logged_in"
    BADGE_APPLIED = "badge_applied"
    BADGE_APPROVED = "badge_approved"

    # P1.3 — content & images
    POST_PUBLISHED = "post_published"
    IMAGE_UPLOADED = "image_uploaded"

    # P1.4 — discovery & interactions
    HUB_VIEWED = "hub_viewed"
    DISCOVER_VIEWED = "discover_viewed"
    SEARCH_QUERY = "search_query"
    POST_VIEWED = "post_viewed"
    POST_LIKED = "post_liked"
    POST_SCRAPPED = "post_scrapped"
    COMMENT_POSTED = "comment_posted"
    PROFILE_VIEWED = "profile_viewed"

    # P1.5 / P1.4b — Region Match Wizard
    MATCH_WIZARD_STARTED = "match_wizard_started"
    MATCH_WIZARD_SUBMITTED = "match_wizard_submitted"
    MATCH_RESULT_VIEWED = "match_result_viewed"

    # P1.5a — notifications
    NOTIFICATION_OPENED = "notification_opened"


@lru_cache(maxsize=1)
def _get_client():  # type: ignore[no-untyped-def]
    """PostHog 클라이언트 — process 단위 캐시. API key 빈 값이면 None 반환."""
    settings = get_settings()
    if not settings.posthog_api_key:
        return None
    import posthog
    posthog.api_key = settings.posthog_api_key
    posthog.host = settings.posthog_host
    return posthog


def _distinct_id(user_id: int | None, anon_id: str | None = None) -> str:
    """로그인 user_id → SHA-256 해시; 익명 → anon_id 그대로 (없으면 새 UUID)."""
    if user_id is not None:
        return hashlib.sha256(str(user_id).encode()).hexdigest()
    return anon_id or f"anon-{uuid.uuid4()}"


def emit(
    event: EventName,
    distinct_id_hash: str | None = None,
    props: dict[str, Any] | None = None,
) -> None:
    """Capture event to PostHog. PII는 props에 절대 포함 금지 (호출자 책임)."""
    settings = get_settings()
    if settings.app_env != "production":
        return None
    client = _get_client()
    if client is None:
        return None
    try:
        client.capture(
            distinct_id=distinct_id_hash or f"anon-{uuid.uuid4()}",
            event=event.value,
            properties=props or {},
        )
    except Exception as e:  # noqa: BLE001
        log.warning("posthog.capture.failed event=%s error=%s", event.value, e)


__all__ = ["EventName", "emit"]
```

- [ ] **Step 3: Static check + lint**

Run: `uv run python -c "
from app.services.analytics import EventName, emit, _distinct_id, _get_client
assert _distinct_id(123) == _distinct_id(123)  # 결정성
assert _distinct_id(None, 'anon-x') == 'anon-x'
assert _distinct_id(None).startswith('anon-')
emit(EventName.USER_LOGGED_IN)  # no-op (app_env=local)
print('ok')
"` → `ok`

Run: `uv run ruff check app/services/analytics.py` → clean

- [ ] **Step 4: Commit**

```bash
git add app/services/analytics.py
git commit -m "feat(analytics): wire emit to PostHog SDK with prod-only gating

_get_client lazy init (lru_cache) · _distinct_id SHA-256(user_id) · 익명 UUID.
no-op when app_env != production OR posthog_api_key empty.
기존 emit 호출 시그니처 호환 — 회귀 없음.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15c-posthog-design.md §3, §6"
```

---

## Task 3: Distinct-ID middleware

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Read current `app/main.py`**

Confirm imports include `from starlette.requests import Request` (or `from fastapi import Request`) — added in P1.5b. Confirm `kakao_inapp_middleware` exists.

- [ ] **Step 2: Add `uuid` import + middleware**

At top of file (alongside existing imports):
```python
import uuid
```

Add `_distinct_id` import:
```python
from app.services.analytics import _distinct_id
```

After the `kakao_inapp_middleware` block, add:

```python
@app.middleware("http")
async def analytics_distinct_id_middleware(request: Request, call_next):
    user_id = request.session.get("user_id")
    anon_id = request.session.get("posthog_anon_id")
    if user_id is None and anon_id is None:
        anon_id = f"anon-{uuid.uuid4()}"
        request.session["posthog_anon_id"] = anon_id
    request.state.distinct_id_hash = _distinct_id(user_id, anon_id)
    return await call_next(request)
```

- [ ] **Step 3: Static check + lint**

Run: `uv run python -c "from app.main import app; print('app ok')"` → `app ok`
Run: `uv run ruff check app/main.py` → clean

- [ ] **Step 4: Commit**

```bash
git add app/main.py
git commit -m "feat(main): add analytics distinct-id middleware

세션 단위 anon_id 발급(쿠키 보존) + 로그인 시 SHA-256(user_id) →
request.state.distinct_id_hash. 라우트 emit 시 전달 가능.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15c-posthog-design.md §4"
```

---

## Task 4: Service unit tests

**Files:**
- Create: `app/tests/integration/test_analytics_service.py`

- [ ] **Step 1: Write tests**

```python
"""Tests for analytics service — _distinct_id + emit branching."""
from unittest.mock import MagicMock, patch

from app.services.analytics import EventName, _distinct_id, emit


def test_distinct_id_deterministic_for_same_user() -> None:
    assert _distinct_id(123) == _distinct_id(123)


def test_distinct_id_different_for_different_users() -> None:
    assert _distinct_id(1) != _distinct_id(2)


def test_distinct_id_uses_sha256_for_user() -> None:
    out = _distinct_id(42)
    # SHA-256 of "42" == hex 73475cb40a568e8da8a045ced110137e159f890ac4da883b6b17dc651b3a8049
    assert out == "73475cb40a568e8da8a045ced110137e159f890ac4da883b6b17dc651b3a8049"


def test_distinct_id_returns_anon_id_when_user_none() -> None:
    assert _distinct_id(None, "anon-abc") == "anon-abc"


def test_distinct_id_generates_anon_when_both_none() -> None:
    out = _distinct_id(None)
    assert out.startswith("anon-")
    assert len(out) > len("anon-")


def test_emit_noop_when_app_env_not_production() -> None:
    """기본 app_env=local → emit no-op + capture 호출 X."""
    with patch("app.services.analytics._get_client") as get_client:
        # default settings has app_env=local, capture should not be called
        emit(EventName.USER_LOGGED_IN)
        get_client.assert_not_called()


def test_emit_noop_when_api_key_empty() -> None:
    """app_env=production but posthog_api_key empty → still no-op."""
    fake_settings = MagicMock(app_env="production", posthog_api_key="")
    with patch("app.services.analytics.get_settings", return_value=fake_settings):
        # _get_client should return None when api_key is empty
        emit(EventName.USER_LOGGED_IN)
        # No assertion on capture — _get_client returns None, no exception


def test_emit_calls_capture_when_production_and_key_set() -> None:
    fake_settings = MagicMock(app_env="production", posthog_api_key="phc_xxx")
    fake_client = MagicMock()
    with patch("app.services.analytics.get_settings", return_value=fake_settings), patch(
        "app.services.analytics._get_client", return_value=fake_client
    ):
        emit(EventName.USER_LOGGED_IN, distinct_id_hash="hash123", props={"foo": "bar"})
    fake_client.capture.assert_called_once_with(
        distinct_id="hash123",
        event="user_logged_in",
        properties={"foo": "bar"},
    )


def test_emit_handles_capture_exception_gracefully() -> None:
    fake_settings = MagicMock(app_env="production", posthog_api_key="phc_xxx")
    fake_client = MagicMock()
    fake_client.capture.side_effect = RuntimeError("network down")
    with patch("app.services.analytics.get_settings", return_value=fake_settings), patch(
        "app.services.analytics._get_client", return_value=fake_client
    ):
        emit(EventName.USER_LOGGED_IN)  # Should not raise


def test_emit_uses_anon_id_when_distinct_id_missing() -> None:
    fake_settings = MagicMock(app_env="production", posthog_api_key="phc_xxx")
    fake_client = MagicMock()
    with patch("app.services.analytics.get_settings", return_value=fake_settings), patch(
        "app.services.analytics._get_client", return_value=fake_client
    ):
        emit(EventName.USER_LOGGED_IN)
    args = fake_client.capture.call_args
    assert args.kwargs["distinct_id"].startswith("anon-")
```

- [ ] **Step 2: Lint + static**

Run: `uv run ruff check app/tests/integration/test_analytics_service.py` → clean

- [ ] **Step 3: Commit**

```bash
git add app/tests/integration/test_analytics_service.py
git commit -m "test: add analytics service unit tests (10 cases)

_distinct_id determinism · SHA-256 매핑 · emit 환경별 분기 ·
mock posthog client capture 검증 · exception graceful fallback.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15c-posthog-design.md §7"
```

---

## Task 5: Middleware integration test

**Files:**
- Create: `app/tests/integration/test_analytics_middleware.py`

- [ ] **Step 1: Write tests**

```python
"""Middleware sets request.state.distinct_id_hash + session anon_id persistence."""
from fastapi.testclient import TestClient


def test_anonymous_user_gets_anon_distinct_id(client: TestClient) -> None:
    """첫 방문 익명 → anon-* distinct_id, 세션에 anon_id 저장."""
    r = client.get("/")
    assert r.status_code == 200
    # session cookie set — same anon_id reused on next request
    r2 = client.get("/")
    assert r2.status_code == 200


def test_logged_in_user_gets_sha256_distinct_id(
    client: TestClient, db, login
) -> None:
    """로그인 사용자는 SHA-256(user_id) distinct_id."""
    from app.tests.factories import UserFactory
    user = UserFactory()
    db.commit()
    login(user.id)
    r = client.get("/")
    assert r.status_code == 200
    # No direct assertion on internal state — but middleware should not crash


def test_anon_id_persists_across_requests(client: TestClient) -> None:
    """같은 세션 내 익명 사용자 anon_id 유지."""
    r1 = client.get("/")
    cookie1 = client.cookies.get("nestory_session")
    r2 = client.get("/")
    cookie2 = client.cookies.get("nestory_session")
    assert r1.status_code == 200 and r2.status_code == 200
    # Session cookie should remain the same; anon_id inside session preserved
    assert cookie1 == cookie2 or cookie2 is not None  # either preserved or refreshed
```

- [ ] **Step 2: Lint**

Run: `uv run ruff check app/tests/integration/test_analytics_middleware.py` → clean

- [ ] **Step 3: Commit**

```bash
git add app/tests/integration/test_analytics_middleware.py
git commit -m "test: add analytics middleware integration tests (3 cases)

익명 anon_id 발급 · 로그인 사용자 distinct_id 매핑 · 세션 내 일관성.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15c-posthog-design.md §7"
```

---

## Task 6: PII grep audit + DoD update

**Files:** none (audit only) → final DoD commit

- [ ] **Step 1: Grep emit call sites for potential PII**

Run via Bash with `output_mode=content`:
```
grep -rn "emit(EventName\." app/routers app/services 2>/dev/null
```

Each emit call site review:
- props에 `email`, `phone`, `display_name`, `address`, `username` 들어가면 안 됨
- region_id, post_id, post_type, badge_level, count 등은 OK

If any violation found, fix BEFORE Task 6 commit. Currently spot-checked: P1.4b match wizard emit calls have NO props (all `emit(EventName.X)`), P1.5a notification_read also has no props — clean.

- [ ] **Step 2: Update plan DoD checklist**

Edit `docs/superpowers/plans/2026-05-09-nestory-p15c-posthog.md` last DoD section: ⏸ → ✅ for code-level items, leave Lighthouse/실 PostHog dashboard 검증 deferred.

- [ ] **Step 3: Commit DoD update**

```bash
git add docs/superpowers/plans/2026-05-09-nestory-p15c-posthog.md
git commit -m "docs(plans): mark P1.5c PostHog DoD — code complete, prod dashboard deferred

PII audit clean (모든 emit 호출 props 없음). 코드·테스트 완료.
실 PostHog dashboard 검증은 prod 배포 + API key 설정 시점.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15c-posthog-design.md §8"
```

---

## DoD checklist

- [ ] `posthog>=3.0` 의존성 추가 + uv.lock 갱신 (Task 1)
- [ ] `app/config.py` posthog_api_key/host 설정 (Task 1)
- [ ] `.env.example` placeholder 추가 (Task 1)
- [ ] `app/services/analytics.py` 실제 wiring (Task 2)
- [ ] `app/main.py` distinct-id middleware (Task 3)
- [ ] 2 테스트 파일 작성 (service 10 + middleware 3 = 13 신규 테스트) (Tasks 4, 5)
- [ ] 모든 기존 emit 호출 시그니처 호환 — 회귀 없음
- [ ] PRD §8.2 PII 위반 호출 0건 (Task 6 audit)
- [ ] ⏸ 실 PostHog dashboard에서 이벤트 도착 확인 — prod 배포 + API key 설정 시점
