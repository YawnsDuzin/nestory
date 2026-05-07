# Nestory — Phase 1.3 (Content + Images) 설계

**작성일**: 2026-05-07
**대상 단계**: P1.2 종료 + factory-boy 도입 직후, P1.4 (허브·검색) 직전
**관련 PRD**: §4.2 페이지 트리, §5.1 모델, §5.3 PostMetadata Discriminated Union, §6.4 이미지 업로드 파이프라인, §6.6 HTMX 패턴
**관련 메모리**: `project_nestory_handoff.md`, `feedback_consistency_first.md`

## 1. 배경 및 동기

Phase 1.1·1.2 까지 데이터 모델·작업 큐·배지·권한 가드가 모두 갖춰졌다. 사용자가 직접 콘텐츠를 만들고 읽는 첫 워크플로우를 P1.3에서 구축한다.

**왜 콘텐츠 + 이미지 묶음?** 두 영역은 강하게 결합되어 있다. 후기·Journey 에피소드는 이미지 없이는 사실상 의미 없는 콘텐츠 (전원주택 후기에 사진 없는 경우 거의 0). 따라서 콘텐츠 작성 라우트와 이미지 업로드 파이프라인을 동일 sub-plan에서 함께 구축한다.

**왜 댓글·like는 미포함?** 사용자가 콘텐츠를 "쓰고 읽는" 핵심 사이클이 P1.3, "상호작용"은 P1.4. 분리하면 P1.3가 25 task 안쪽으로 들어와 P1.2와 비슷한 분량 유지. 또한 P1.4 허브·검색이 댓글·like 카운터 표시와 결합되므로 두 영역을 같이 묶는 것이 자연스럽다.

## 2. 범위

### 2.1 In-scope

- **5 write 라우트**: `/write/review` · `/write/journey` · `/write/journey/{id}/ep` · `/write/question` · `/write/plan`
- **인라인 answer 폼**: `/question/{qid}/answer` POST (post.type=ANSWER 생성)
- **4 detail 페이지**: `/post/{id}` (review·plan·answer 공용) · `/journey/{id}` · `/journey/{id}/ep/{n}` · `/question/{id}`
- **이미지 업로드 파이프라인**:
  - sync: `/htmx/image/upload` (검증 + EXIF strip + 원본 저장 + image row + worker dispatch)
  - async: `image_resize` 워커 핸들러 실구현 (Pillow + thumb320 + medium960 + WebP)
  - 정적 서빙: `/img/{image_id}/{variant}` (orig·thumb·medium·webp)
- **신규 service**: `app/services/posts.py` (5 type별 create) + `app/services/images.py`
- **신규 router**: `app/routers/content.py` + `app/routers/journey.py` + `app/routers/images.py`
- **markdown 렌더링**: `markdown` 라이브러리 + Jinja filter (`/img/{id}/orig` → `/img/{id}/medium` 자동 swap)
- **테스트**: factory-boy 기반 service·route·worker·E2E 테스트 (~40-50건)

### 2.2 Out-of-scope (P1.4+)

- 댓글 (Comment 모델은 P1.1에 있음) — P1.4
- like / scrap (Interaction Table 객체는 P1.1에 있음) — P1.4
- /discover · /hub · /feed (허브·피드) — P1.4
- 검색 (`pg_trgm` + `simple` FTS) — P1.4
- Draft 상태 (status=DRAFT enum 존재하지만 P1.3는 publish only) — P1.5+
- HEIC 입력 지원 (pillow-heif 의존성) — P1.5+
- 이미지 갤러리·캐러셀·라이트박스 — P1.5+
- nginx 정적 서빙 — P1.5+
- /me/drafts, /me/scraps, /me/following — P1.5+
- Admin content 관리 (`/admin/content`) — P1.5

## 3. 아키텍처

### 3.1 신규 라우터 (3개)

```
app/routers/
├── content.py      # /write/review · /write/question · /write/plan
│                   # /post/{id} · /question/{id} · /question/{qid}/answer
├── journey.py      # /write/journey · /write/journey/{id}/ep
│                   # /journey/{id} · /journey/{id}/ep/{n}
└── images.py       # /htmx/image/upload (POST) · /img/{id}/{variant} (GET)
```

기존 `me.py`·`admin.py`·`auth.py`·`pages.py` 그대로. `app/main.py`에 3개 라우터 등록.

**왜 분리?** content.py 만 두면 6+개 라우트 응집되어 journey episode 흐름이 묻힘. journey는 sub-resource 라우트 응집을 위해 별도 파일. images는 정적 서빙 + HTMX 업로드 완전히 다른 관심사라 별도.

