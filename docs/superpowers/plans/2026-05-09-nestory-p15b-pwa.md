# P1.5b PWA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PRD §9.3 P1 종료 기준 PWA + 카카오 인앱 브라우저 호환 — manifest + 최소 Service Worker (offline fallback) + UA 기반 카카오 인앱 안내 배너.

**Architecture:** 정적 manifest.webmanifest + 정적 sw.js + 정적 pwa.js 등록 스크립트 + 미들웨어로 `request.state.kakao_inapp` 주입 + base.html 배너 + `/_offline` 라우트. 마이그레이션 0건. 기존 정적 마운트 활용.

**Tech Stack:** FastAPI middleware / Jinja2 SSR / Service Worker API / Web App Manifest / Tailwind / Alpine.js (배너 닫기)

**Spec reference:** `docs/superpowers/specs/2026-05-09-nestory-p15b-pwa-design.md`

---

## File Structure

| Path | Role | Status |
|---|---|---|
| `app/static/manifest.webmanifest` | PWA manifest JSON | Create |
| `app/static/sw.js` | Service Worker — install/activate/fetch | Create |
| `app/static/js/pwa.js` | SW registration script | Create |
| `app/templates/base.html` | Add `<link rel="manifest">`, Apple meta, pwa.js, kakao banner include | Modify |
| `app/templates/components/_kakao_inapp_banner.html` | 배너 partial | Create |
| `app/templates/pages/_offline.html` | SW fallback page | Create |
| `app/services/kakao_inapp.py` | `is_kakao_inapp(request)` UA helper | Create |
| `app/main.py` | `kakao_inapp_middleware` 등록 | Modify |
| `app/routers/pages.py` | `GET /_offline` 라우트 | Modify |
| `app/tests/integration/test_kakao_inapp.py` | helper unit tests | Create |
| `app/tests/integration/test_kakao_inapp_middleware.py` | middleware + banner integration | Create |
| `app/tests/integration/test_pwa_static.py` | manifest/sw/pwa.js fetch tests | Create |
| `app/tests/integration/test_offline_route.py` | `/_offline` route test | Create |

---

## Task 1: Manifest + base.html meta

**Files:**
- Create: `app/static/manifest.webmanifest`
- Modify: `app/templates/base.html`

- [ ] **Step 1: Write `app/static/manifest.webmanifest`**

```json
{
  "name": "Nestory · 전원생활 정착 커뮤니티",
  "short_name": "Nestory",
  "description": "은퇴자 전원생활 정착의 전 과정을 실거주자 후기·Journey로 아카이빙합니다.",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "theme_color": "#1f3d36",
  "background_color": "#f8fafc",
  "lang": "ko",
  "icons": [
    {
      "src": "/static/img/logo-c-mark.svg",
      "sizes": "any",
      "type": "image/svg+xml",
      "purpose": "any maskable"
    }
  ]
}
```

- [ ] **Step 2: Modify `app/templates/base.html` head**

Find the `<link rel="apple-touch-icon" ...>` line. Add right after:

```html
  <link rel="manifest" href="{{ url_for('static', path='/manifest.webmanifest') }}">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="Nestory">
```

- [ ] **Step 3: Static check + lint**

Run: `uv run python -c "
import json
with open('app/static/manifest.webmanifest') as f:
    m = json.load(f)
assert m['name'] and m['start_url'] == '/' and m['display'] == 'standalone' and m['icons']
print('manifest valid')
"` → `manifest valid`

- [ ] **Step 4: Commit**

```bash
git add app/static/manifest.webmanifest app/templates/base.html
git commit -m "feat(pwa): add web app manifest + Apple meta tags

manifest.webmanifest (standalone display, theme #1f3d36, SVG icon).
base.html: link rel=manifest + apple-mobile-web-app-* meta.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15b-pwa-design.md §3, §5"
```

---

## Task 2: Kakao inapp UA helper + unit test

**Files:**
- Create: `app/services/kakao_inapp.py`
- Create: `app/tests/integration/test_kakao_inapp.py`

