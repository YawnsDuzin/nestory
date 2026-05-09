# Nestory — P1.5b PWA + 카카오 인앱 브라우저 호환 설계

**작성일**: 2026-05-09
**대상 단계**: P1.5b (P1.5 4 sub-plan 중 두 번째)
**관련 PRD**: §9.3 Phase 1 — "PWA manifest + 카카오 인앱 브라우저 호환성 검증 [v1.1 · B2]" · §10
**관련 메모리**: P1.5a 완료 후 진입

## 0. 핵심 결정 요약 (자율 결정)

| 항목 | 결정 |
|---|---|
| Manifest 형식 | `manifest.webmanifest` 정적 JSON. SVG 아이콘 그대로 활용 + 192/512 PNG는 P2 |
| 디스플레이 모드 | `standalone` (홈 화면 추가 시 별도 앱 모양) |
| Theme color | `#1f3d36` (이미 base.html에 정의된 색상 — 일관성 유지) |
| Service Worker | 최소형 — App shell + offline fallback page (`/_offline`) only. 푸시·백그라운드 동기화는 P2 |
| 캐싱 전략 | network-first + cache fallback (정적 리소스 + 마지막 방문 페이지) |
| 카카오 인앱 처리 | UA 기반 서버 사이드 감지. 인앱이면 상단에 "외부 브라우저로 열기" 안내 배너. 강제 우회 X (사용자 선택) |
| 푸시 알림 | P2 (Web Push API + VAPID 키 별도 결정 필요) |

## 1. 배경 및 동기

PRD §9.3 P1 종료 기준에 PWA 명시. 두 가지 동기:

1. **홈 화면 추가** — 시니어 사용자가 매번 브라우저 검색·URL 입력하지 않고 앱 아이콘으로 진입. 시각적 진입 비용 감소.
2. **카카오 인앱 브라우저 호환** — 한국 시니어 사용자의 다수 진입 경로. 인앱 브라우저는 일부 기능 (PWA 설치, 외부 결제 등) 제한 → 사용자에게 외부 브라우저 사용 안내.

오프라인 동작은 본질적 가치 낮음 (콘텐츠 중심 사이트) — 그러나 Service Worker 등록 자체가 "PWA 자격" 조건이라 최소 SW로 충족. 오프라인 시점엔 안내 페이지만.

## 2. 범위

### 2.1 In-scope

- `app/static/manifest.webmanifest` — name, short_name, theme_color, background_color, icons, display, start_url, scope
- `app/static/sw.js` — Service Worker (오프라인 fallback + 정적 자원 캐싱)
- `app/static/js/pwa.js` — SW 등록 + 설치 프롬프트 캡처 (선택적 표시)
- `app/templates/base.html` — `<link rel="manifest">` + `<meta name="apple-mobile-web-app-*">` 추가
- `app/templates/components/_kakao_inapp_banner.html` — 인앱 브라우저 배너 partial
- `app/templates/components/nav.html` — 배너 include (조건부)
- `app/templates/pages/_offline.html` — SW 캐시 미스 시 표시 페이지
- `app/routers/pages.py` 또는 `app/main.py` — `GET /_offline` 라우트 (SW가 fetch 가능)
- `app/services/kakao_inapp.py` — UA detection helper `is_kakao_inapp(request) -> bool`
- 4 테스트 파일 — manifest serving · SW serving · `/_offline` route · kakao detection helper · banner render

### 2.2 Out of scope

- Web Push 알림 (P2 — VAPID 키 + push subscription 모델 필요)
- 백그라운드 동기화 (P2)
- IndexedDB 오프라인 콘텐츠 (P2)
- 192×192 / 512×512 PNG 아이콘 — SVG 1개만 (Android Chrome은 SVG 지원, iOS는 apple-touch-icon SVG 지원 일부 제한이지만 P1 허용 범위)
- 강제 카카오 우회 (kakaolink 외부 호출) — 사용자 선택권 우선
- iOS standalone 가짜 풀스크린 회피 — 일반 표시 OK
- 설치 프롬프트 커스터마이징 (Add to Home Screen 표시 시점 제어) — Chrome 기본 동작 사용

## 3. Manifest

```json
{
  "name": "Nestory · 전원주택 정착 커뮤니티",
  "short_name": "Nestory",
  "description": "은퇴자 전원주택 정착의 전 과정을 실거주자 후기·Journey로 아카이빙합니다.",
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

`/static/` 정적 마운트 그대로 활용 — 별도 라우트 불필요.

## 4. Service Worker

```javascript
// app/static/sw.js
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
  // GET 요청만 캐시 — POST·인증 흐름은 항상 네트워크
  if (event.request.method !== 'GET') return;

  // network-first, fallback to cache, fallback to /_offline
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

**의도적 단순화**:
- POST/PUT/DELETE는 SW 통과 X (Authentication 흐름 보존)
- 모든 GET을 캐싱하지만 network-first로 신선도 우선
- 캐시 만료/제한 정책 X (브라우저 자동 GC 의존)

## 5. SW 등록 + manifest 링크

`app/static/js/pwa.js` 신규:

```javascript
// PWA registration — runs on every page after DOMContentLoaded
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js', { scope: '/' })
      .catch((err) => console.warn('SW registration failed:', err));
  });
}
```