### 3.2 신규 서비스 (2개)

#### 3.2.1 `app/services/posts.py`

CLAUDE.md `## 네이티브 확장 대비` 4원칙 준수:
- 첫 인자 `db: Session`, 두 번째 `user/author: User`
- `request.session` / `Cookie` / `Request` import 금지
- ORM `Post` 객체 반환 (P2 시점 `XxxRead` Pydantic 스키마 도입 시 `response_model=` 직결)

시그니처:

```python
def create_review(db: Session, author: User, region: Region, payload: ReviewMetadata,
                  title: str, body: str) -> Post: ...

def create_journey(db: Session, author: User, region: Region,
                   title: str, description: str | None,
                   start_date: date | None) -> Journey: ...

def create_journey_episode(db: Session, author: User, journey: Journey,
                           payload: JourneyEpisodeMetadata,
                           title: str, body: str) -> Post: ...

def create_question(db: Session, author: User, region: Region, payload: QuestionMetadata,
                    title: str, body: str) -> Post: ...

def create_answer(db: Session, author: User, parent_question: Post, body: str) -> Post: ...

def create_plan(db: Session, author: User, region: Region, payload: PlanMetadata,
                title: str, body: str) -> Post: ...

def increment_view_count(db: Session, post: Post) -> None: ...
```

각 함수가 type별 Pydantic 모델을 인자로 받고 `payload.model_dump(by_alias=False, exclude_none=True)`를 `Post.metadata`에 저장. region/parent_question 같은 ORM 객체로 받음 (FK id 아님). 라우트가 `db.get`으로 미리 조회 + ownership 검증 후 전달.

create_journey_episode는 (journey_id, episode_no) UNIQUE 보장 — `journey.posts` 중 max(episode_no)+1 자동.

#### 3.2.2 `app/services/images.py`

```python
def validate_upload(file: UploadFile) -> tuple[bytes, str, int, int]: ...
    # 반환: (raw_bytes, mime, width, height) — 이후 strip_exif 입력으로 사용

def strip_exif(raw: bytes, mime: str) -> bytes: ...
    # GPS·카메라 정보·기타 EXIF 모두 제거 (Pillow save without exif)

def store_original(db: Session, owner: User, raw_clean: bytes,
                   ext: str, width: int, height: int) -> Image: ...
    # uuid4 → file_path = f"images/{uuid}/orig.{ext}"
    # IMAGE_BASE_PATH 아래 디렉토리 생성 + 저장
    # Image row insert (status=PROCESSING)

def dispatch_resize(image: Image) -> None: ...
    # workers.queue.enqueue(JobKind.IMAGE_RESIZE, {"image_id": image.id})

def upload_image(db: Session, owner: User, file: UploadFile) -> Image: ...
    # 위 4개 합성 — 라우트가 호출하는 단일 entrypoint
```

`upload_image` 가 sync 부분 모두 실행 후 `Image` 반환 (status=PROCESSING). 라우트는 `image.id` + 원본 URL을 JSON으로 응답.

### 3.3 워커 핸들러 실구현

기존 stub `app/workers/handlers/image_resize.py` 실구현:

```python
@register(JobKind.IMAGE_RESIZE)
def handle_image_resize(payload: dict[str, Any]) -> None:
    image_id = payload["image_id"]
    with SessionLocal() as db:
        img = db.get(Image, image_id)
        if not img or img.status == ImageStatus.READY:
            return  # idempotent

        try:
            base_dir = Path(settings.image_base_path) / "images" / str(image_id)
            orig_path = Path(settings.image_base_path) / img.file_path_orig
            with PILImage.open(orig_path) as src:
                thumb = _resize_to_width(src, 320)   # PIL Image.thumbnail
                medium = _resize_to_width(src, 960)
                _save(thumb, base_dir / "thumb.jpg", "JPEG", quality=85)
                _save(thumb, base_dir / "thumb.webp", "WEBP", quality=80)
                _save(medium, base_dir / "medium.jpg", "JPEG", quality=88)
                _save(medium, base_dir / "medium.webp", "WEBP", quality=82)

            img.file_path_thumb = f"images/{image_id}/thumb.jpg"
            img.file_path_medium = f"images/{image_id}/medium.jpg"
            img.file_path_webp = f"images/{image_id}/medium.webp"
            img.status = ImageStatus.READY
        except Exception as e:
            img.status = ImageStatus.FAILED
            log.error("image_resize.failed", image_id=image_id, error=str(e))
            raise  # 큐가 mark_failed + retry backoff
        finally:
            db.commit()
```

