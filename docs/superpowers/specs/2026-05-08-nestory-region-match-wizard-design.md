# Nestory — Region Match Wizard 설계 (AI 보강)

**작성일**: 2026-05-08
**대상 단계**: P1.5 직전 또는 P1.4b. PRD §1.5.3 [v1.1·B3]에 정의된 Pillar R 핵심 차별화의 첫 정식 구현 + AI 자연어 설명 보강.
**관련 PRD**: §1.5.3 Region Match Wizard, §6.4 [B5] `user_interest_regions`, §5.1 모델, §14 리스크 (콜드 스타트)
**관련 메모리**: `project_nestory_handoff.md` (P1.5 진입 직전 상태)

## 0. 핵심 결정 요약 (브레인스토밍 결과)

| 항목 | 결정 |
|---|---|
| AI 적용 범위 | 추천 이유 자연어 설명만 (점수 계산은 deterministic — 시드 테이블 dot product) |
| LLM provider | claude-haiku-4-5 |
| Integration | **Claude Agent SDK + OAuth** (정적 API key 미사용 — 토큰 회전 가능) |
| 호출 시점 | Sync — 결과 페이지 SSR 시 Top 3 모두 (1-2초 지연 허용) |
| 캐시 | P2로 이월 (작동 후 비용·hit-rate 측정 후 결정) |
| LLM fallback | 정적 점수 breakdown 텍스트 (예: "활동 8 + 의료 6 + 가족 4 + 농사 7 + 예산 5 = 30점") |

## 1. 배경 및 동기

PRD §1.5.3에 Region Match Wizard가 **Phase 1 MVP**로 명시되어 있으나 P1.1·1.2·1.3·1.4까지 미구현. 이유: 점수 매트릭스(`RegionScoringWeight`) 시드 데이터 + 관리자 수기 입력 절차가 별도 결정이었음.

**왜 지금 도입?**
- P1.4 종료로 hub/discover/search/feed/profile 5개 surface가 완성됨. wizard 결과 페이지가 hub로 흘러들어가는 자연스러운 UX 가능.
- 콜드 스타트(섹션 14 리스크) — 신규 가입자가 "어디 시군이 좋아요?" 질문에 의존하지 않게 즉시 답을 줌.
- AI 자연어 설명이 들어가면 단일 점수보다 시니어에게 훨씬 친화적 — "양평이 매칭된 이유: ① 자녀 1시간 거리 ② 단독주택 5억 예산 적합 ③ 텃밭 활동 가능".

**왜 AI는 설명에만?**
점수 계산은 deterministic이어야 함 — Pillar R(Region Match)의 신뢰가 LLM 환각에 흔들리면 차별화 무너짐. AI는 점수의 "이야기화"만 담당. fallback도 정적 텍스트로 graceful degrade.

**왜 Claude Agent SDK + OAuth?**
정적 `ANTHROPIC_API_KEY` 대신 OAuth 토큰 사용 → 회전 가능, 운영자 변경 시 재발급 쉬움. SDK는 retries·prompt caching·error handling 내장. 단일 HTTP 호출보다 장기 유지보수 비용 ↓. (실제 SDK가 OAuth flow를 어떻게 노출하는지는 implementation 시점에 SDK 문서 / `claude-code-guide` 스킬로 검증 — 본 spec은 OAuth 채택을 결정만 명시.)

## 2. 범위

### 2.1 In-scope

- 라우트 4개: `GET /match/wizard`, `GET /match/wizard/q/{n}`, `POST /match/wizard/submit`, `GET /match/result`
- HTMX 단계 전환 + 시니어 친화 UI (1문항 1화면, 큰 글씨, 단계 인디케이터)
- 5문항 정의 (활동·의료·자녀방문·농사·예산) + 각 4 옵션
- `RegionScoringWeight` 모델 + 마이그레이션 + 4 pilot region × 5축 = 20 row 시드
- `app/services/match.py` — `compute_top_regions(answers)` (deterministic) + `generate_explanations(matches, answers)` (LLM)
- Claude Agent SDK 통합 + OAuth env 변수 + fallback 정적 텍스트
- 비로그인: URL params로 결과 인코딩. 로그인: `user_interest_regions(priority=1,2,3)` UPSERT
- 결과 페이지: Top 3 카드 + AI 설명 + 거주자 N명 후기 링크
- 테스트: scoring service unit (deterministic), LLM mock, result route integration