- [ ] **Step 1: Write helper**

```python
# app/services/kakao_inapp.py
"""카카오톡 인앱 브라우저 감지 — UA 기반.

PRD §9.3 P1 종료 기준 [v1.1·B2] 호환성 검증용.
"""
from fastapi import Request


def is_kakao_inapp(request: Request) -> bool:
    """User-Agent에 KAKAOTALK 토큰이 있으면 인앱 브라우저로 판정 (대소문자 무관)."""
    ua = request.headers.get("user-agent", "")
    return "KAKAOTALK" in ua.upper()


__all__ = ["is_kakao_inapp"]
```

- [ ] **Step 2: Write unit test**

```python
# app/tests/integration/test_kakao_inapp.py
"""Tests for is_kakao_inapp UA detection."""
from unittest.mock import MagicMock

from app.services.kakao_inapp import is_kakao_inapp


def _request_with_ua(ua: str) -> MagicMock:
    req = MagicMock()
    req.headers = {"user-agent": ua}
    return req


def test_kakao_ua_detected() -> None:
    assert is_kakao_inapp(_request_with_ua("Mozilla/5.0 KAKAOTALK 9.0.0")) is True


def test_kakao_ua_lowercase_detected() -> None:
    assert is_kakao_inapp(_request_with_ua("kakaotalk/8.0")) is True


def test_chrome_ua_not_detected() -> None:
    assert is_kakao_inapp(
        _request_with_ua("Mozilla/5.0 (Windows NT 10) Chrome/120")
    ) is False


def test_empty_ua_not_detected() -> None:
    assert is_kakao_inapp(_request_with_ua("")) is False


def test_missing_ua_header_not_detected() -> None:
    req = MagicMock()
    req.headers = {}
    assert is_kakao_inapp(req) is False
```

- [ ] **Step 3: Lint + static**

Run: `uv run ruff check app/services/kakao_inapp.py app/tests/integration/test_kakao_inapp.py` → clean
Run: `uv run python -c "from app.services.kakao_inapp import is_kakao_inapp; print('ok')"` → `ok`

- [ ] **Step 4: Commit**

```bash
git add app/services/kakao_inapp.py app/tests/integration/test_kakao_inapp.py
git commit -m "feat(services): add kakao inapp UA detection helper

is_kakao_inapp(request) — UA에 KAKAOTALK 토큰 있으면 True (대소문자 무관).
Unit 5 cases — kakao 정상/대소문자/chrome/empty/missing.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15b-pwa-design.md §6.1"
```

---

## Task 3: Middleware + banner partial + base.html include

**Files:**
- Modify: `app/main.py`
- Create: `app/templates/components/_kakao_inapp_banner.html`
- Modify: `app/templates/base.html`
- Create: `app/tests/integration/test_kakao_inapp_middleware.py`

- [ ] **Step 1: Add middleware to `app/main.py`**

After the existing `app.add_middleware(SessionMiddleware, ...)` block, before `app.mount("/static", ...)`:

```python
from starlette.requests import Request

from app.services.kakao_inapp import is_kakao_inapp


@app.middleware("http")
async def kakao_inapp_middleware(request: Request, call_next):
    request.state.kakao_inapp = is_kakao_inapp(request)
    return await call_next(request)
```

(Place imports at top with other imports.)

- [ ] **Step 2: Write banner partial**

```html
{# app/templates/components/_kakao_inapp_banner.html #}
{% if request.state.kakao_inapp %}
<div class="bg-amber-50 border-b border-amber-200 px-4 py-3 text-sm text-amber-900"
     x-data="{ show: true }" x-show="show">
  <div class="mx-auto max-w-3xl flex items-start gap-3">
    <span class="text-lg">📱</span>
    <div class="flex-1">
      <p class="font-semibold">외부 브라우저에서 열어보세요</p>
      <p class="mt-1 text-amber-800">
        카카오톡 인앱 브라우저에서는 일부 기능(홈 화면 추가, 알림)이 제한됩니다.
        우측 상단 메뉴 → "다른 브라우저로 열기"를 이용해주세요.
      </p>
    </div>
    <button type="button" @click="show = false" class="text-amber-600 hover:text-amber-900" aria-label="닫기">✕</button>
  </div>
</div>
{% endif %}
```

