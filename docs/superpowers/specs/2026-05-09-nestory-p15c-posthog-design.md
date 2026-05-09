# Nestory — P1.5c PostHog 활성화 설계

**작성일**: 2026-05-09
**대상 단계**: P1.5c (P1.5 4 sub-plan 중 세 번째)
**관련 PRD**: §14.5 이벤트 카탈로그 · §10 (NFR Analytics) · §8.2 PII 정책
**관련 OI**: OI-14 ✅ (PostHog Cloud free 결정됨, PRD §10 확정)
**관련 메모리**: P1.5a/b 완료 후 진입

## 0. 핵심 결정 요약 (자율 결정)

| 항목 | 결정 |
|---|---|
| Provider | PostHog Cloud free (`https://us.i.posthog.com` 기본 host) — OI-14에서 결정됨 |
| SDK | 공식 `posthog` Python SDK |
| Distinct ID | 로그인 사용자: SHA-256(user_id) — 솔트 없음 (사용자별 일관 식별만 필요, 역추적 불가). 익명: 세션 단위 익명 ID (cookie 없으면 random UUID 한 번) |
| 컨텍스트 주입 | `app/main.py`에 미들웨어 추가 — `request.state.distinct_id_hash` 캐시. emit 호출 시 미명시면 미들웨어 값 사용 |
| Capture 방식 | sync — `posthog.capture(distinct_id, event, properties)`. PostHog SDK 자체 background queue로 비동기 발송 (사용자 응답 시간에 영향 X) |
| 환경 변수 | `POSTHOG_API_KEY` (필수 — 빈 값이면 emit no-op). `POSTHOG_HOST` (기본 `https://us.i.posthog.com`) |
| 이벤트 catalog | 기존 18 enum 그대로 사용 — 신규 이벤트 추가 X |
| Props PII 검사 | 코드 리뷰로 강제. SDK 호출 직전 props 키 화이트리스트 검증 X (over-engineering — 호출자가 책임) |
| 환경별 발송 | `app_env != "production"` 시 emit no-op (개발 데이터 오염 방지). prod만 실제 capture |

## 1. 배경 및 동기

PRD §14.5에 18개 이벤트 카탈로그 정의됨 (P1.4 + P1.4b + P1.5a까지). 현재 `app/services/analytics.py`의 `emit()`은 no-op stub — enum dispatch 강제만 수행. P1.5c는 stub을 실제 PostHog client로 wiring한다.

**핵심 가치**:
1. 시군 매칭 wizard 사용 분포 (Q&A 옵션 분포 → 시드 가중치 보정 데이터)
2. 검색어 분석 (검색 후 클릭률 → 검색 결과 품질 회고)
3. 알림 open rate (Pillar T 응답률 직결)
4. 콘텐츠 발행/조회 깔때기 (Phase 2 메트릭 게이트 — `Pillar T 1년차 → 3년차 재작성률 ≥ 25%` 측정 기반)

**왜 익명 모드?** PRD §8.2 PII 미수집 원칙. SHA-256(user_id)는 distinct_id로만 사용 — PostHog 대시보드에서도 평문 ID가 보이지 않음. 사용자 본인이 PostHog에 GDPR 삭제 요청 보낼 때도 우리 측에서 해시 매핑 가능 (역추적 불가지만 매핑 테이블 — 그러나 P2 옵션, P1.5c는 hash forget-me 없음).

## 2. 범위

### 2.1 In-scope

- `posthog` Python SDK 의존성 추가 + `uv sync`
- `app/config.py` — `posthog_api_key`, `posthog_host` 설정 추가
- `.env.example` — placeholder 추가
- `app/services/analytics.py` 재작성:
  - `_get_client()` lazy `posthog.Posthog(...)` (lru_cache)
  - `_distinct_id(user)` SHA-256 기반 helper
  - `emit(event, distinct_id_hash=None, props=None)` — 실제 capture 호출
  - `app_env != "production"` 또는 `posthog_api_key`가 빈 값일 때 no-op (개발/테스트)