### 2.2 Out of scope

- LLM 응답 캐시 (P2 비용 측정 후 도입 결정)
- 사용자 후기 기반 점수 보정 (PRD §1.5.3 — Phase 3)
- 자유 입력 자연어 위저드 (PRD에 객관식 명시)
- "농사 의향 + 예산" 조합 추가 가중치 같은 미세 보정 (deterministic 단순 dot product 유지)
- 위저드 결과 통계 dashboard (관리자 콘솔에서 P1.5 추가 가능)
- 재실행 시 이전 답변 prefill (URL share 흐름으로 충분)

## 3. AI 적용 영역 — 자연어 설명만

### 3.1 무엇을 LLM이 생성하는가

각 Top 3 region에 대해 **1-2문장 한국어 설명** — 시니어 존댓말, 시군 이름 + 구체적 매칭 이유.

**Prompt 예시** (system + user 조합):

```
[system]
당신은 한국 전원주택 정착 추천 도우미입니다. 시니어 사용자의 라이프스타일 답변과 시군 점수를 보고, 왜 이 시군이 추천되었는지 1-2문장으로 친절하게 설명합니다. 존댓말 사용. 시군 이름과 핵심 매칭 이유 2-3개를 자연스럽게 엮으세요. 절대 점수 자체나 숫자를 본문에 노출하지 마세요.

[user]
시군: 양평군 (경기도)
사용자 라이프스타일:
- 활동: 텃밭·정원
- 의료: 매우 중요
- 자녀 방문: 월 2-3회
- 농사: 텃밭 정도
- 예산: 5-8억

매칭 점수 분포 (참고용, 본문에 직접 노출 금지):
- 활동 8/10, 의료 7/10, 자녀방문 9/10, 농사 7/10, 예산 8/10

설명을 1-2문장으로:
```

**기대 출력 예시**:
> "양평군은 서울에서 1시간 거리라 자녀가 자주 방문하기 좋고, 단독주택 시세가 예산에 잘 맞으며 텃밭 정도의 농사를 즐기시기에도 충분한 환경입니다."

### 3.2 무엇을 LLM이 생성하지 않는가

- region 점수 자체 (deterministic dot product)
- Top 3 선출 (점수 정렬)
- 시군 정보 사실 검증 (시드 데이터에 의존, LLM은 시드 정보만 참고)

LLM이 환각하는 것을 막기 위해 prompt에 region 시드 점수만 제공하고, region 외부 사실은 일절 인용하지 못하게 함. "양평은 한강이 가깝다" 같은 일반 지식은 OK이지만 "양평 인구는 11만명" 같은 사실은 시드에 없으면 prompt에서 제거.

### 3.3 Fallback — LLM 미동작 시

```python
def static_explanation(match: RegionMatch) -> str:
    return (
        f"{match.region.sigungu}이(가) Top {match.rank}로 추천되었습니다. "
        f"5개 항목 매칭 점수 합계 {match.total_score}점."
    )
```

결과 페이지는 항상 200. LLM 호출 실패는 사용자에게 보이지 않음 (점수 있고 설명만 정적).

## 4. 데이터 모델

### 4.1 신규 테이블

```python
# app/models/region_scoring.py
class RegionScoringWeight(Base):
    __tablename__ = "region_scoring_weights"

    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="CASCADE"), primary_key=True
    )
    activity_score: Mapped[int]      # Q1 → 0~10
    medical_score: Mapped[int]       # Q2 → 0~10 (의료 인프라 풍부도)
    family_visit_score: Mapped[int]  # Q3 → 0~10 (수도권 접근성)
    farming_score: Mapped[int]       # Q4 → 0~10 (농지·기후)
    budget_score: Mapped[int]        # Q5 → 0~10 (시세 → 낮을수록 score 높음)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
```