- [ ] **Step 3: Modify `app/templates/base.html` body** to include banner before nav

Find:
```html
<body class="h-full bg-slate-50 text-slate-900 antialiased">
  {% include "components/nav.html" %}
```

Change to:
```html
<body class="h-full bg-slate-50 text-slate-900 antialiased">
  {% include "components/_kakao_inapp_banner.html" %}
  {% include "components/nav.html" %}
```

- [ ] **Step 4: Write integration test**

```python
# app/tests/integration/test_kakao_inapp_middleware.py
"""Middleware sets request.state.kakao_inapp + banner conditional render."""
from fastapi.testclient import TestClient


def test_kakao_ua_shows_banner(client: TestClient) -> None:
    r = client.get("/", headers={"user-agent": "Mozilla/5.0 KAKAOTALK 9.0.0"})
    assert r.status_code == 200
    assert "외부 브라우저에서 열어보세요" in r.text


def test_chrome_ua_no_banner(client: TestClient) -> None:
    r = client.get(
        "/", headers={"user-agent": "Mozilla/5.0 Chrome/120"}
    )
    assert r.status_code == 200
    assert "외부 브라우저에서 열어보세요" not in r.text


def test_no_ua_no_banner(client: TestClient) -> None:
    r = client.get("/", headers={"user-agent": ""})
    assert r.status_code == 200
    assert "외부 브라우저에서 열어보세요" not in r.text
```

- [ ] **Step 5: Static check + lint**

Run: `uv run python -c "from app.main import app; print('app ok')"` → `app ok`
Run: `uv run ruff check app/main.py app/services/kakao_inapp.py app/tests/integration/test_kakao_inapp_middleware.py` → clean

- [ ] **Step 6: Commit**

```bash
git add app/main.py app/templates/components/_kakao_inapp_banner.html app/templates/base.html app/tests/integration/test_kakao_inapp_middleware.py
git commit -m "feat(pwa): add kakao inapp middleware + banner

http middleware caches is_kakao_inapp result on request.state.
base.html includes banner partial — 인앱 브라우저 사용자에게 외부 브라우저 안내.
Alpine으로 ✕ 닫기.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15b-pwa-design.md §6"
```

---

## Task 4: Service Worker + registration script

**Files:**
- Create: `app/static/sw.js`
- Create: `app/static/js/pwa.js`
- Modify: `app/templates/base.html`

- [ ] **Step 1: Write `app/static/sw.js`**

```javascript
const CACHE_VERSION = 'nestory-v1';
const APP_SHELL = [
  '/',
  '/_offline',
  '/static/img/logo-c-full.svg',
  '/static/img/logo-c-mark.svg',
  '/static/manifest.webmanifest',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_VERSION).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  event.respondWith(
    fetch(event.request)
      .then((res) => {
        const copy = res.clone();
        caches.open(CACHE_VERSION).then((cache) => cache.put(event.request, copy));
        return res;
      })
      .catch(() => caches.match(event.request).then((res) => res || caches.match('/_offline')))
  );
});
```

- [ ] **Step 2: Write `app/static/js/pwa.js`**

```javascript
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js', { scope: '/' })
      .catch((err) => console.warn('SW registration failed:', err));
  });
}
```

- [ ] **Step 3: Modify `app/templates/base.html`** — add pwa.js script tag

Find:
```html
  <script src="{{ url_for('static', path='/js/app.js') }}" defer></script>
  <style>[x-cloak] { display: none !important; }</style>
</head>
```

