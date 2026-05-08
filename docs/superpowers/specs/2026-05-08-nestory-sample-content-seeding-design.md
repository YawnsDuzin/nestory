# Nestory — Sample Content Seeding 설계

**작성일**: 2026-05-08
**대상 단계**: P1.4 (Hub + Search) 종료 직후, P1.5 진입 직전 — dogfood 가치 회복
**관련 PRD**: §4.2 페이지 트리, §5.3 PostMetadata, §6.4 이미지 파이프라인
**관련 메모리**: `project_nestory_handoff.md`

## 1. 배경 및 동기

P1.4가 끝나며 hub/discover/search/feed/profile 5개 화면이 완성됐지만 `seed_demo.py`의 시드 데이터로는 **이미지 0건 · PLAN type 누락 · 댓글 0건** 상태라 다음 화면들이 텍스트만 잔뜩 보이는 모습으로 동작한다. P1.5 진입 전 한 번 더 dogfooding 가치를 회복하고, 동시에 P1.3 이미지 파이프라인(EXIF/resize/WebP)과 P1.4 comments service의 실 사용 검증을 한 번에 끝낸다.

**왜 외부 API(Picsum)?** 사용자가 prompt에서 "웹에서 연관되는 느낌의 이미지" 요청. Pillow 합성 placeholder는 dogfooding 가치 낮음. Unsplash/Pexels는 API key 등록·.env 설정 부담 + license 책임. Picsum은 API key 불필요·즉시 동작·풍경 분위기 충분 — dogfood 시드용으로 가장 실용적.

**왜 sync 이미지 처리?** dispatch enqueue 후 워커 폴링 대기는 비결정적. 시드 종료 시점에 모든 이미지가 READY 상태여야 manual QA가 즉시 가능. 워커 컨테이너 의존도 줄어듦.

## 2. 범위

### 2.1 In-scope

- 신규 파일: `app/scripts/seed_assets/__init__.py`, `app/scripts/seed_assets/picsum.py`
- 수정 파일: `app/scripts/seed_demo.py`
- review · journey episode 각각에 1-3장 Picsum 이미지 첨부 (랜덤)
- PLAN type 4개 추가 (interested 사용자 작성, 0-1장 이미지)
- 각 review·journey ep에 0-3 top-level 댓글 + ~30% 확률 1 reply
- `--reset` 동작 확장: `var/uploads/` 폴더 청소

### 2.2 Out of scope

- 이미지 키워드 매칭 (Unsplash 같은 검색 API)
- 데이터 양 확장 (12 → 30+ review)
- 공지사항(announcement) 시딩 — P1.5 admin 콘솔 작업과 함께
- Q&A의 답변(ANSWER)에 이미지 첨부 — current factory 설계 변경 부담
- migration 추가 (DB 스키마 변경 없음)

## 3. 컴포넌트

| 파일 | 역할 |
|------|------|
| `app/scripts/seed_assets/__init__.py` (신규) | 패키지 마커 (빈 파일) |
| `app/scripts/seed_assets/picsum.py` (신규) | `download_and_attach(post, count)` — Picsum 호출 + bytes를 image 서비스 통과 + 워커 핸들러 sync 호출 + 본문 markdown 삽입 |
| `app/scripts/seed_demo.py` (수정) | PLAN 4개 추가 + review/journey ep 루프에서 `download_and_attach` 호출 + 댓글 시딩 + `--reset` 청소 |

## 4. 이미지 시딩 흐름 (sync)

`download_and_attach(session, post, count, *, base_seq)`:

1. `count = random.randint(1, 3)` 회 반복
2. `httpx.get(f"https://picsum.photos/1280/720?random={base_seq+i}", timeout=5.0)`
3. 실패 시 `warnings.warn(...)` + 해당 첨부 skip (fail open). 누적 실패 ≥ 10이면 시드 abort.
4. bytes를 `app/services/images.py` 의 기존 검증/저장 helper로 통과 — EXIF strip + uuid 파일명 + `Image` row INSERT (`status=PROCESSING`, owner=post.author). **함수명은 plan 시점에 실제 시그니처 확인 후 확정.**
5. `app/workers/handlers/image_resize.py` 의 핸들러를 **dispatch 우회 직접 호출** → thumb 320 + medium 960 WebP 생성, `status=READY` 업데이트. **handler 시그니처도 plan 시점에 확인.**
6. 이미지 ID들을 본문 끝에 `\n\n![](/img/<id>/orig)` 형태로 append (markdown 필터가 `medium`으로 swap)