각 점수 정수 0~10. 시드는 alembic migration에서 4 pilot region × 5축 = 20 row INSERT. notes에는 점수 근거(예: "양평 평균 단독주택 매매가 4.5억 → 5-8억 예산 적합 8점").

**Q5 budget**: 시군의 평균 부지·건축 비용을 5축 점수로 변환. 낮은 비용 시군이 "예산 우선" 사용자에게 매칭됨. 변환은 단순 역수 매핑 (시드 시점 결정).

### 4.2 기존 테이블 활용

`user_interest_regions(user_id, region_id, priority)` — P1.1에서 이미 정의됨 (B5). priority 1·2·3에 wizard 결과 Top 3 UPSERT.

## 5. 라우트 + UI

| Method | Path | 역할 |
|---|---|---|
| GET | `/match/wizard` | 시작 화면 ("5문항 답하시면 Top 3 시군을 추천합니다") + Q1로 이동 버튼 |
| GET | `/match/wizard/q/{n}` | n번째 문항 partial (HTMX swap target). 1~5. 답변 받으면 다음 문항으로 swap. |
| POST | `/match/wizard/submit` | 5답변 form-encoded 받기 → 점수 계산 → LLM 3회 호출 → 결과 페이지 redirect (URL params 인코딩) |
| GET | `/match/result?a=A1,A2,A3,A4,A5` | 결과 페이지. URL params 파싱 → 다시 점수 계산 → LLM 호출 → SSR. 로그인 사용자는 `user_interest_regions` UPSERT |

**왜 GET result에서 다시 점수 계산?** Bookmark/공유 가능. URL이 그대로 답변을 담음. 익명 사용자 cookie 미사용 (PRD §6.4 익명 우선).

**왜 LLM이 GET result에서 호출?** 첫 호출은 POST submit에서 → 즉시 redirect. 사용자가 같은 URL을 재방문(bookmark) 시 다시 LLM 호출. 캐시는 P2.

### 5.1 Wizard UI 패턴 (시니어 친화)

- 1문항 1화면 (한 번에 하나만 묻기)
- 큰 글씨 (`text-2xl`), 충분한 간격
- 단계 인디케이터: "2 / 5" 표시
- 4 옵션은 큰 라디오 버튼 (`min-h-12`, full-width)
- "이전" 버튼 (마지막 문항 외)
- "다음" 버튼은 답변 선택 시 활성화

## 6. 5문항 + 옵션 + 점수 매핑

| Q# | 질문 | 옵션 (A~D) | 5축 가중치 |
|---|---|---|---|
| Q1 | 은퇴 후 어떤 활동을 가장 즐기시고 싶으신가요? | A) 텃밭·정원 가꾸기 / B) 등산·자연 산책 / C) 예술·취미 활동 / D) 조용한 휴식 | A→농사·활동 강함, B→활동 강함, C→의료 약간, D→의료 강함·활동 약함 |
| Q2 | 의료 시설 접근성은 얼마나 중요하신가요? | A) 매우 중요 (만성질환) / B) 중요 / C) 보통 / D) 낮음 | A→의료 10, B→7, C→5, D→3 |
| Q3 | 자녀나 가족 방문은 얼마나 자주 예상하시나요? | A) 주 1회 이상 / B) 월 2-3회 / C) 분기 1회 / D) 거의 없음 | A→가족방문 10, B→8, C→5, D→3 |
| Q4 | 농사나 텃밭에 얼마나 시간을 들일 의향이세요? | A) 본격 농업 / B) 텃밭 정도 / C) 마당만 / D) 안 함 | A→농사 10, B→7, C→3, D→0 |
| Q5 | 부지+건축 예산 밴드는? | A) 3억 이하 / B) 3-5억 / C) 5-8억 / D) 8억 이상 | A→예산우선 10, B→7, C→5, D→3 |

**점수 계산** = `Σ (user_weight[axis] × region_score[axis])` for each region. Top 3.