- `app/main.py` 미들웨어 — `request.state.distinct_id_hash` 캐시 (로그인 사용자 user_id 해시 또는 익명 세션 ID)
- 모든 기존 emit 호출 사이트는 변경 X — 시그니처 호환 유지
- 4 테스트 파일:
  - service unit (`_distinct_id` 결정성, `emit` no-op 분기, app_env 검증, 토큰 빈 값 분기)
  - middleware integration (`request.state.distinct_id_hash` 설정)
  - emit + mock SDK (capture 호출 검증)
  - PII guard test (props에 email 들어있으면? — 현재 정책상 호출자 책임이지만 test로 캡처)

### 2.2 Out of scope

- PostHog Feature Flag 사용 — P2
- A/B test 트래킹 — P2
- 사용자 본인 GDPR 삭제 요청 자동화 (`/me/forget-me`) — P2
- 이벤트 props 화이트리스트 자동 검증 — P2
- 신규 이벤트 추가 — P1.5c는 기존 18개 활성화만
- 서버 사이드 외 클라이언트 사이드 PostHog JS SDK — P2 (서버 사이드만으로 핵심 깔때기 측정 가능)
- IP geolocation enrichment — PostHog 자체 기능 사용 (별도 코드 X)
- Identify (`posthog.identify(...)`) — distinct_id 변경 흐름은 P1.5c엔 필요 없음 (login 시점 anon → user 전환은 P2)

## 3. SDK 통합

### 3.1 의존성

`pyproject.toml`:
```toml
"posthog>=3.0",
```

### 3.2 Settings

`app/config.py`에 추가:
```python
posthog_api_key: str = ""  # 빈 값이면 emit no-op
posthog_host: str = "https://us.i.posthog.com"  # PostHog Cloud US 기본
```

`.env.example`:
```
POSTHOG_API_KEY=
POSTHOG_HOST=https://us.i.posthog.com
```

### 3.3 Distinct ID

```python
import hashlib

def _distinct_id(user_id: int | None, anon_id: str | None = None) -> str:
    """로그인 user_id → SHA-256 해시; 익명 → anon_id 그대로 (없으면 새 UUID 발급)."""
    if user_id is not None:
        return hashlib.sha256(str(user_id).encode()).hexdigest()
    return anon_id or _generate_anon_id()


def _generate_anon_id() -> str:
    import uuid
    return f"anon-{uuid.uuid4()}"
```

(솔트 없음 — distinct_id를 PostHog에 보내는 것이 곧 추적이지만 평문 user_id 비노출이 본 정책의 핵심. 솔트는 over-engineering — 같은 사용자가 매번 다른 distinct_id를 가지면 분석 불가.)

### 3.4 emit 재작성

```python
"""PostHog event capture — wired to posthog SDK in production.

PRD §14.5 이벤트 카탈로그 + §8.2 PII 정책.
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
    # ... existing 18 entries unchanged ...


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
    if user_id is not None:
        return hashlib.sha256(str(user_id).encode()).hexdigest()
    return anon_id or f"anon-{uuid.uuid4()}"


def emit(
    event: EventName,
    distinct_id_hash: str | None = None,
    props: dict[str, Any] | None = None,
) -> None:
    """Capture event to PostHog.

    no-op when:
    - app_env != "production" (dev/test/local data pollution 방지)
    - posthog_api_key empty (운영 미설정 시 silent fail)

    `distinct_id_hash` 미명시 시 익명 UUID. 호출자가 라우트에서
    `request.state.distinct_id_hash` 를 전달하는 것이 권장.
    """
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

## 4. 미들웨어

`app/main.py` 추가 (P1.5b 카카오 미들웨어 다음에):

```python
from app.services.analytics import _distinct_id


@app.middleware("http")
async def analytics_distinct_id_middleware(request: Request, call_next):
    user_id = request.session.get("user_id")
    # 익명 ID는 세션 쿠키에 한 번 발급 후 유지 — 같은 익명 사용자 일관 ID
    anon_id = request.session.get("posthog_anon_id")
    if user_id is None and anon_id is None:
        anon_id = f"anon-{uuid.uuid4()}"
        request.session["posthog_anon_id"] = anon_id
    request.state.distinct_id_hash = _distinct_id(user_id, anon_id)
    return await call_next(request)