## 5. PLAN type 4개

`PostType.PLAN`, `interested` 사용자 작성. 4개의 (title, body) 페어:

1. "양평 동향 검토 — 3개 부지 비교 중" / 가족 4인, 예산 5억, 2027년 봄 이주 검토.
2. "곡성 1년 이내 이주 계획" / 은퇴 후 부부, 2026년 가을 입주 목표.
3. "홍천 vs 영월, 어디로 할까?" / 두 지역 장단점 정리, 의견 구함.
4. "은퇴 5년 후, 단독 vs 듀플렉스" / 자녀 가구 합산 가능성 검토.

각 PLAN에 0-1장 Picsum (PostMetadata `PlanMetadata` 통과 보장 — `factory-boy`의 PostFactory `_default_metadata` 분기 사용).

## 6. 댓글 시딩

각 review · journey ep:

```python
top_count = random.randint(0, 3)
for _ in range(top_count):
    author = random.choice([resident_a, resident_b, rv_a, rv_b])
    top = CommentFactory(post=post, author=author)
    if random.random() < 0.30:
        reply_author = random.choice([resident_a, resident_b, rv_a, rv_b])
        CommentFactory(post=post, author=reply_author, parent=top)
```

1-level reply cap (P1.4 정책 준수 — `comments` service의 nested-reply 차단 가드와 일치).

## 7. `--reset` 동작 확장

기존 TRUNCATE 직후 추가 step (uploads 경로 키는 plan 시점에 settings 확인 후 확정):

```python
uploads_dir = settings.<uploads_path_key>  # plan 단계에서 정확한 키 확인
if uploads_dir.exists():
    for child in uploads_dir.iterdir():
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)
else:
    uploads_dir.mkdir(parents=True, exist_ok=True)
```

폴더 자체는 유지 (mount target). 파일/하위 폴더만 청소.

## 8. 에러 처리

- Picsum 단일 호출 실패 → warn + skip. 글은 텍스트만 시딩.
- 누적 실패 ≥ 10 → 시드 abort + 안내: "Picsum 네트워크 차단됨. 방화벽/프록시 점검 또는 image 옵션 비활성 모드 (TBD: --no-images flag) 사용."
- `--no-images` flag는 in-scope 아님 (P1.5+ 필요 시 추가). 현재는 abort만.
- httpx import 안 해도 되는지 확인 — `pyproject.toml`에 이미 추가돼 있어야 함 (kakao OAuth로 이미 사용 중).

## 9. DoD (Definition of Done)

- `uv run python -m app.scripts.seed_demo --reset` exit 0
- DB 카운트:
  - `regions=4`, `users=6`, `posts ≈ 12+5+4+4+~7 = ~32`, `comments ≈ 30~40`, `images ≈ 17×2 = ~34`
- `var/uploads/` 에 orig + thumb320 + medium960 WebP 파일들 존재 (각 이미지당 3 파일)
- 모든 Image row `status=READY`
- 브라우저 manual QA — 6개 화면 :
  - `/discover` — region 카드 + 인기 후기 5개
  - `/hub/yangpyeong` — 양평 후기/Journey/질문 탭
  - `/hub/yangpyeong/reviews` 페이지 — 카드 썸네일 표시
  - `/post/<review_id>` — body markdown 이미지 inline 렌더
  - `/feed` — 최신 글 mixed feed
  - `/search?q=양평` — review/journey/question 결과 출력
- pytest baseline 회귀 없음 (현재 403 pass) — seed_demo가 모듈 import 변경하지 않으므로 영향 없어야 함