**user_weight 매핑은 services/match.py 안에 명시 상수**:

```python
# app/services/match.py
USER_WEIGHTS = {
    1: {"A": {"activity": 8, "farming": 7, ...}, "B": {...}, "C": {...}, "D": {...}},
    2: {...},
    ...
}
```

**왜 5축 score를 단일 합산?** 단순. 시니어 친화. 가중치 정교화는 P3 사용자 후기 기반 보정 시점에.

## 7. AI 통합 — Claude Agent SDK + OAuth

### 7.1 SDK 의존성

`pyproject.toml`에 추가:

```toml
[project]
dependencies = [
    ...,
    "claude-agent-sdk>=0.1",  # 정확한 패키지 이름은 implementation 시 SDK 문서로 확인
]
```

(SDK 패키지 이름 공식 확인 → Anthropic 공식 SDK가 아닌 Claude Code SDK 변형일 수 있음. claude-code-guide 스킬로 implementation 시점 검증 필요.)

### 7.2 OAuth 설정

```bash
# .env (gitignore)
ANTHROPIC_OAUTH_CLIENT_ID=xxx
ANTHROPIC_OAUTH_CLIENT_SECRET=xxx
ANTHROPIC_OAUTH_REFRESH_TOKEN=xxx
```

`app/config.py`에 추가:

```python
anthropic_oauth_client_id: str = ""
anthropic_oauth_client_secret: str = ""
anthropic_oauth_refresh_token: str = ""
```

`.env.example`에 placeholder. 운영자가 실제 OAuth 발급 후 .env 설정. CI/test에서는 SDK mock.

### 7.3 LLM 호출 wrapper

```python
# app/services/match.py
def generate_explanations(matches: list[RegionMatch], answers: dict[int, str]) -> list[str]:
    """Top 3 region 각각에 대해 1-2문장 설명. 실패 시 fallback."""
    settings = get_settings()
    if not settings.anthropic_oauth_refresh_token:
        return [_static_explanation(m) for m in matches]
    
    client = _get_sdk_client()  # OAuth 토큰 자동 갱신
    explanations = []
    for m in matches:
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _user_prompt(m, answers)}],
                timeout=5.0,
            )
            explanations.append(resp.content[0].text.strip())
        except Exception as e:
            log.warning("match_llm.failed", region_id=m.region.id, error=str(e))
            explanations.append(_static_explanation(m))
    return explanations
```

타임아웃 5초. 실패는 fallback. 누적 실패가 잦으면 `JobKind.NOTIFICATION`으로 admin alert (P1.5 알림 시스템과 연계).

### 7.4 Prompt 캐싱 (선택 — 비용 최적화)

System prompt는 모든 호출 동일 → Anthropic prompt caching 활용. SDK가 자동 처리하지만 명시적으로 `cache_control: {"type": "ephemeral"}` 표시. 비용 ~50% 절감 기대 (3 호출 중 2번이 cached).

## 8. 결과 페이지 + 비로그인 정책

### 8.1 결과 페이지 구성

- 헤더: "추천 시군 Top 3"
- 카드 3개:
  - region 사진 (Region 모델의 cover_image 또는 placeholder)
  - 시군 이름 + 시도
  - **AI 추천 이유** (1-2문장, fallback 시 정적)
  - "거주자 N명의 후기 보기" → `/hub/{slug}` 링크
  - "팔로우" 버튼 (로그인 사용자) — `user_interest_regions` 토글
- 하단: "다른 답변으로 다시 시도" → `/match/wizard`

### 8.2 비로그인 사용자

- URL params에 답변 인코딩 (`?a=A1,A2,A3,A4,A5`)
- "결과를 저장하시려면 로그인하세요" CTA — 로그인 후 자동 `user_interest_regions` UPSERT (next URL 보존 + answers 재사용)
- bookmark/공유 가능

### 8.3 로그인 사용자

- POST submit 시 `user_interest_regions(user_id, region_id, priority)` 3 row UPSERT (priority 1/2/3)
- 같은 사용자가 wizard 재실행 시 기존 row 덮어쓰기