Change to:
```html
  <script src="{{ url_for('static', path='/js/app.js') }}" defer></script>
  <script src="{{ url_for('static', path='/js/pwa.js') }}" defer></script>
  <style>[x-cloak] { display: none !important; }</style>
</head>
```

- [ ] **Step 4: Static check**

Run: `uv run python -c "
from pathlib import Path
sw = Path('app/static/sw.js').read_text()
assert 'CACHE_VERSION' in sw and 'install' in sw and 'fetch' in sw
pwa = Path('app/static/js/pwa.js').read_text()
assert 'serviceWorker' in pwa and 'register' in pwa
print('SW + pwa.js valid')
"` → `SW + pwa.js valid`

- [ ] **Step 5: Commit**

```bash
git add app/static/sw.js app/static/js/pwa.js app/templates/base.html
git commit -m "feat(pwa): add Service Worker + registration script

sw.js: app shell precache + network-first fetch + offline fallback.
pwa.js: navigator.serviceWorker.register on load.
base.html: pwa.js defer script tag.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15b-pwa-design.md §4, §5"
```

---

## Task 5: /_offline route + page template

**Files:**
- Create: `app/templates/pages/_offline.html`
- Modify: `app/routers/pages.py`
- Create: `app/tests/integration/test_offline_route.py`

- [ ] **Step 1: Write template**

```html
{% extends "base.html" %}
{% block title %}오프라인 · Nestory{% endblock %}
{% block content %}
<section class="text-center py-16 space-y-4">
  <p class="text-5xl">📡</p>
  <h1 class="text-2xl font-bold text-slate-900">오프라인입니다</h1>
  <p class="text-slate-600">
    인터넷 연결이 복원되면 자동으로 다시 시도됩니다.
  </p>
  <a href="/" class="inline-block rounded-md bg-emerald-600 px-5 py-2.5 text-white hover:bg-emerald-700">
    홈으로
  </a>
</section>
{% endblock %}
```

- [ ] **Step 2: Add route to `app/routers/pages.py`**

Read existing pages.py first to see the structure. Add at the end:

```python
@router.get("/_offline", response_class=HTMLResponse)
def offline_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/_offline.html", {"current_user": None}
    )
```

(Imports: `Request`, `HTMLResponse`, `templates` should already be present in pages.py.)

- [ ] **Step 3: Write test**

```python
# app/tests/integration/test_offline_route.py
"""GET /_offline returns 200 without auth."""
from fastapi.testclient import TestClient


def test_offline_route_renders_for_anonymous(client: TestClient) -> None:
    r = client.get("/_offline")
    assert r.status_code == 200
    assert "오프라인입니다" in r.text


def test_offline_route_includes_home_link(client: TestClient) -> None:
    r = client.get("/_offline")
    assert r.status_code == 200
    assert 'href="/"' in r.text
```

- [ ] **Step 4: Static check + lint**

Run: `uv run python -c "
from app.main import app
paths = [getattr(r, 'path', '') for r in app.routes]
assert '/_offline' in paths, '_offline route not registered'
print('route registered')
"` → `route registered`
Run: `uv run ruff check app/routers/pages.py app/tests/integration/test_offline_route.py` → clean

- [ ] **Step 5: Commit**

```bash
git add app/templates/pages/_offline.html app/routers/pages.py app/tests/integration/test_offline_route.py
git commit -m "feat(pwa): add /_offline route + template

SW fallback page for cache miss while offline. 비인증 200.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15b-pwa-design.md §7"
```

---

## Task 6: Static PWA fetch test

**Files:**
- Create: `app/tests/integration/test_pwa_static.py`

- [ ] **Step 1: Write tests**