**WebP 우선순위**: thumb·medium 둘 다 webp 생성하지만 모델 컬럼 `file_path_webp` 1개라 medium.webp 만 저장 (PRD §6.4 "원본·medium의 WebP" — 원본 webp는 P1.5+ CDN).

**RPi 부하**: 10MB 사진 1장 ~1.5–3초. 워커 1개 동시 처리, 큐가 직렬화하므로 동시성 문제 없음.

### 3.4 정적 서빙 — `/img/{image_id}/{variant}`

```
GET /img/{image_id}/{variant}
  variant ∈ {orig, thumb, medium, webp}
```

- DB에서 image 조회 → 존재 안 하면 404
- variant 가 아직 처리 안 됐으면 (file_path_*가 NULL) → orig으로 graceful fallback
- 권한 체크 없음 (published post 의 첨부 이미지는 공개)
- `Cache-Control: public, max-age=86400` 헤더 (1일 브라우저 캐시)
- soft-deleted post 의 image도 일단 서빙 (P1.4에서 정밀 권한 검토)

대안 검토: nginx 직접 서빙 → P1.5+ 검토. P1.3은 FastAPI FileResponse.

### 3.5 5 write 라우트 매트릭스

| 경로 | 가드 | post.type | metadata | 특수 |
|---|---|---|---|---|
| GET·POST `/write/review` | `require_badge(RESIDENT)` 🏡 | REVIEW | ReviewMetadata | region 자기 region 자동 |
| GET·POST `/write/journey` | `require_badge(RESIDENT)` 🏡 | (Journey row) | — | 생성 후 → `/journey/{id}` redirect |
| GET·POST `/write/journey/{id}/ep` | `require_badge(RESIDENT)` + journey 소유 | JOURNEY_EPISODE | JourneyEpisodeMetadata | episode_no = max+1 자동 |
| GET·POST `/write/question` | `require_login()` 🔒 | QUESTION | QuestionMetadata | region 선택 |
| 인라인 POST `/question/{qid}/answer` | `require_login()` 🔒 | ANSWER | AnswerMetadata (빈) | parent_post_id, region 상속 |
| GET·POST `/write/plan` | `require_login()` 🔒 | PLAN | PlanMetadata | region = primary_region 또는 폼 선택; 미설정 시 "관심 region 등록" 메시지 |

### 3.6 폼 일관성 — 4-section 구조

5 type 모두 동일 4-section:

```
1. 헤더 카드        — type 라벨 + 가이드 한 줄
2. 공통 필드 카드   — title input + body textarea + 이미지 첨부 버튼
3. type별 metadata  — Pydantic 모델 미러 (input 필드)
4. 발행 카드        — region select + [발행] 버튼
```

템플릿 구조:

```
app/templates/pages/write/
├── _base.html                # 4-section 레이아웃
├── _common_fields.html       # title, body, image-attach
├── _publish_card.html        # region select + 발행
├── _meta_review.html         # ReviewMetadata 필드
├── _meta_journey_episode.html
├── _meta_question.html
├── _meta_plan.html
├── review.html               # _base + _meta_review
├── journey_create.html       # Journey row 생성용 (title·desc·region·start_date)
├── journey_episode.html
├── question.html
└── plan.html
```

journey 만 별도 폼 (Journey row 생성, post 아님). answer는 인라인 폼이라 별도 partial 없음.

### 3.7 이미지 첨부 UX (HTMX)

```html
<!-- _common_fields.html -->
<input type="file" name="image" accept="image/jpeg,image/png,image/webp"
       hx-post="/htmx/image/upload"
       hx-trigger="change"
       hx-encoding="multipart/form-data"
       hx-on::after-request="insertMarkdown(event)">
<script>
  function insertMarkdown(e) {
    if (e.detail.successful) {
      const data = JSON.parse(e.detail.xhr.responseText);
      const ta = document.getElementById('body-textarea');
      ta.value += `\n\n![](${data.url})`;
    }
  }
</script>
```

`/htmx/image/upload` 응답: `{"image_id": 42, "url": "/img/42/orig"}` (JSON). HTMX 가 받은 응답을 JS 가 markdown 텍스트로 textarea에 삽입.

**왜 JSON 응답?** CLAUDE.md "이미지 업로드 라우트가 path 문자열만 반환 → JSON API 추가 시 응답 재설계 필요" 안티패턴 회피. **id + url 둘 다 반환**으로 P2 dual-mode 전환 비용 0.

### 3.8 form → service 변환 패턴

라우트 핸들러 (`/write/review` 예시):