`app/templates/base.html` `<head>` 안에 추가:

```html
<link rel="manifest" href="{{ url_for('static', path='/manifest.webmanifest') }}">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Nestory">
```

기존 `</body>` 이전에 추가:

```html
<script src="{{ url_for('static', path='/js/pwa.js') }}" defer></script>
```

## 6. 카카오 인앱 브라우저 감지 + 배너

### 6.1 UA 패턴

카카오톡 인앱 브라우저 UA는 `KAKAOTALK/<version>` 패턴. 감지 helper:

```python
# app/services/kakao_inapp.py
"""카카오톡 인앱 브라우저 감지 — UA 기반."""
from fastapi import Request


def is_kakao_inapp(request: Request) -> bool:
    """User-Agent에 KAKAOTALK 토큰이 있으면 인앱 브라우저로 판정."""
    ua = request.headers.get("user-agent", "")
    return "KAKAOTALK" in ua.upper()
```

### 6.2 배너 partial

`app/templates/components/_kakao_inapp_banner.html`:

```html
{% if is_kakao_inapp %}
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

`nav.html`의 `<nav>` 직전 또는 base.html `<body>` 직후에 include. base.html이 모든 페이지 공통이므로 base.html에 통합:

```html
<body class="h-full bg-slate-50 text-slate-900 antialiased">
  {% include "components/_kakao_inapp_banner.html" %}
  {% include "components/nav.html" %}
  ...
```

### 6.3 컨텍스트 주입

모든 라우트가 `is_kakao_inapp` 컨텍스트를 받도록 — 가장 깔끔한 방법: 글로벌 템플릿 컨텍스트 함수.

`app/templating.py`에서 `templates` 객체에 `env.globals['is_kakao_inapp']` 등록:

```python
# app/templating.py 수정
from app.services.kakao_inapp import is_kakao_inapp
templates.env.globals["is_kakao_inapp"] = is_kakao_inapp
```

그러나 이 globals는 request 인자를 받는 함수 — 템플릿에서 `{{ is_kakao_inapp(request) }}` 호출 형태가 됨. 더 단순한 방법: 미들웨어로 `request.state.kakao_inapp`에 캐시.

**선택**: 미들웨어 방식. `app/main.py`에 추가:

```python
@app.middleware("http")
async def kakao_inapp_middleware(request: Request, call_next):
    request.state.kakao_inapp = is_kakao_inapp(request)
    return await call_next(request)
```

배너 partial은 `request.state.kakao_inapp` 읽음:

```html
{% if request.state.kakao_inapp %}
```

## 7. /_offline 페이지

`app/templates/pages/_offline.html`:

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

`app/routers/pages.py`에 라우트 추가:

```python
@router.get("/_offline", response_class=HTMLResponse)
def offline_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "pages/_offline.html", {"current_user": None})
```

(SW 캐시 미스 시 fallback이므로 인증 불필요. `current_user=None`으로 렌더.)

## 8. 테스트 전략

| Test file | Verifies |
|---|---|
| `test_pwa_static.py` | `/static/manifest.webmanifest` 200 + JSON 파싱 + name/icons 포함. `/static/sw.js` 200 + JS Content-Type. `/static/js/pwa.js` 200. |
| `test_kakao_inapp.py` | `is_kakao_inapp(request)` UA 매칭 (KAKAOTALK 포함 / 미포함 / 대소문자 비교). |
| `test_kakao_inapp_middleware.py` | 미들웨어가 `request.state.kakao_inapp` 설정. 카카오 UA로 GET / 시 배너 텍스트 노출, 일반 UA는 미노출. |
| `test_offline_route.py` | `GET /_offline` 200, 비로그인 OK, "오프라인" 텍스트 포함. |

## 9. DoD

- [ ] `/static/manifest.webmanifest` JSON 파싱 OK + `name`, `short_name`, `start_url`, `icons` 모두 존재
- [ ] base.html이 `<link rel="manifest">` + Apple meta 4종 출력
- [ ] `/static/sw.js` 응답 200 + `application/javascript` Content-Type
- [ ] `/static/js/pwa.js` SW 등록 코드 포함
- [ ] `GET /_offline` 200 (비로그인 가능)
- [ ] 카카오 UA로 요청 시 배너 텍스트 "외부 브라우저에서 열어보세요" 노출, 일반 UA는 미노출
- [ ] Lighthouse PWA 검사 (수동 — Docker-up PC) — manifest detected · SW registered · installable 만족
- [ ] 4 테스트 PASS (Docker 미가용 시 deferred)

## 10. 구현 task 추정

7-8 task:

1. `manifest.webmanifest` + base.html `<link>` + Apple meta
2. `app/services/kakao_inapp.py` + 단위 테스트
3. 카카오 인앱 미들웨어 등록 + base.html 배너 include + partial 작성 + 미들웨어 테스트
4. `app/static/sw.js` + `app/static/js/pwa.js` + base.html 등록
5. `_offline.html` + `/_offline` 라우트 + 테스트
6. 정적 PWA 테스트 (`/static/manifest.webmanifest` + sw.js fetch)
7. 수동 QA + DoD 갱신