```

(`uuid` import 필요 — `app/main.py` top-level.)

라우트는 `request.state.distinct_id_hash`를 emit 호출 시 전달:

```python
emit(EventName.HUB_VIEWED, request.state.distinct_id_hash, {"region_id": region.id})
```

기존 emit 호출 사이트 (P1.4b match · P1.5a notifications)는 distinct_id_hash 미명시 — 시그니처 호환 유지. P2에서 모든 호출 사이트가 `request.state.distinct_id_hash` 를 전달하도록 backfill 가능. P1.5c는 호환성 유지 우선.

**[중요] 본 spec은 호출 사이트 backfill 안 함**: 기존 emit() 호출은 distinct_id 없이 호출되므로 익명 UUID로 capture됨 — 같은 사용자의 행동이 분리됨. 분석 정확도 한계는 인정. P2에서 backfill.

## 5. PII 정책 + props 검사

호출자 책임 — 코드 리뷰 체크리스트에 명시. `emit` 자체는 props를 그대로 전달.

코드 리뷰 차단 패턴 (이 spec에 명시 → 리뷰어가 사용):
- `props={"email": user.email}` ❌
- `props={"phone": ...}` ❌
- `props={"name": ...}` ❌ (display_name 포함)
- `props={"address": ...}` ❌ (시군 ID `region_id`는 OK — 시군은 PII 아님)
- `props={"region_id": 42, "post_type": "review"}` ✅
- `props={"q": query}` ⚠️ — 검색어 자체는 OK이지만 사용자 식별 가능성 검토 (이름·주소 검색 등). PRD §14.5는 검색어 트래킹 허용.

## 6. 환경별 활성화

| `app_env` | API key | emit() |
|---|---|---|
| `local` | (any) | no-op |
| `local` (소수의 디버깅 용) | (any) | no-op |
| `production` | empty | no-op (운영자 미설정) |
| `production` | set | **capture 발송** |

테스트 시 `app_env="local"` 자동 no-op — 테스트가 PostHog 트래픽 쏘지 않음.

## 7. 테스트 전략

| Test file | Verifies |
|---|---|
| `test_analytics_service.py` | `_distinct_id` 결정성 (같은 user_id → 같은 해시), 익명 UUID 발급, `emit` 분기 — `app_env` non-prod 시 no-op, API key 빈 값 시 no-op, prod + key 시 client.capture 호출 (mock) |
| `test_analytics_middleware.py` | 미들웨어 로그인 사용자 → SHA-256 distinct_id, 익명 → 같은 세션 내 일관 anon_id (두 번 GET해도 같은 anon-id), `request.state.distinct_id_hash` 설정 |
| `test_analytics_emit_call_sites.py` | 기존 라우트 emit 호출이 시그니처 호환 (mock client.capture 호출 횟수 확인 — `app_env=production` 패치) |

## 8. DoD

- [ ] `posthog>=3.0` 의존성 추가 + uv.lock 갱신
- [ ] `app/config.py` posthog_api_key/host 설정
- [ ] `.env.example` placeholder 추가
- [ ] `app/services/analytics.py` `_get_client` + `_distinct_id` + `emit` 실제 wiring
- [ ] `app/main.py` middleware 추가 — `request.state.distinct_id_hash`
- [ ] 3 테스트 파일 모두 PASS (Docker 미가용 시 deferred)
- [ ] 모든 기존 emit 호출 사이트 시그니처 호환 — 회귀 없음
- [ ] PRD §8.2 PII 위반 호출 0건 (수동 코드 그렙)
- [ ] 비용 추정: PostHog Cloud free = 월 1M 이벤트 무료 — Phase 1 100명 × 일 30 이벤트 = 90K/월 → 안전권

## 9. 구현 task 추정

6-7 task:

1. `posthog` 의존성 + `app/config.py` settings + `.env.example`
2. `app/services/analytics.py` 재작성 (`_get_client` + `_distinct_id` + `emit` wiring)
3. `app/main.py` analytics_distinct_id_middleware
4. service 테스트 (mock posthog, 분기 검증)
5. middleware 테스트 (`request.state.distinct_id_hash`)
6. PII grep — 모든 emit 호출 사이트 props 검사
7. 수동 QA + DoD 갱신