```python
@router.post("/write/review")
async def submit_review(
    user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    db: Session = Depends(get_db),
    title: str = Form(...),
    body: str = Form(...),
    region_id: int = Form(...),
    house_type: Literal["단독", "타운하우스", "듀플렉스"] = Form(...),
    size_pyeong: int = Form(...),
    satisfaction_overall: int = Form(...),
    # ... 나머지 ReviewMetadata 필드
):
    region = db.get(Region, region_id)
    if not region:
        raise HTTPException(400, "유효하지 않은 region")
    try:
        meta = ReviewMetadata(
            house_type=house_type, size_pyeong=size_pyeong,
            satisfaction_overall=satisfaction_overall, ...
        )
    except ValidationError as e:
        return form_error_response(e)
    post = posts_service.create_review(db, user, region, meta, title, body)
    return RedirectResponse(f"/post/{post.id}", status_code=303)
```

라우트는 ① form → Pydantic 변환 + ValidationError catch ② service 호출 ③ redirect 만. 비즈니스 로직 0줄.

### 3.9 4 detail 페이지

| 경로 | 가드 | 콘텐츠 | 노출 |
|---|---|---|---|
| `/post/{id}` | Public | review·plan·answer 공용 | author·region·published_at·body(markdown→HTML)·metadata 카드 |
| `/journey/{id}` | Public | Journey 헤더 | title·description·cover·start_date·status + 에피소드 카드 리스트 |
| `/journey/{id}/ep/{n}` | Public | 단일 에피소드 | post.type=JOURNEY_EPISODE 1건 + 이전/다음 ep 네비 |
| `/question/{id}` | Public | Q&A 스레드 | question 본문 + 답변 리스트 + 인라인 answer 폼 (require_login) |

**404 처리**: post.deleted_at IS NOT NULL 또는 status != PUBLISHED → 404. journey.deleted_at IS NOT NULL → 404.

**author 자기 hidden 도 본인은 봐야 함** → P1.4 검토. P1.3은 단순 "published 만 노출".

#### 3.9.1 metadata 카드 — type별 4 partial

```
app/templates/pages/detail/
├── _base.html
├── post.html
├── journey.html
├── journey_episode.html
├── question.html
├── _meta_card_review.html
├── _meta_card_plan.html
├── _meta_card_journey_ep.html
└── _meta_card_question.html
```

post.html 안에 `{% if post.type == "review" %}{% include "detail/_meta_card_review.html" %}` 5분기. 작성 폼 partial과 1:1 대칭 — 향후 type 추가 시 두 partial만 추가.

#### 3.9.2 view_count 증가

GET /post/{id} 진입 시 `Post.view_count += 1` 단순 증가. 동일 IP 중복 카운트 무시 (P1.4 정밀화). 라우트에서 1줄 update + commit.

### 3.10 markdown 렌더링

`markdown` 라이브러리 + Jinja filter (`app/templates/filters.py` 신규):

```python
def markdown_to_html(text: str) -> str:
    html = markdown.markdown(text, extensions=["fenced_code", "nl2br"])
    # /img/{id}/orig → /img/{id}/medium 자동 swap (대역폭 절약)
    html = re.sub(r'src="/img/(\d+)/orig"', r'src="/img/\1/medium" loading="lazy"', html)
    return html
```

- `markdown` (pure-python, RPi 안전, raw HTML 무시 → XSS 방어)
- /img/{id}/orig → medium 자동 변환 — 작성 시 항상 orig 삽입, 표시 시점 swap
- 워커가 아직 medium 안 만든 경우 라우트가 orig fallback → 정상 표시

### 3.11 ENV·설정

`app/config.py` 갱신:

```python
class Settings(BaseSettings):
    ...
    image_base_path: Path = Path("./media")          # local; prod: /var/nestory/media
    max_upload_size: int = 10 * 1024 * 1024
    image_max_dimension: int = 6000
```

`.gitignore`에 `media/` 추가. `docker-compose.local.yml` worker 서비스에 `volumes: - ./media:/app/media` 마운트 추가.

## 4. 테스트 전략 (factory-boy 기반)

CLAUDE.md `## Architecture > 테스트 데이터` 원칙 준수 — 직접 `Post(...)` 생성자 호출 0건.