```python
# app/tests/integration/test_pwa_static.py
"""Verify PWA static assets are served correctly."""
import json

from fastapi.testclient import TestClient


def test_manifest_served_and_valid_json(client: TestClient) -> None:
    r = client.get("/static/manifest.webmanifest")
    assert r.status_code == 200
    m = json.loads(r.text)
    assert m["name"]
    assert m["short_name"] == "Nestory"
    assert m["start_url"] == "/"
    assert m["display"] == "standalone"
    assert m["icons"]


def test_sw_js_served(client: TestClient) -> None:
    r = client.get("/static/sw.js")
    assert r.status_code == 200
    assert "CACHE_VERSION" in r.text
    assert "fetch" in r.text


def test_pwa_js_served(client: TestClient) -> None:
    r = client.get("/static/js/pwa.js")
    assert r.status_code == 200
    assert "serviceWorker" in r.text


def test_base_html_includes_manifest_link(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert 'rel="manifest"' in r.text
    assert 'apple-mobile-web-app-capable' in r.text
```

- [ ] **Step 2: Lint**

Run: `uv run ruff check app/tests/integration/test_pwa_static.py` → clean

- [ ] **Step 3: Commit**

```bash
git add app/tests/integration/test_pwa_static.py
git commit -m "test: add PWA static assets serving tests

manifest.webmanifest JSON valid + sw.js + pwa.js served +
base.html includes manifest link.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15b-pwa-design.md §9"
```

---

## Task 7: Full sweep + DoD update

**Files:** none (verification + plan DoD checklist)

- [ ] **Step 1: Full lint**

Run: `uv run ruff check app/`
Expected: clean.

- [ ] **Step 2: Full pytest run (Docker-up PC only — skip if no Docker)**

Run: `uv run pytest app/tests/ -q`
Expected: 모든 테스트 PASS (P1.3+P1.4+P1.4b+P1.5a baseline + 신규 P1.5b 13 추가).

- [ ] **Step 3: Manual Lighthouse check (Docker-up PC)**

서버 실행 후 Chrome DevTools Lighthouse → PWA 카테고리 검사:
- ✅ Web app manifest (manifest.webmanifest detected)
- ✅ Service Worker registered
- ✅ Installable (Chrome "Install Nestory" 프롬프트 사용 가능)

- [ ] **Step 4: Manual mobile/카카오 인앱 QA**

- 일반 모바일 Chrome: 사이트 진입 → 주소창 메뉴 → "홈 화면에 추가" 시도 → Nestory 아이콘으로 추가됨
- 카카오톡 채팅에 사이트 URL 공유 → 카카오 인앱 브라우저로 진입 → 노란 배너 "외부 브라우저에서 열어보세요" 노출

- [ ] **Step 5: Plan DoD 갱신**

이 plan 파일 마지막 DoD 체크 표 갱신.

- [ ] **Step 6: Commit DoD 결과**

```bash
git add docs/superpowers/plans/2026-05-09-nestory-p15b-pwa.md
git commit -m "docs(plans): mark P1.5b PWA DoD — code complete, manual QA deferred

코드·테스트 완료. Lighthouse PWA 검사 + 카카오 인앱 실측은 docker-up PC.

Refs: docs/superpowers/specs/2026-05-09-nestory-p15b-pwa-design.md §9"
```

---

## DoD checklist (2026-05-09 코드 구현 완료)

- [x] manifest.webmanifest JSON 유효 + 모든 필수 필드 (Task 1)
- [x] base.html `<link rel="manifest">` + Apple meta 4종 출력 (Task 1)
- [x] sw.js install/activate/fetch 핸들러 + APP_SHELL precache + offline fallback (Task 4)
- [x] pwa.js navigator.serviceWorker.register (Task 4)
- [x] `/_offline` 라우트 등록 (route 정적 확인 ✅) — 비로그인 200 (Task 5)
- [x] 카카오 UA 시 배너 노출 / 일반 UA 미노출 — middleware + integration test 작성 (Task 3)
- [x] 4 테스트 파일 작성 (kakao helper 5 + middleware 3 + static 4 + offline 2 = 14 신규 테스트). lint clean ✅
- [ ] ⏸ Lighthouse PWA installable — Docker-up PC + 실 배포 환경 필요
- [x] 새 마이그레이션 0건

**구현 commits**: `ec8f84a..4dfe74a` (6 commits).