## 9. 에러 처리

| 상황 | 처리 |
|---|---|
| 5문항 미답 (POST submit) | 400 + flash "모든 문항에 답해주세요" |
| URL params 부정 (잘못된 옵션 코드) | 400 + 첫 화면으로 redirect |
| Region 시드 부족 (< 3 region) | 500 — 운영자 점검 필요. 현재 4 pilot region이라 발생 안 해야 함 |
| LLM timeout/error | fallback 정적 설명, 페이지는 200 |
| OAuth 만료 | SDK refresh 자동 시도 → 실패 시 fallback. admin alert (P1.5+) |

## 10. 비용 추정

- Wizard 완료당 3 LLM 호출 (input ~500 tok + output ~150 tok per call)
- claude-haiku-4-5 가격 (2026-05-08 기준): input $1/M, output $5/M
- 호출 1건 비용: 500/1M × $1 + 150/1M × $5 = $0.0005 + $0.00075 = ~$0.001
- Wizard 1회 = ~$0.003
- 일 100 wizard = $0.30/day = ~$9/month
- Prompt caching 50% off → ~$4.5/month

P2 캐시 도입 시 동일 답변 조합 hit-rate 향상 (시니어 답변 분포가 유사할 가능성). 비용 추가 30~50% 절감 기대.

## 11. 테스트 전략

| Test file | Verifies |
|---|---|
| `test_region_scoring_model.py` | Model fields/constraints. seed migration 적용 후 20 row 존재. |
| `test_match_service_scoring.py` | `compute_top_regions(answers)` deterministic. Top 3 정렬 정확. 동점 처리. |
| `test_match_service_llm.py` | `generate_explanations` — SDK mock으로 정상 응답·timeout·error 시 fallback. |
| `test_match_routes.py` | 4 라우트 (wizard 시작·문항 partial·submit·result). HTMX header 검증. URL params 인코딩 round-trip. |
| `test_match_wizard_e2e.py` | 5문항 모두 답한 흐름 → 결과 페이지 → user_interest_regions row 3개 UPSERT (로그인). |

LLM mock은 `unittest.mock.patch` 또는 SDK가 제공하는 dry-run. 실제 OAuth 호출은 절대 테스트에서 하지 않음.

## 12. DoD (Definition of Done)

- 4 라우트 모두 정상 동작 (200/302/400 분기)
- 5문항 wizard UX 시니어 친화 — 1문항 1화면, 큰 글씨, HTMX swap
- 4 pilot region × 5축 시드 데이터 적용 (alembic migration linear chain 유지)
- `compute_top_regions` 결정적 — 같은 입력 → 같은 출력
- LLM 호출 실패 시 fallback 정적 설명 작동, 페이지 항상 200
- 로그인 사용자 wizard 재실행 시 `user_interest_regions` 덮어쓰기
- pytest baseline 회귀 없음 (현재 403 pass)
- 브라우저 manual QA — wizard 끝까지 진행 + 결과 카드 3개 + 링크 클릭 → hub 정상
- 비용 1주일 운영 < $1 (실측)

## 13. 구현 task 추정

10-14 task. 대략적 분해:

1. RegionScoringWeight 모델 + 마이그레이션
2. 4 pilot region × 5축 seed (migration 안에)
3. `app/services/match.py` — `compute_top_regions` (deterministic)
4. Anthropic SDK 의존성 + OAuth env 추가 + .env.example 갱신
5. `generate_explanations` (SDK 통합 + timeout + fallback)
6. `app/routers/match.py` — 4 라우트
7. `app/templates/pages/match/wizard.html` + `q_partial.html` + `result.html`
8. POST submit → user_interest_regions UPSERT (로그인 사용자)
9. 결과 페이지 region 카드 + AI 설명 + hub 링크
10. 5 test 파일 + LLM mock
11. seed_demo에 wizard URL 1개 노출 (홈 페이지 hero?) — 선택
12. main.py 라우터 등록 + nav 링크 (선택)