| 테스트 파일 | 사용 factory | 검증 대상 |
|---|---|---|
| `test_posts_service.py` | `UserFactory`·`RegionFactory`·`JourneyFactory`·type별 `*PostFactory` | 5 type create + view_count + Pydantic 검증 통과 |
| `test_images_service.py` | `UserFactory` + `tests/fixtures/sample.jpg` | validate·strip_exif·store_original·dispatch |
| `test_image_resize_handler.py` | `ImageFactory(status=PROCESSING)` + 실제 파일 + `process_one()` | thumb/medium/webp 생성 + status=READY |
| `test_content_routes.py` | `ResidentUserFactory`·`UserFactory` + `_login_cookie` (P1.2 패턴) | 5 write 라우트 + ValidationError 400 |
| `test_detail_routes.py` | type별 `*PostFactory` | 4 detail 페이지 + 404 처리 + view_count |
| `test_image_upload_route.py` | `UserFactory` + multipart upload | JSON 응답 + image_id + url |
| `test_image_serve_route.py` | `ImageFactory` + variant fallback | FileResponse + Cache-Control |
| `test_post_workflow_e2e.py` | `ResidentUserFactory` + 실제 이미지 | 로그인→업로드→write/review→detail 표시 전체 |

**fixtures 신규**: `app/tests/fixtures/sample.jpg` (실제 JPEG 200x200, EXIF 포함) — 검증·EXIF strip·resize 공용.

## 5. Definition of Done

- [ ] 5 write 라우트 모두 동작 (가드 통과 시)
- [ ] 4 detail 페이지 모두 동작 (404 처리 포함)
- [ ] 인라인 answer 폼 동작
- [ ] 이미지 업로드 → markdown 삽입 → detail 표시 전체 흐름
- [ ] image_resize 워커가 thumb/medium/webp 생성 + status=READY 갱신
- [ ] EXIF strip 검증 (sample.jpg with GPS → 처리 후 EXIF 없음)
- [ ] view_count 증가 검증
- [ ] PostMetadata Pydantic 검증 모든 5 write 경로에서 강제 (잘못된 metadata POST → 400)
- [ ] `pytest app/tests/ -q` 통과 (기존 166 + 신규 ~40-50 = ~210 예상)
- [ ] `ruff check app/` 통과
- [ ] CLAUDE.md `## 네이티브 확장 대비` 4원칙 준수 (`grep -r "request.session" app/services/` 비어있음)
- [ ] CLAUDE.md `## Architecture > 테스트 데이터` 원칙 준수 (직접 `Post(...)` 0건)
- [ ] `media/` gitignore + docker-compose worker volume 마운트
- [ ] `markdown` 의존성 추가 (`uv add markdown`)
- [ ] 새 alembic 마이그레이션 없음 (모든 모델 P1.1에서 정의됨)

## 6. Open Items (P1.3 진입 전 결정)

- **OI-P1.3-1**: markdown 라이브러리 — `markdown` (pure Python, GFM partial) vs `markdown-it-py` (CommonMark 정식, 더 무거움). **잠정**: `markdown`.
- **OI-P1.3-2**: 이미지 동시 첨부 N개 제한 — **잠정**: 5개. textarea 작성 중 5번 첨부 시 차단 (HTMX hx-on 으로 카운트).
- **OI-P1.3-3**: Plan region 처리 — Post.region_id NOT NULL 제약. **잠정**: user.primary_region_id 자동 사용 + 미설정 시 "관심 region 등록 후 작성" 메시지.
- **OI-P1.3-4**: post body 최대 길이 — 모델은 Text 무제한. **잠정**: 50KB hard cap (10MB 마크다운 도배 방지).
- **OI-P1.3-5**: image owner == post author 검증 — markdown `/img/{id}/...`가 다른 user 의 image 일 수 있음. **잠정**: P1.3 검증 안 함 (URL 추측 어려움). P1.4에서 중앙 검증.

## 7. 비목표 (확인용)

- 댓글, like, scrap 액션 (P1.4)
- /discover, /hub, /feed (P1.4)
- 검색 (P1.4)
- Draft 상태·autosave (P1.5+)
- HEIC 입력 (P1.5+)
- 이미지 갤러리·라이트박스 (P1.5+)
- nginx 정적 서빙 (P1.5+)
- /me/drafts·/me/scraps·/me/following (P1.5+)
- Admin content 관리 (P1.5)
- ImageFactory `with_thumbnails()` trait (P1.3 미사용 시 미도입; P1.4+ 시 필요할 때 추가)

## 8. 후속 작업

- **P1.4 (허브·검색)**: /discover · /hub/{slug} · 댓글 · like/scrap · `pg_trgm` 검색
- **P1.5 (알림·관리자·PWA)**: 카카오 알림톡 · /admin/content · PostHog 통합 · PWA manifest
- **PostFactory 신규 type 추가 시**: `app/tests/factories/post.py:_default_metadata`에 분기 추가 + `app/templates/pages/write/_meta_<type>.html` + `app/templates/pages/detail/_meta_card_<type>.html` 둘 다 추가
