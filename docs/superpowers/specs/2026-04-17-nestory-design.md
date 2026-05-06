# Nestory 제품 요구사항 문서 (PRD)

**문서 버전**: 1.1
**작성일**: 2026-04-17 (v1.0) · **2026-05-06 갱신 (v1.1)**
**상태**: 초안 (사용자 리뷰 대기)
**작성**: Claude + 제품 오너 (브레인스토밍 세션)

### 변경 이력

| 버전 | 일자 | 주요 변경 |
|---|---|---|
| 1.0 | 2026-04-17 | 초안 — 비전·차별화 축·데이터 모델·로드맵·NFR 정리 |
| 1.1 | 2026-05-06 | 구조적 부채·콘텐츠 갭·운영 신뢰 보강 14개 항목 반영 (A1–A4, B1–B5, C1–C5). 자세한 위치는 각 섹션 인라인 노트 `[v1.1]` 참조 |
| 1.1.1 | 2026-05-06 | **OI-14 확정 — PostHog Cloud free 채택**. §10·§11·§14.5·§15 갱신 |

#### v1.1 변경 요약 (인덱스)

| 코드 | 영역 | 반영 위치 |
|---|---|---|
| **A1** | 백그라운드 작업 큐 PG 기반 영속화 | §6.1 · §6.7 (신설) |
| **A2** | 한국어 검색 Phase 1부터 (`pg_trgm` + 형태소 1단계) | §5.2 · §9.3 |
| **A3** | `Post.metadata` Pydantic Discriminated Union | §5.3 · §6.2 |
| **A4** | 알림 채널 — 카카오 알림톡 우선 | §9.4 · §15 (OI-12) |
| **B1** | 예비자 "내 정착 계획" Post type | §2.1 · §4.2 · §5.1·§5.3 |
| **B2** | PWA + 카카오 인앱 브라우저 호환 | §10 |
| **B3** | Resident 재검증·이사·`ex_resident` | §5.1 · §5.4 |
| **B4** | Pillar T 인센티브 강화 (회고 배지) | §1.5.1 |
| **B5** | 다중 관심 지역 (`user_interest_regions`) | §5.1 |
| **C1** | 후기 cross-validation (거주자 동의/이의) | §1.5.4 (신설) · §5.1 |
| **C2** | 권한 가드 표준 패턴 (`require_badge`) | §6.2 · §4.3 |
| **C3** | Soft delete 일관성·탈퇴 시 익명화 정책 | §5.1 · §8.3 (신설) |
| **C4** | Analytics 도구·이벤트 카탈로그 | §10 · §14 |
| **C5** | Phase 게이트에 스키마 안정성 게이트 | §9.6 |

---

## 0. 요약 (Executive Summary)

**Nestory** (Nest + Story, 둥지 + 이야기) 는 은퇴자와 전원주택 예비 입주자를 위한 커뮤니티 웹 서비스입니다. 핵심 가치는 **"전원주택 정착의 전 과정 — 터잡기 → 건축 → 입주 → 3년차 — 을 실거주자의 솔직한 여정으로 아카이빙하고, 예비 은퇴자가 실패·후회 없이 결정할 수 있도록 돕는다."** 입니다.

사용자는 크게 **예비 은퇴자(검토자)** 와 **실거주 은퇴자** 로 나뉘며, 거주자가 콘텐츠를 공급하고 예비자가 소비하는 하이브리드 구조입니다. 제품의 히어로 기능은 **구조화된 입주 후기** 와 **타임라인형 정착 일지(Journey)** 로, 둘은 단일 데이터 모델로 통합됩니다.

초기 버전은 **수도권 근교 5개 시군 파일럿** 으로 시작하고, 기술 스택은 **Python · FastAPI · PostgreSQL · Jinja2 · HTMX · Alpine.js** 를 사용해 **라즈베리파이에서 호스팅** 하는 프로토타입 구조입니다. 신뢰는 **4단계 하이브리드 배지 시스템** 으로 확보합니다.

전체 개발은 **Phase 0–3 (약 27주, 6.5개월)** 로 분해되며, 각 Phase 끝은 독립적으로 출시 가능한 증분입니다. 수익화는 Phase 3 (시공사 디렉토리·리드)에서 도입합니다.

---

## 1. 비전 및 목표

### 1.1 제품 비전

> 전원주택 정착의 전 과정을 실거주자의 솔직한 여정으로 아카이빙하고, 예비 은퇴자가 실패·후회 없이 결정할 수 있도록 돕는 모바일 퍼스트 웹 커뮤니티.

### 1.2 북극성 지표 (North Star Metric)

**"검증된 입주 후기 + 진행 중 Journey의 합계 × 월간 활성 예비자 수"**

콘텐츠 공급(거주자)과 수요(예비자) 가 양쪽 모두 성장해야 지표가 증가하는 복합 구조. 한쪽만 성장하면 의미가 없음.

### 1.3 포지셔닝

| 경쟁 제품 | 핵심 도메인 | Nestory와의 차이 |
|---|---|---|
| 호갱노노 | 도시 아파트 · 투자 | Nestory는 **전원주택 · 정착·삶의 질** |
| 오늘의집 | 인테리어 · 커머스 | Nestory는 **집 외부 + 지역 + 여정** |
| 네이버 카페 | 레거시 PC 중심 | Nestory는 **모바일 · 구조화 · 검색성** |
| 당근 | 현재 거주자 이웃 | Nestory는 **예비자 + 거주자 브리지** |
| 직방 · Zillow | 거래 중개 | Nestory는 **커뮤니티 · 콘텐츠 아카이브** |

**시장 공백**: "예비 입주자가 기존 입주자의 3–5년 여정을 시간순으로 볼 수 있는 모바일 앱"은 국내에 없음. 특히 **"실패·후회 포인트"를 검증된 실명으로 공유** 하는 포맷이 비어 있음. (근거: 섹션 A 레퍼런스 리서치 참조)

### 1.4 핵심 가치 제안

| 대상 | 가치 | 근거 |
|---|---|---|
| **예비 은퇴자** | 실패 사례 기반 의사결정 단축 | 배지로 검증된 후기, Journey로 3년치 경험 압축 |
| **실거주 은퇴자** | 경험이 사라지지 않는 아카이브 + 지역 연결 | 오프라인 카페보다 구조화·검색성·영속성 |
| **관리자** | 품질과 신뢰를 지키는 도구 | 배지 시스템으로 자연스러운 품질 계층 |

### 1.5 차별화 축 (Differentiation Pillars)

핵심 경쟁자(네이버 카페·호갱노노·오늘의집·당근)가 구조적으로 추격하기 어려운 3개 축. PRD 전반의 데이터 모델·UX 결정은 이 축을 강화하는 방향으로 정렬한다.

#### 1.5.1 Time-lag Review · 시간차 회고 (Pillar T)

**정의**: 1년차 입주 후기 작성자에게 동일 항목 템플릿을 재작성하도록 알리고, 1년차/3년차 응답을 *동일 사용자·동일 집* 단위로 비교하는 페이지를 자동 생성.

**왜 차별점인가**:
- 카페·블로그는 "지금 글"만 보여줌. 동일 인물의 시간 경과 변화는 추적 불가.
- 호갱노노·오늘의집은 단발성 후기 구조 — 시계열 자산 없음.
- "1년차 만족도 9 → 3년차 6, 가장 후회한 결정: 보일러 연료" 같은 콘텐츠가 의사결정 임팩트 가장 큼.

**구현 윤곽**:
- `Post`(type=review)에 `review_year_offset INT NOT NULL` 추가. 1년차=1, 3년차=3.
- `parent_review_id` 자가참조로 동일 집의 후속 후기 연결.
- 1년차 작성 +24개월 시점 알림 큐(`scheduled_notification` 테이블) — 3년차 재작성 유도.
- `/review/{id}/timelapse` 라우트: 1년차/3년차 동일 항목 좌우 비교 뷰.
- 데이터 충분 시 시군 허브에 "1→3년차 만족도 변화 분포" 차트 노출.

**[v1.1 · B4] 응답률 인센티브 — 알림 단일 의존 회피**:

24개월 후 알림 1회로는 응답률이 낮을 가능성이 큼 (이메일 도달률·시니어 인박스 행태 고려). 알림 외에도 **응답을 매력적으로 만드는 구조** 를 데이터·UX 양쪽에 심어 차별화 축이 데이터로 살아남도록 한다.

- **3년차 회고 작성자 전용 배지**: `🌳 3년차 회고` (resident 배지의 표시 속성 추가). 1→3년차 후기 쌍을 완성한 사용자에게 자동 부여.
- **허브·프로필 상단 노출**: 3년차 회고 완료 후기는 시군 허브 후기 탭 상단에 "검증된 시계열" 라벨로 우선 노출 (정렬 가중치 +).
- **알림 다채널화**: §9.4 카카오 알림톡(A4) 우선 + 이메일·앱 내 배너 동시 발송. 24·26개월 시점 2회 리마인더 + 작성 시작 후 14일 임시저장 만료 알림.
- **응답 시점 1·3년 외 보강 옵션**: 6개월·1년·3년차 3시점 입력으로 확장 가능 (`review_year_offset` 값만 늘리면 됨, 스키마 변경 불필요).
- **성공 메트릭**: 1년차 작성자 중 3년차 재작성률 ≥ 25% (Phase 3 초기 게이트). 미달 시 인센티브 재설계.

**마일스톤**: Phase 2(데이터 모델 + 1년차 후기 작성) → **Phase 3(2027 하반기, 1년차 누적 시점)에 알림·비교 뷰 활성화**. 데이터가 쌓이지 않은 초기엔 코드만 준비.

#### 1.5.2 Regret Cost Aggregator · 후회 비용 정량화 (Pillar C)

**정의**: 후기·Journey 작성 시 *"이 결정으로 추가 발생한 손실 추정액·시간"* 을 항목별 선택 입력. 시군·결정 카테고리별로 통계 집계.

**왜 차별점인가**:
- 단일 후기보다 *합산된 후회 통계* 가 예비자의 의사결정 임팩트 큼.
- 카페·블로그는 자유 서술이라 합산 불가.
- "양평 평균 후회 비용 1,200만 원, 1위 항목: 진입로 포장(40%)" 같은 메트릭은 정성 후기가 도달 못 하는 수준의 신뢰를 제공.

**구현 윤곽**:
- `Post.metadata` JSONB에 `regret_items: [{category, cost_krw_band, time_months_band, free_text}]` 추가.
- `cost_krw_band`는 라디오 선택지(밴드: ~100만 / 100–500만 / 500–2000만 / 2000만+) — 정확한 금액 노출 회피, 통계 산출에 충분.
- `regret_category`는 enum(`land`/`design`/`build`/`move`/`life`/`region`).
- 시군 허브에 `/hub/{slug}/regret` 통계 페이지: 카테고리별 후회 비용 분포.
- 안티패턴: "투자 손실"·"시세 하락"은 카테고리에서 제외 — 정착 결정 회고에만 적용 (안티패턴 OI에 명시).

**마일스톤**: Phase 2(후기 템플릿 v1과 함께 출시). 통계 페이지는 후기 50건 누적 후 시군 허브에 표시.

#### 1.5.3 Region Match Wizard · 지역 매칭 위저드 (Pillar R)

**정의**: 신규 가입자에게 5문항(은퇴 후 활동 / 의료 우선도 / 자녀 방문 빈도 / 농사 의향 / 예산 밴드)을 단계별 위저드로 묻고 *"당신에게 맞는 시군 Top 3"* 를 즉시 제시. 시니어 친화 UX(큰 글씨·1문항 1화면·단계 인디케이터).

**왜 차별점인가**:
- 신규 예비자의 **콜드 스타트 문제**(섹션 14 리스크 표 참조) 해결의 핵심 진입점.
- 카페는 "어디 시군이 좋아요?" 질문 글에 의존 — 답변 비균질·광고 혼재.
- Phase 1 출시 시점부터 즉시 가치 제공 가능. 지역 인증·후기 누적 전이라도 작동.

**구현 윤곽**:
- 라이프스타일 가중치 설정은 `RegionScoringWeight` 시드 테이블(시군 × 5축 점수) — Phase 1 초기엔 관리자 수기 입력, Phase 3에서 사용자 후기 기반 보정.
- 위저드 라우트 `/match/wizard` (HTMX 단계 전환) → 결과 `/match/result?...`.
- 결과 페이지에 시군 허브 링크 + "이 시군에 사는 거주자 N명 후기" 동시 노출 — 다음 행동 유도.
- 비로그인도 사용 가능, 결과 저장은 로그인 후.

**마일스톤**: **Phase 1 MVP 포함** — 콜드 스타트 해결이 핵심.

#### 1.5.4 Peer Validation · 거주자 상호 검증 (Pillar V) [v1.1 · C1]

**정의**: 같은 시군의 다른 실거주자가 후기·Journey 에피소드에 **"내용 정확함"·"이의 있음"** 을 표시할 수 있는 cross-validation 메커니즘. 광고성·허위 후기의 자정 작용을 만드는 신뢰 레이어.

**왜 차별점인가**:
- 단일 모더레이터(관리자 1인) 병목을 분산 — §12 리스크표의 "관리자 1인 병목"·"광고성 위장 후기" 두 항목 동시 완화.
- 카페·블로그는 같은 동네 거주자라도 댓글·반박 외엔 구조화된 검증 수단 없음. 통계 집계 불가.
- "양평 입주자 7명 중 6명이 정확하다고 표시" 같은 메트릭은 단일 평점보다 신뢰도 큼.

**구현 윤곽**:
- `post_validations(post_id, validator_user_id, vote ENUM('confirm','dispute'), note TEXT NULLABLE, created_at)` 테이블.
- 검증 권한: `validator_user_id`가 해당 시군의 `badge_level='resident'` 이고 `post.author_id` 와 다를 것. 동일 시군 거주자만 투표 가능.
- 후기 카드에 "거주자 N명 동의 / M명 이의" 배지 노출. 이의 ≥ 2건이면 관리자 큐(`/admin/reports`)에 자동 진입 (별도 reason='peer_dispute').
- 자기 후기에 대한 셀프 어뷰징 방지: 동일 시군 내 거주자가 ≥ 3명일 때만 메트릭 표시 (작은 시군은 익명성 보호).
- 어뷰징 방어: 한 사용자당 하루 dispute 상한 5회. 반복 dispute 후 미채택 시 가중치 감소.

**안티패턴 (의도적 제외)**:
- 좋아요·인기 투표가 아님 (이건 일반 사용자 `post_likes` 가 담당).
- 평점·별점 시스템이 아님 — Pillar C(Regret Cost) 가 정량 메트릭 담당.

**마일스톤**: **Phase 2** — 모더레이션 워크플로우와 함께 출시. Phase 1엔 데이터 모델만 준비 (`post_validations` 테이블).

#### 1.5.5 차별화 축 → 경쟁자 비교

| 축 | 네이버 카페 | 호갱노노 | 오늘의집 | 당근 | Nestory |
|---|---|---|---|---|---|
| Time-lag (T) | ✗ | ✗ | ✗ | ✗ | **✓ (Phase 3+)** |
| Regret Cost (C) | ✗ (서술뿐) | △ (실거래가만) | ✗ | ✗ | **✓ (Phase 2)** |
| Match Wizard (R) | ✗ | △ (지도 필터) | ✗ | ✗ | **✓ (Phase 1 MVP)** |
| **Peer Validation (V)** | △ (댓글뿐) | ✗ | ✗ | △ (매너온도) | **✓ (Phase 2)** |

네 축 중 **하나라도 모방하려면 데이터 모델·온보딩·운영을 모두 재설계**해야 함 → 구조적 해자.

---

## 2. 사용자 (Personas)

### 2.1 주요 페르소나

#### P1. 예비 은퇴자 (Prospect) — 주요 수요자 + **보조 공급자 [v1.1 · B1]**

- 연령: 50–65세
- 상태: 전원주택 이주를 검토 중이거나 준비 초기
- 니즈: "실패 사례를 먼저 알고 싶다", "시행착오 비용 줄이기", **"내 정착 계획을 공개하고 거주자 조언을 받고 싶다"**
- 기기: 모바일 우선, 카카오톡 상시, 네이버 검색 주력
- 앱 내 행동: 후기 탐색·스크랩, Journey 팔로우, Q&A 작성, 지역 허브 방문, **"내 정착 계획" 작성 (콜드 스타트 시 콘텐츠 보조 공급)**

#### P2. 실거주 은퇴자 (Resident) — 주요 공급자

- 연령: 55–70세
- 상태: 이미 전원주택 입주. 최근 1개월 ~ 5년차
- 니즈: "내 경험을 남기고 싶다", "이웃을 찾고 싶다", "업자·자재 정보 공유"
- 기기: 모바일 + 데스크톱 혼용
- 앱 내 행동: 후기·Journey 작성, Q&A 답변, 지역 허브 활동, 오프라인 정모 (v2+)

#### P3. 관리자 (Admin) — 내부 운영

- 역할: 배지 승인, 신고 처리, 콘텐츠 큐레이션, 공지
- 초기 인원: 1명 (미정, OI-5 참조)
- 도구: /admin 대시보드

#### P4. 전문가 / 시공사 (Phase 3+)

- 역할: 공식 프로필, 실수요자 응답, 리드 수신
- 인증: 사업자등록증 검증

### 2.2 배지 기반 권한 매트릭스

배지는 **저장 수준 3단계** (DB enum `badge_level`) + **표시 속성 1개** (N년차, 계산값) 구조입니다. "4단계 배지"라는 표현은 사용자 관점의 시각적 구분이며, 실제 권한 분기는 3단계 enum으로 결정됩니다.

| 배지 | 저장 방식 | 획득 방법 | 권한 |
|---|---|---|---|
| 🌱 관심자 | `badge_level = 'interested'` | 회원가입 (기본) | 읽기·댓글·Q&A 작성·스크랩·팔로우 |
| 📍 지역 인증 | `badge_level = 'region_verified'` | GPS 또는 주소 연동 성공 | 위 + 지역 필터 커뮤니티 작성 |
| 🏡 실거주자 | `badge_level = 'resident'` | 증빙 업로드 + 관리자 승인 | 위 + **입주 후기·Journey 작성** + 후기 상단 노출 |
| 🌳 N년차 | 계산값 (`resident_verified_at + N년`) | 실거주자 배지 획득 후 자동 | 실거주자와 동일. 프로필·후기 상단에 "3년차" 등 표시 |

---

## 3. 핵심 사용자 흐름

### 3.1 Flow A — 예비자의 의사결정 여정

```
홈 피드 → 시군 허브 진입 → 후기 필터(예산·평수) →
후기 상세 열람 → 스크랩 → 작성자의 Journey 팔로우 →
관심 있는 Q&A → 카카오 로그인 → 알림 수신
```

### 3.2 Flow B — 거주자의 콘텐츠 생성

```
카카오 로그인 → 프로필 설정 → 실거주자 배지 신청(증빙) →
관리자 승인 대기 → 배지 획득 → 후기 작성(템플릿 + 사진) →
Journey에 묶기 (선택) → 공개 → 댓글·질문 응답
```

### 3.3 Flow C — 관리자 모더레이션

```
관리자 대시보드 → 배지 신청 큐 → 증빙 확인 → 승인/반려 →
신고된 콘텐츠 검토 → 처리(숨김·경고·차단) → 공지 발행
```

---

## 4. 정보 구조 (IA) 및 페이지 맵

### 4.1 전역 네비게이션

모바일 하단 탭 5개:

| 아이콘 | 라벨 | 경로 |
|---|---|---|
| 🏠 | 홈 | `/` |
| 🗺️ | 탐색 | `/discover` |
| ➕ | 작성 (FAB, 로그인 필요) | `/write/*` |
| 🔔 | 알림 | `/notifications` |
| 👤 | 프로필 | `/me` |

데스크톱에서는 상단 헤더로 변환됨.

### 4.2 페이지 트리

```
/                                  홈 피드 (비로그인 OK)
├── /feed                          전체/팔로우 피드
├── /discover                      지역 허브 목록
│   └── /hub/{sigungu}            예) /hub/yangpyeong
│       ├── (허브 홈: 후기+Journey+Q&A+이웃 섹션)
│       ├── /hub/{sigungu}/reviews
│       ├── /hub/{sigungu}/journeys
│       └── /hub/{sigungu}/questions
│
├── /post/{id}                     개별 후기 상세
├── /journey/{id}                  Journey 상세 (연작)
│   └── /journey/{id}/ep/{n}
├── /question/{id}                 Q&A 스레드
│
├── /write/review      🔒🏡        후기 작성 (실거주자 배지 필요)
├── /write/journey     🔒🏡        Journey 생성/편집
├── /write/question    🔒          Q&A 작성 (로그인만)
├── /write/plan        🔒          [v1.1 · B1] 내 정착 계획 작성 (예비자, 로그인만)
│
├── /u/{username}                  공개 프로필
│   ├── /u/{username}/posts
│   ├── /u/{username}/journeys
│   └── /u/{username}/scraps
│
├── /me                🔒          내 대시보드
│   ├── /me/scraps
│   ├── /me/following
│   ├── /me/badge                  배지 상태·신청
│   └── /me/settings
│
├── /auth/login                    이메일·카카오 로그인
├── /auth/kakao/callback
├── /auth/signup
│
├── /admin             🛡           관리자 전용
│   ├── /admin/badge-queue
│   ├── /admin/reports
│   ├── /admin/content
│   ├── /admin/users
│   └── /admin/announcements
│
└── (Phase 3+ 예약)
    ├── /map
    ├── /directory/builders
    └── /directory/builder/{id}
```

### 4.3 인증·권한 매트릭스

| 레벨 | 대상 페이지 | 특징 |
|---|---|---|
| Public | `/`, `/feed`, `/discover`, `/hub/*`, `/post/*`, `/journey/*`, `/question/*`, `/u/*` | SEO·공유·검색 유입 대상. 로그인 유도 CTA. |
| 🔒 로그인 | `/me`, `/me/*`, `/notifications`, `/write/question`, `/write/plan` | 이메일 또는 카카오 로그인 후 접근. |
| 🏡 실거주자 배지 | `/write/review`, `/write/journey` | 관리자 승인된 배지 소유자만. 미획득 시 `/me/badge`로 유도. |
| 🛡 관리자 | `/admin/*` | `users.role = 'admin'`. 초기엔 ENV로 지정, v2에 세분화. |

**[v1.1 · C2] 권한 가드 표준 패턴**: 위 매트릭스는 코드에서 FastAPI Depends 의존성으로 강제한다. §6.2 디렉토리 구조의 `app/deps.py` 에 표준 가드 정의:

```python
# app/deps.py — 권한 가드 표준 패턴
def require_login(...) -> User: ...                      # 🔒
def require_badge(level: BadgeLevel) -> Callable: ...    # 🏡 등 — Depends 팩토리
def require_admin(...) -> User: ...                      # 🛡
def require_resident_in_region(region_id: int) -> ...    # Pillar V cross-validation 투표 권한
```

라우트 정의 시 위 가드 외 다른 인증 검사 금지 (코드 리뷰 체크리스트 항목). 미사용 시 PR 리뷰에서 차단.

### 4.4 시군 허브 페이지 구성

시군 허브는 Nestory의 중심 페이지. 섹션 구성:

1. 허브 헤더 — 지역명·등록 거주자 수·후기 수·Journey 수
2. 탭: **후기** / **Journey** / **Q&A** / **이웃**
3. 인기 후기 카드 리스트
4. 진행 중 Journey 카드
5. 실시간 Q&A 스레드
6. (Phase 3) 지역 시공사 섹션

### 4.5 홈 피드 전략

**비로그인** (획득 우선): 추천 허브 3–4개, 인기 후기, 진행 중 Journey, "카카오로 1초 시작" CTA.

**로그인** (개인화): 팔로우 Journey의 새 에피소드, 관심 지역 새 글, 팔로우 추천.

---

## 5. 데이터 모델

### 5.1 핵심 엔티티

#### users
```
id PK
email UNIQUE
password_hash NULLABLE     -- 카카오 전용이면 NULL
kakao_id UNIQUE NULLABLE
username UNIQUE            -- URL 슬러그용
display_name
bio, profile_image_id FK → images
role ENUM('user','admin')
badge_level ENUM('interested','region_verified','resident','ex_resident')  -- [v1.1 · B3]
primary_region_id FK → regions NULLABLE
resident_verified_at TIMESTAMPTZ NULLABLE
resident_revalidated_at TIMESTAMPTZ NULLABLE   -- [v1.1 · B3] 마지막 재검증 시점
ex_resident_at TIMESTAMPTZ NULLABLE            -- [v1.1 · B3] 이주/탈거 시점
last_login_at
created_at, updated_at, deleted_at (soft delete)
anonymized_at TIMESTAMPTZ NULLABLE              -- [v1.1 · C3] PIPA 탈퇴 후 익명화 처리 완료 시점
```

#### user_interest_regions [v1.1 · B5]
```
user_id FK → users
region_id FK → regions
priority INT             -- 1=top, 2, 3 (Match Wizard 결과 저장용)
created_at
PRIMARY KEY (user_id, region_id)
```
검토 중인 예비자가 양평·가평·춘천 등 여러 시군을 동시에 관심 등록 가능. Match Wizard 결과 자동 저장 + 알림 다중 시군 적용.

#### regions
```
id PK
sido, sigungu              -- 경기도, 양평군
slug UNIQUE                -- 'yangpyeong'
description, cover_image
is_pilot BOOL              -- 파일럿 시군 여부
created_at
```

#### posts (통합 콘텐츠 테이블)
```
id PK
author_id FK → users
region_id FK → regions
journey_id FK → journeys NULLABLE
parent_post_id FK → posts NULLABLE   -- 답변이 질문을 참조
type ENUM('review','journey_episode','question','answer','plan')  -- [v1.1 · B1]
episode_no INT NULLABLE              -- Journey 내 순서
title
body TEXT                            -- 마크다운
metadata JSONB                       -- 타입별 구조화 필드 (5.3) — Pydantic Discriminated Union 검증
status ENUM('draft','published','hidden')
view_count INT DEFAULT 0
published_at TIMESTAMPTZ NULLABLE
created_at, updated_at
deleted_at TIMESTAMPTZ NULLABLE       -- [v1.1 · C3] soft delete 일관성
```

> **[v1.1 · C3] Soft delete 일관성**: `users` 외에도 `posts`·`journeys`·`comments` 모두 `deleted_at` 컬럼을 가진다. 모든 조회 쿼리는 `deleted_at IS NULL` 필터를 강제하기 위해 SQLAlchemy의 `with_loader_criteria` 또는 베이스 쿼리 mixin을 통해 적용한다. raw SQL 금지 (§8.1 항목과 일치).

#### post_validations [v1.1 · C1]
```
id PK
post_id FK → posts
validator_user_id FK → users          -- 동일 시군 resident 만
vote ENUM('confirm','dispute')
note TEXT NULLABLE
created_at
UNIQUE (post_id, validator_user_id)   -- 동일 사용자 1회만
```
거주자 cross-validation (Pillar V) 데이터 저장. 권한 체크는 §6.2 `require_resident_in_region` 가드에서 수행.

#### journeys
```
id PK
author_id FK → users
region_id FK → regions
title, description, cover_image_id FK → images NULLABLE
start_date DATE                      -- 터잡기 시작일 등
status ENUM('in_progress','completed')
created_at, updated_at
```

#### badge_applications
```
id PK
user_id FK → users
requested_level ENUM('region_verified','resident')
region_id FK → regions
status ENUM('pending','approved','rejected')
reviewer_id FK → users NULLABLE
applied_at, reviewed_at
review_note TEXT
```

#### badge_evidence
```
id PK
application_id FK → badge_applications
evidence_type ENUM('utility_bill','contract','building_cert','geo_selfie')
file_path                            -- 비공개 디렉토리
uploaded_at
scheduled_delete_at                   -- 승인 30일 후 자동 삭제
```

#### images
```
id PK
owner_id FK → users
post_id FK → posts NULLABLE
file_path_orig, file_path_thumb, file_path_medium, file_path_webp
width, height, size_bytes
alt_text
order_idx INT                        -- 포스트 내 순서
status ENUM('processing','ready','failed')
uploaded_at
```

#### comments
```
id PK
post_id FK → posts
author_id FK → users
parent_id FK → comments NULLABLE     -- 스레디드
body TEXT
status ENUM('visible','hidden')
created_at, updated_at
deleted_at TIMESTAMPTZ NULLABLE       -- [v1.1 · C3] soft delete 일관성
```

#### tags, post_tags
```
tags(id, name UNIQUE, slug UNIQUE)
post_tags(post_id, tag_id)  -- M:N
```

#### 라이트 테이블 (상호작용)
```
post_likes(post_id, user_id, created_at)
post_scraps(post_id, user_id, created_at)
user_follows(follower_id, following_id, created_at)
journey_follows(journey_id, user_id, created_at)
```

#### notifications
```
id PK
user_id FK → users         -- 수신자
type ENUM(...)
source_user_id FK NULLABLE
target_type, target_id
is_read BOOL DEFAULT FALSE
created_at
```

#### reports
```
id PK
reporter_id FK → users
target_type, target_id
reason ENUM(...)
detail TEXT
status ENUM('pending','resolved','rejected')
handled_by FK → users NULLABLE
handled_at
created_at
```

#### audit_logs
```
id PK
actor_id FK → users
action ENUM(...)
target_type, target_id
note TEXT
created_at
```

#### announcements
```
id PK
author_id FK → users        -- admin
title, body
pinned BOOL DEFAULT FALSE
published_at
```

### 5.2 주요 인덱스

- `posts (region_id, published_at DESC)` — 허브 피드
- `posts (journey_id, episode_no)` — Journey 에피소드
- `posts (author_id, published_at DESC)` — 프로필
- `posts (type, status, published_at DESC)` — 전체 피드
- GIN `posts.metadata` — JSONB 필드 필터
- **GIN `posts (title || body) gin_trgm_ops`** — [v1.1 · A2] **Phase 1부터** `pg_trgm` 기반 부분일치·오타 허용 검색 (한국어 공백 분할 약점 보완)
- GIN `to_tsvector('simple', title || body)` — Phase 1: `simple` 컨피그 (공백 토크나이즈) + 위 trgm 보조. **Phase 2+: mecab-ko / korean unaccent** 도입하여 형태소 기반 정밀도 향상
- `notifications (user_id, is_read, created_at DESC)` — 알림 큐
- `badge_applications (status, applied_at)` — 관리자 큐
- `post_validations (post_id, vote)` — [v1.1 · C1] Pillar V 통계 집계
- `user_interest_regions (region_id, priority)` — [v1.1 · B5] 다중 관심 지역 알림

> **[v1.1 · A2] Phase 1 검색 전략**: PostgreSQL FTS의 한국어 처리는 기본 토크나이저(공백 분할)로는 거의 작동하지 않음 — "양평군"·"양평", "단열재"·"단열" 매칭 실패. mecab 형태소 분석은 RPi에서 빌드 부담 큼. 따라서 **Phase 1은 `pg_trgm` 부분일치 + `simple` FTS 병행** 으로 시작하고, **Phase 2에 mecab-ko 도입을 OI-13으로 결정**. 검색 라우트는 trgm 결과 ∪ FTS 결과를 합쳐 ranking.

### 5.3 Post.metadata JSONB 스키마 (type별)

#### 5.3.1 type=review / journey_episode

```json
{
  "house_type": "단독|타운하우스|듀플렉스",
  "size_pyeong": 32,
  "land_size_pyeong": 180,
  "budget_total_manwon": 32000,
  "budget_breakdown": {
    "land": 15000,
    "construction": 14000,
    "etc": 3000
  },
  "move_in_date": "2024-03",
  "construction_period_months": 9,
  "satisfaction_overall": 4,
  "regrets": ["단열", "부지 선정"],
  "highlights": ["마당", "자연광"],
  "builder_info": { "name": "**건축", "verified": false },
  "regret_items": [                     // Pillar C (Regret Cost Aggregator)
    {
      "category": "land|design|build|move|life|region",
      "cost_krw_band": "<100|100-500|500-2000|2000+",
      "time_months_band": "<1|1-3|3-6|6+",
      "free_text": "진입로 포장 비용 추가 발생"
    }
  ],
  "journey_ep_meta": {
    "phase": "터|건축|입주|1년차|3년차",
    "period_label": "2024 봄"
  },
  "review_year_offset": 1               // Pillar T — 1년차/3년차 비교용
}
```

#### 5.3.2 type=plan (예비자 정착 계획) [v1.1 · B1]

```json
{
  "interest_regions": [12, 27],         // region_id 리스트 (Top 3)
  "target_move_year": 2027,
  "household_size": 2,
  "budget_total_manwon_band": "10000-20000",
  "must_have": ["채소밭", "도서관 30분 내"],
  "nice_to_have": ["계곡 인접"],
  "concerns": ["겨울 난방비", "병원 거리"],
  "construction_intent": "self_build|buy_existing|rent_first|undecided",
  "open_to_advice": true                // 거주자 답글 받기 동의
}
```

#### 5.3.3 [v1.1 · A3] Pydantic Discriminated Union 검증 강제

`Post.metadata`는 **자유 JSONB가 아니다**. type별 Pydantic 모델로 타이트하게 검증한다:

```python
# app/schemas/post_metadata.py
class ReviewMetadata(BaseModel):
    model_config = ConfigDict(extra='forbid')   # 정의되지 않은 필드 거부
    house_type: Literal['단독', '타운하우스', '듀플렉스']
    size_pyeong: PositiveInt
    # ... (위 5.3.1 필드)

class PlanMetadata(BaseModel):
    model_config = ConfigDict(extra='forbid')
    # ... (위 5.3.2 필드)

PostMetadata = Annotated[
    Union[ReviewMetadata, JourneyEpisodeMetadata, QuestionMetadata, AnswerMetadata, PlanMetadata],
    Field(discriminator='__post_type__')   # Post.type 와 매칭
]
```

- 모든 쓰기 경로 (`POST /write/*`, HTMX 파샬, 어드민) 는 `PostMetadata` 검증 통과 후에만 DB 저장.
- `extra='forbid'` 로 클라이언트의 임의 필드 주입 차단 → Pillar C 통계가 깨지지 않음.
- 마이그레이션 시: 자주 조회되는 필드는 컬럼으로 승격 (예: `regret_total_cost_krw_band`). 점진 진행 — 컬럼 추가 → backfill → switch read → switch write → metadata 키 제거. 최종 템플릿 필드는 파일럿 거주자 인터뷰로 검증 (OI-11).

### 5.4 배지 상태 머신

```
가입 시 → badge_level='interested' 🌱
  │
  │ (GPS 또는 주소 인증)
  ▼
badge_level='region_verified' 📍
primary_region_id = X
  │
  │ BadgeApplication 생성 (requested_level='resident')
  │ → 증빙 업로드 → status='pending'
  │
  │ 관리자 검토
  ├─ rejected → interested 상태 유지 (재신청 가능)
  │
  ▼ approved
badge_level='resident' 🏡
resident_verified_at = now()
resident_revalidated_at = now()
→ 후기·Journey 작성 권한 부여
  │
  │ 시간 경과 (일배치 계산)
  ▼
🌳 N년차 표시 속성 (resident_verified_at + 365d / 3y / 5y)
🌳 3년차 회고 표시 속성 ([v1.1 · B4] 1→3년차 후기 쌍 완성 시)
```

#### 5.4.1 [v1.1 · B3] 재검증·이사·탈거 분기

**연 1회 재검증** (§12 리스크 표 "광고성 위장 후기" 항목 충족):
```
resident_verified_at + 365d 경과
  → maintenance worker 가 알림 발송 ("거주 상태 재확인 부탁드립니다")
  → 사용자 응답
    ├─ '계속 거주 중' (소극적 확인) → resident_revalidated_at = now()
    ├─ 14일 무응답 → '경고' 상태 (UI 배지 흐림 처리, 작성 권한 유지)
    └─ 60일 무응답 → resident → ex_resident 자동 전환
```

**이사 (region 이전)**:
```
사용자가 /me/badge 에서 "이사했습니다" 신청
  → 새 region 증빙 업로드 → 관리자 검토 → 승인
  → primary_region_id 갱신 / resident_verified_at 유지 / resident_revalidated_at = now()
  (기존 시군 후기는 익명 표시 변경 없이 유지 — 시계열 자산 보존)
```

**탈거 (전원주택 → 도시 복귀)**:
```
사용자 자발 신청 OR 60일 무응답 자동 전환
  → badge_level = 'ex_resident', ex_resident_at = now()
  → 작성 권한 박탈, 기존 콘텐츠 유지 (UI에 "이전 거주자" 표기)
  → Pillar V 검증 권한 박탈 (현재 거주자만 cross-validation 가능)
```

### 5.5 증빙 유형

| 타입 | 요구사항 | 신뢰도 |
|---|---|---|
| utility_bill | 전기·수도·가스 고지서 (본인명 + 주소, 금액 마스킹) | ⭐⭐⭐ |
| contract | 매매·건축 계약서 일부 (인감·금액 마스킹) | ⭐⭐⭐ |
| building_cert | 건축물대장 사본 | ⭐⭐⭐ |
| geo_selfie | 집 앞 셀카 + GPS EXIF | ⭐⭐ |

정확한 허용 조합은 OI-3에서 확정.

---

## 6. 기술 아키텍처

### 6.1 기술 스택

| 레이어 | 선택 | 비고 |
|---|---|---|
| 언어 | Python 3.12 | 단일 언어 풀스택 |
| 웹 프레임워크 | FastAPI | ASGI, Pydantic v2 |
| ASGI 서버 | Uvicorn (uvloop) | 워커 2 |
| 리버스 프록시 | Nginx | 정적 파일·미디어 캐싱 |
| DB | PostgreSQL 16 (arm64) | RPi 공식 지원 |
| ORM | SQLAlchemy 2.x + Alembic | 마이그레이션 |
| 템플릿 | Jinja2 | SSR |
| 프론트엔드 인터랙션 | HTMX + Alpine.js | 빌드 단계 없음 |
| 인증 | itsdangerous 서명 쿠키 + argon2-cffi | 카카오 OAuth 2.0 |
| 이미지 처리 | Pillow + pillow-heif | WebP 지원 |
| 백그라운드 태스크 | **PostgreSQL 기반 미니 큐 (`pgmq` 또는 LISTEN/NOTIFY + jobs 테이블)** [v1.1 · A1] | 영속성 보장. Redis 의존성 회피. v3+ 트래픽 증가 시 ARQ/Redis 검토 |
| 호스팅 | Raspberry Pi (OS Bookworm 64) | 프로토타입 |
| 외부 노출 | Cloudflare Tunnel (cloudflared) | DDoS·SSL 위임 |
| CSS | Tailwind CSS (CDN 시작 → Build 전환) | OI-4에서 최종 결정 |
| 관측성 | structlog + Sentry + UptimeRobot | 무료 티어 |
| 테스트 | pytest + FastAPI TestClient + Playwright | 단위·통합·E2E |
| 컨테이너 (선택) | Docker | 개발 환경 재현성용 |

### 6.2 디렉토리 구조

```
nestory/
├── app/
│   ├── main.py                   # FastAPI 엔트리
│   ├── config.py                 # pydantic-settings (ENV)
│   ├── deps.py                   # DI (세션·현재 사용자·배지 가드)
│   ├── db/
│   │   ├── base.py               # SQLAlchemy Base
│   │   ├── session.py            # engine, session
│   │   └── migrations/           # Alembic
│   ├── models/                   # ORM 모델 (user, post, journey, badge, ...)
│   ├── schemas/                  # Pydantic (form·JSON)
│   ├── repositories/             # DB 접근 (쿼리 함수)
│   ├── services/                 # 비즈니스 로직
│   │   ├── auth.py
│   │   ├── badges.py
│   │   ├── posts.py
│   │   ├── images.py             # Pillow 리사이즈·WebP·EXIF 제거
│   │   ├── storage.py            # 로컬 FS 추상화 (→ 후일 S3 스왑)
│   │   └── notifications.py
│   ├── routers/
│   │   ├── pages/                # Jinja2 전체 페이지
│   │   ├── htmx/                 # HTMX 파샬 (댓글·좋아요·무한스크롤)
│   │   ├── api/                  # JSON API (모바일 앱 v3+ 대비)
│   │   └── admin/
│   ├── templates/
│   │   ├── base.html
│   │   ├── layouts/
│   │   ├── pages/                # (home, hub, post, journey, me, admin)
│   │   ├── components/           # 카드·배지·네비
│   │   └── partials/             # HTMX 응답 조각
│   ├── static/
│   │   ├── css/
│   │   ├── js/                   # htmx.min.js, alpine.min.js, app.js
│   │   └── icons/
│   ├── workers/                  # [v1.1 · A1] PG 기반 작업 큐 (jobs 테이블 + LISTEN/NOTIFY)
│   │   ├── queue.py              # enqueue/dequeue/retry, advisory lock
│   │   ├── handlers/             # image_resize, notification_send, scheduled_revalidation
│   │   └── runner.py             # systemd 워커 프로세스 (별도 systemd unit)
│   └── tests/ (unit · integration · e2e)
├── alembic.ini
├── pyproject.toml                # uv 또는 poetry
├── .env.example
├── deploy/
│   ├── nginx.conf
│   ├── systemd/nestory.service
│   └── cloudflared.yml
└── scripts/
    ├── seed_regions.py           # 시군 초기 데이터
    ├── backup.sh
    └── restore.sh
```

### 6.3 시스템 다이어그램 (요청 흐름)

```
┌──────────┐  HTTPS  ┌──────────────────┐ Tunnel  ┌─────────────────────────────┐
│ Browser  │ ──────▶ │ Cloudflare Edge  │ ──────▶ │ Raspberry Pi                │
│ (모바일  │ ◀────── │ (DDoS·SSL·캐시)  │ ◀────── │ cloudflared 아웃바운드      │
│  / 데탑) │         └──────────────────┘         │                             │
└──────────┘                                      │ ┌─────────────────────────┐ │
                                                  │ │ Nginx (:80 내부)        │ │
                                                  │ │ · 정적 캐싱 · gzip      │ │
                                                  │ └──────┬──────────────────┘ │
                                                  │        │ reverse proxy      │
                                                  │        ▼                    │
                                                  │ ┌─────────────────────────┐ │
                                                  │ │ Uvicorn (:8000)         │ │
                                                  │ │  FastAPI app            │ │
                                                  │ │   Jinja2 SSR + HTMX     │ │
                                                  │ │   BackgroundTasks       │ │
                                                  │ └────┬──────────┬─────────┘ │
                                                  │      ▼          ▼           │
                                                  │ ┌─────────┐ ┌──────────┐    │
                                                  │ │Postgres │ │Local FS  │    │
                                                  │ │  :5432  │ │/var/     │    │
                                                  │ └────┬────┘ │ nestory/ │    │
                                                  │      │      └────┬─────┘    │
                                                  │      ▼           ▼          │
                                                  │ ┌────────────────────────┐  │
                                                  │ │백업: pg_dump · rsync   │  │
                                                  │ │ → 외장 USB + B2 무료   │  │
                                                  │ │ 일 1회 · 14일 보관     │  │
                                                  │ └────────────────────────┘  │
                                                  └─────────────────────────────┘
```

### 6.4 이미지 업로드 파이프라인

1. **검증** (동기): 크기 ≤ 10MB · MIME 화이트리스트 · magic bytes 확인 · 치수 ≤ 6000x6000
2. **EXIF 제거** (동기, 중요): GPS·개인정보 제거. HEIC는 JPEG로 변환 후.
3. **원본 저장** (동기): `/media/orig/YYYY/MM/{uuid}.jpg`
4. **images 레코드** 생성 (status='processing')
5. **BackgroundTasks**:
   - Pillow로 thumb(320px)·medium(960px) 생성
   - WebP 변환 (원본·medium)
   - images 레코드 업데이트 (status='ready', 경로 저장)

RPi 성능 주의: 동시 업로드 세마포어 2–3. 10MB 사진 1장 ~1.5–3초 (RPi 4B).

### 6.5 인증 흐름

**이메일/비밀번호**: argon2id 해싱 · 세션 쿠키 발급

**카카오 OAuth 2.0**:
```
1. /auth/kakao/start → 302 https://kauth.kakao.com/oauth/authorize
2. 사용자 동의 → callback?code=...&state=...
3. /auth/kakao/callback
   · state 검증 (CSRF)
   · code → access_token 교환
   · GET /v2/user/me → kakao_id, nickname, email (동의 시)
   · users upsert (kakao_id 기준)
   · 세션 쿠키 발급 (SessionMiddleware · SameSite=Lax · HTTPOnly · Secure)
4. → Redirect /
```

### 6.6 HTMX 파샬 패턴

```
[서버 렌더 페이지]
  /post/123 → 전체 HTML (base layout 포함)

[HTMX 파샬]
  POST /htmx/post/123/like → <button class="liked">♥ 42</button>
  POST /htmx/post/123/comment → <article class="comment">...</article>
  GET /htmx/post/123/comments?page=2 → <div>...더 많은 댓글...</div>
```

클라이언트 상태관리 라이브러리 없음. Alpine.js는 드롭다운·토글 등 소규모 UI에만.

### 6.7 [v1.1 · A1] 백그라운드 작업 큐 — PostgreSQL 기반

**왜 별도 큐?** FastAPI의 `BackgroundTasks` 는 인메모리 — 프로세스 재시작·크래시 시 작업 유실. 이미지 변환, 알림 발송, Pillar T 24개월 알림, resident 재검증 일배치 등 핵심 작업이 사라지면 **차별화 축이 데이터로 살아남지 못함**. 따라서 영속화된 큐를 Phase 1부터 도입한다.

**구조**:

```
┌──────────────────────┐  enqueue   ┌────────────────────────┐
│ FastAPI route /htmx  │ ─────────▶ │  jobs 테이블 (Postgres)│
│ /upload, /publish    │            │  + LISTEN/NOTIFY 채널   │
└──────────────────────┘            └────┬───────────────────┘
                                          │ NOTIFY
                                          ▼
                                  ┌────────────────────────┐
                                  │ workers/runner.py      │
                                  │  · advisory lock       │
                                  │  · 핸들러 디스패치     │
                                  │  · 실패 재시도 backoff │
                                  │  (별도 systemd unit:   │
                                  │   nestory-worker.service)
                                  └────────────────────────┘
```

**`jobs` 테이블**:
```
id PK
kind ENUM('image_resize','notification','revalidation_check','timelapse_remind','export')
payload JSONB
status ENUM('queued','running','succeeded','failed','dead')
attempts INT DEFAULT 0
max_attempts INT DEFAULT 5
run_after TIMESTAMPTZ DEFAULT now()    -- 지연/예약 작업
locked_at, locked_by               -- 워커 ID
last_error TEXT
created_at, completed_at
INDEX (status, run_after)
```

- 워커는 `SELECT ... FOR UPDATE SKIP LOCKED` 로 동시성 안전하게 작업 픽업.
- LISTEN/NOTIFY 로 즉시 깨우기 + 폴링 fallback (1초 간격, 빈 큐일 때).
- 실패 시 지수 백오프 (`run_after = now() + 2^attempts * 1min`), `max_attempts` 초과 시 `dead` 상태로 보관 (관리자 확인 후 수동 재시도).
- 핵심 작업: 이미지 리사이즈 (§6.4 Step 5), 카카오 알림톡 발송 (§9.4), Pillar T 24개월 알림 발송, resident 연 1회 재검증 알림, 백업 검증, audit_log 비동기 기록.

**deploy 추가**: `deploy/systemd/nestory-worker.service` (Uvicorn과 별도 프로세스). RPi 코어가 충분하므로 워커 1개로 시작, 부하 증가 시 N개로 확장.

---

## 7. 배포 및 운영

### 7.1 환경

| 환경 | 용도 | 인프라 |
|---|---|---|
| local | 개발 | macOS/Windows · Docker Compose (Postgres) · uvicorn --reload |
| staging (선택) | 검증 | RPi 또는 VPS 작은 인스턴스 |
| production | 실서비스 | Raspberry Pi 4B 4GB · 64-bit Bookworm |

### 7.2 외부 노출

**Cloudflare Tunnel (cloudflared)** 채택.
- 장점: 포트포워딩 불필요, DDoS·SSL 자동, 홈 IP 비공개, 무료
- 대체: DDNS + 공유기 포트포워딩 (비추천: IP 노출·보안 부담)
- 폴백: DDNS 경로 비활성 상태로 사전 설정 (CF 장애 대비)

### 7.3 백업

- **DB**: `pg_dump` 일 1회 → 외장 USB (`/mnt/backup/pg/YYYY-MM-DD.sql.gz`) + Backblaze B2 rsync
- **미디어**: rsync `--link-dest` 증분 → 외장 USB + B2
- **보관**: 14일 일간 + 6개월 주간
- **복원 리허설**: 월 1회 (Docker로 임시 DB 복원 + 주요 쿼리 확인). 미실행 시 경보.

### 7.4 systemd 유닛

- `nestory.service` — Uvicorn
- `nestory-worker.service` — [v1.1 · A1] PG 기반 작업 큐 워커 (별도 프로세스, 재시작 시 큐 유실 없음)
- `nestory-backup.timer` — 백업 일배치
- `nestory-maintenance.timer` — 증빙 파일 만료 삭제·N년차 승급 계산·resident 재검증 알림 (jobs 테이블에 enqueue)

---

## 8. 보안 및 개인정보

### 8.1 보안 체크리스트

| 영역 | 조치 |
|---|---|
| 비밀번호 | argon2id (passlib) |
| 세션 | itsdangerous 서명 쿠키 · SameSite=Lax · HTTPOnly · Secure |
| CSRF | form hidden token + HTMX hx-headers 검증 |
| 레이트 리밋 | slowapi — 로그인 5/min · 업로드 10/hour · 댓글 20/hour |
| 파일 업로드 | magic bytes · 크기 제한 · EXIF 제거 · 파일명 UUID |
| XSS | Jinja2 autoescape · 마크다운은 bleach 화이트리스트 |
| SQL 인젝션 | SQLAlchemy ORM 전용 · raw SQL 금지 |
| CSP | script-src self · img-src self data: |
| 증빙 파일 | 비공개 디렉토리 · 승인 30일 후 자동 삭제 |
| 주소 공개 | 시군 단위까지만 (상세 주소 DB 저장만, 공개 안 함) |
| 회원 탈퇴 | soft delete 7일 유예 후 영구 삭제 · 법정 보존 항목 익명화 유지 |

### 8.2 개인정보 수집 최소화 원칙

- 필수: 이메일 또는 카카오 ID, 표시명
- 선택: 프로필 이미지, 소개, 주요 시군 (배지용)
- 민감: 증빙 파일 → 승인 30일 후 자동 삭제, 비공개 저장소

### 8.3 [v1.1 · C3] 탈퇴 처리·콘텐츠 익명화 정책

회원 탈퇴 시 사용자 식별정보는 파기하지만, **공개된 후기·Journey·Q&A는 커뮤니티 자산** 으로 가치가 있다 (Pillar T·V의 시계열 자산). 따라서 콘텐츠는 **익명화 후 유지** 하는 것이 기본. 사용자가 명시적으로 "내 콘텐츠 전체 삭제"를 요청한 경우만 hard delete.

| 단계 | 처리 |
|---|---|
| **D+0 (탈퇴 신청)** | `users.deleted_at = now()`. 즉시 로그아웃·세션 만료. UI에서 작성자 표시는 "탈퇴한 사용자". 7일 유예 — 본인이 복구 가능 |
| **D+7 (확정)** | 식별정보 파기: `email`·`kakao_id`·`username`·`display_name`·`bio`·`profile_image_id` → NULL 또는 무작위 해시. `password_hash` 폐기. `anonymized_at = now()`. 증빙 파일 즉시 삭제. |
| **콘텐츠 기본** | `posts`·`journeys`·`comments` 의 `author_id` 는 유지 (FK 무결성), 표시는 "탈퇴한 사용자"로 렌더 |
| **콘텐츠 명시적 삭제 요청 시** | `posts.deleted_at` 일괄 설정 → 30일 후 hard delete (백업에서도 다음 사이클에 정리) |
| **법정 보존 항목** | 신고·수사 협조 기록 등 법령상 의무 보존 항목은 별도 테이블에 익명 ID로 보존 (PIPA 제21조) |

**조회 쿼리는 항상 `deleted_at IS NULL` 필터 강제** (§5.1 Soft delete 일관성 노트와 일치). 베이스 mixin 또는 SQLAlchemy `with_loader_criteria` 사용.

---

## 9. Phased 로드맵

### 9.1 전체 타임라인

| Phase | 기간 | 한 줄 요약 |
|---|---|---|
| **Phase 0** · Foundation | Week 1–3 (약 3주) | 인프라·로그인·기반 세팅 |
| **Phase 1** · Core MVP | Week 4–11 (약 8주) | 허브 + 입주 후기 + 배지 |
| **Phase 2** · Journey + 커뮤니티 | Week 12–19 (약 8주) | Journey·Q&A·팔로우·모더레이션 |
| **Phase 3** · 플랫폼 확장 | Week 20–27 (약 8주) | 지도·시공사·수익화 |

총 27주 (약 6.5개월). 각 Phase 끝은 독립적으로 출시 가능한 증분.

### 9.2 Phase 0 · Foundation (Week 1–3)

**인프라·기반**
- 프로젝트 스캐폴딩 (uv · pyproject)
- RPi 환경 구축 (Python 3.12 · PostgreSQL 16)
- Cloudflare Tunnel + Nginx + systemd
- Alembic 초기 마이그레이션
- Sentry + UptimeRobot 연동
- CI (GitHub Actions — lint · test · build)

**도메인 초기**
- User · Region 모델 + seed (수도권 5개 시군)
- 이메일/비밀번호 로그인
- Kakao OAuth 연동
- Admin 부트스트랩 (ENV 지정)
- Base layout · Jinja2 템플릿 · HTMX·Alpine 로드
- 테스트 인프라 (pytest · factory-boy · httpx)

**완료 기준**: 로컬에서 로그인 → 빈 홈 페이지 렌더. RPi에 배포되어 도메인 접속 가능. pg_dump 자동 실행.

### 9.3 Phase 1 · Core MVP (Week 4–11)

**포함 기능**
- 배지 3단계 (관심자·지역인증·실거주자). 신청·증빙·관리자 승인 큐
- Post CRUD (type=review, **type=plan [v1.1 · B1]**). 구조화 템플릿 · Pydantic Discriminated Union 검증 · 초안/발행
- 이미지 파이프라인 (EXIF 제거 · 3단 리사이즈 · WebP) — **PG 기반 작업 큐 [v1.1 · A1]**
- **Region Match Wizard `/match/wizard` (Pillar R · MVP)** — `user_interest_regions` 자동 저장 [v1.1 · B5]
- 시군 허브 페이지 `/hub/{slug}` (후기 목록·필터·정렬)
- 후기 상세 `/post/{id}` + 스크랩·좋아요·댓글
- 검색 — **`pg_trgm` + `simple` FTS 병행 [v1.1 · A2]** (지역·평수·예산 필터)
- 홈 피드 (비로그인/로그인 분기)
- 프로필 `/u/{username}` · `/me`
- 알림 (bell UI · 인앱)
- 관리자 v1 (배지 승인 · 콘텐츠 숨김 · 사용자 조회)
- 반응형 UI · **PWA manifest + 카카오 인앱 브라우저 호환성 검증 [v1.1 · B2]**
- **Analytics 트래킹 [v1.1 · C4]** — PostHog/Plausible self-host + 핵심 이벤트 카탈로그 (§14)
- **데이터 모델 준비**: `post_validations`·`user_interest_regions`·`jobs` 테이블 (사용은 Phase 2부터)

**성공 기준**: 파일럿 지역에서 실거주자 10명 · 후기 30건 · **type=plan 작성 20건 [v1.1 · B1]** · 주간 활성 사용자 100+ · TTFB p95 ≤ 600ms · 검색 결과 첫 페이지 LCP ≤ 2.5s.

### 9.4 Phase 2 · Journey + 커뮤니티 (Week 12–19)

**포함 기능**
- Journey CRUD · 에피소드 순서 · phase 라벨 · 타임라인 뷰
- Journey 팔로우 + 새 에피소드 알림
- N년차 배지 자동 계산 + **resident 연 1회 재검증 일배치 [v1.1 · B3]**
- Q&A (type=question/answer) · 허브 내 섹션 · 태그
- User follow · 개인화 피드 가중치
- **Pillar V 활성화 [v1.1 · C1]** — `post_validations` 투표 UI · 시군 허브 메트릭 · 이의 ≥ 2건 자동 큐잉
- **Pillar C 출시** — 후기 템플릿에 `regret_items` 입력 + 시군 허브 `/hub/{slug}/regret` 통계 (50건 누적 후 활성화)
- 신고 · 모더레이션 워크플로우
- 공지사항 (`/admin/announcements`)
- 관리자 v2 (KPI 대시보드 · 신고 처리 이력 · cross-validation 분쟁 큐)
- **알림 채널 [v1.1 · A4]**: 카카오 알림톡(비즈메시지) **우선 채널** + 이메일 보조 + 앱 내 배너. 50–65세 도달률 고려. 비용·심사 리스크는 OI-12에서 결정.
- 이주·탈거 처리 흐름 (`ex_resident` 전환) [v1.1 · B3]

**성공 기준**: Journey 5건 이상 진행 중 · 팔로우 100+ · 주간 재방문율 40% · Q&A 답변률 60%+ · cross-validation 투표 200건 누적 · 알림톡 도달률 ≥ 85%.

### 9.5 Phase 3 · 플랫폼 확장 (Week 20–27)

**포함 기능**
- Kakao Map 통합 (`/map` · 마커 · 클러스터)
- 고급 검색 (JSONB 필터 · 저장된 검색 · 알림)
- 시공사 디렉토리 (`/directory/builders` · 프로필 · 인증 배지 · 평점)
- 업체 온보딩 (사업자등록증 검증 · 프리미엄 리스팅)
- 리드 폼 ("상담 요청" · 이메일·알림 · 전환 추적)
- 수익화 훅 (스폰서드 허브 배너 · 프리미엄 슬롯 · 리드 수수료)
- 분석 확장 (코호트 · 리텐션 · 콘텐츠 성과)
- 확장 준비 (미디어 R2/S3 이관 옵션 · DB 읽기 복제본 옵션)

**성공 기준**: 시공사 10+ · 월 리드 30+ · 첫 유료 계약 1건 이상.

### 9.6 Phase별 리스크 게이트

| Phase | 게이트 질문 | 미달 시 대응 |
|---|---|---|
| 1 종료 (메트릭) | 파일럿 지역에서 콘텐츠 30건·사용자 100명 확보됐는가? | Phase 2 대신 콘텐츠 시딩 스프린트 (오프라인·파트너십) |
| 1 종료 (스키마) [v1.1 · C5] | `Post.metadata` Pydantic 스키마가 실제 사용 데이터로 안정화됐는가? `regret_items`·`builder_info`·이미지 컬럼 후보 정리됐는가? | 마이그레이션 회고 → 컬럼 승격/스키마 freeze 결정. Phase 2 진입 전 1주 스키마 보강 스프린트 |
| 2 종료 (메트릭) | Journey가 실제로 쓰이는가? 재방문율 상승? cross-validation 투표 200건 도달? | Journey UX 재설계 · Pillar V 인센티브 재검토 · Phase 3 지연 |
| 2 종료 (스키마) [v1.1 · C5] | `jobs`·`post_validations` 테이블 운영 데이터로 인덱스·파티셔닝 필요성 확인됐는가? | 인덱스 추가·아카이브 정책 · `audit_logs` 분리 검토 |
| 3 종료 | RPi가 현재 트래픽을 감당하는가? | CCU 50 넘으면 VPS 이관 (§12 런북) · 미디어 R2 분리 |
| 3 종료 (Pillar T) [v1.1 · B4] | 1년차 후기 작성자 중 3년차 재작성률 ≥ 25% 달성됐는가? | 인센티브 재설계 · 회고 배지 노출 강화 또는 차별화 축 우선순위 재조정 |

### 9.7 오프-로드맵

| 항목 | 재검토 시점 |
|---|---|
| 모바일 네이티브 앱 | DAU 300+ |
| 한 달 살기 체험 매칭 | 별도 서비스로 분리 검토 |
| 오프라인 정모 매칭 | Phase 2 팔로우 안정화 후 |
| VR·드론 투어 | 시공사 프로필 외부 링크로만 |
| AI 추천·자동 요약 | 콘텐츠 5,000건 이상 후 |

---

## 10. 비기능 요구사항 (NFR)

| 영역 | 요구사항 |
|---|---|
| 성능 | TTFB p95 ≤ 600ms (허브·홈) · LCP ≤ 2.5s (4G) · 20 CCU 목표 / 50 CCU 상한 |
| 가용성 | 월 99% (월 약 7h 다운타임 허용) · VPS 이관 후 99.5% |
| 백업·복구 | RPO 24h · RTO 4h · 월 1회 복원 리허설 의무 |
| 접근성 | WCAG 2.1 AA · 최소 폰트 16px · 버튼 44×44px · 대비 4.5:1 · **rem 기반 폰트 + 사용자 브라우저 폰트 크기 설정 존중** |
| 브라우저 | Chrome/Safari/Edge/Samsung Internet 최근 2버전 · 구형은 graceful degradation |
| **카톡 인앱 브라우저 [v1.1 · B2]** | **카카오톡 인앱 브라우저(WebKit/WebView 기반)에서 정상 작동 필수** — 시니어 진입 경로 1순위. CI에 카톡 인앱 시뮬레이션 (User-Agent + WebView 제약) 수동 체크리스트 추가. 외부 브라우저 강제 오픈 hint 노출 (`?from=kakao` 시) |
| **PWA [v1.1 · B2]** | `manifest.webmanifest` + 최소 service worker (오프라인 fallback 페이지 + 정적 자산 캐싱) · "홈 화면에 추가" 가능. iOS/Android 모두 검증. Phase 1 출시 |
| 반응형 | 모바일(375–414px) · 태블릿(768px) · 데스크톱(1280px) |
| SEO | SSR · OG 태그 · sitemap.xml · robots.txt · JSON-LD (Article·Review) |
| 언어 | 한국어 단일 (키-값 파일 · v3+ 다국어 대응 여지) |
| 관측성 | structlog · Sentry · UptimeRobot · /healthz · Phase 2+ Prometheus /metrics |
| **분석 [v1.1 · C4, OI-14 확정 2026-05-06]** | **PostHog Cloud free** (1M 이벤트/월 무료) — 익명 모드(쿠키 미사용)로 시니어 동의 부담 회피. 가입 깔때기·Pillar T 응답률·콘텐츠 발견 퍼널을 박스에서 분석 가능. 데이터 미국 저장 → §11 외부 위탁 처리방침에 PostHog Inc. 명시. 핵심 이벤트 카탈로그는 §14.5 |

---

## 11. 법적 · 컴플라이언스

| 항목 | 처리 |
|---|---|
| 개인정보보호법 (PIPA) | 처리방침 페이지 · 증빙 파일 30일 자동 삭제 · 탈퇴 7일 유예 후 식별정보 파기·콘텐츠 익명화 (상세 §8.3) |
| 정보통신망법 | 카카오 OAuth로 본인확인 간접 충족 · 마케팅 이메일 별도 동의 |
| 14세 미만 | 약관에 "만 14세 이상" 명시 · 가입 시 생년 확인 |
| 위치기반서비스 | v1 시군 단위는 해당 없음 · Phase 3 지도 도입 시 신고 검토 |
| 통신판매중개 (Phase 3+) | 런칭 전 사업자등록 + 통신판매업 신고 |
| 쿠키 | 필수만 사용 (분석은 PostHog 익명 모드로 쿠키리스 — 동의 배너 미필요). |
| **외부 위탁 처리 [v1.1, OI-14]** | 처리방침에 명시: 카카오(인증·알림톡)·Sentry(에러)·**PostHog Inc., 미국 (분석 트래킹)**·Cloudflare(DDoS·SSL)·Backblaze B2(백업). 각 위탁 항목·국외 이전 사실·항목 보관 기간을 처리방침 별표로 명시 (PIPA 제17·제28조의8). |
| 저작권 | 사용자 소유 + 서비스 운영용 비독점 라이선스 · 탈퇴 후 처리 명시 |

---

## 12. 주요 리스크 및 완화

| 리스크 | 영향 | 완화 |
|---|---|---|
| 콜드 스타트 | 🔴 치명적 | 파일럿 5개 시군 집중 · 관리자 10건 시드 · 네이버 카페 파트너십 · 오프라인 |
| 광고성·위장 후기 | 🔴 치명적 | 배지 엄격 승인 · 패턴 감지 · 신고 24h 처리 · 연 1회 재검증 |
| RPi 하드웨어 장애 | 🟠 높음 | 일일 백업 · 이중화 · 예비 SD · 복원 리허설 · VPS 이관 48h 런북 |
| 관리자 1인 병목 | 🟠 높음 | 배지 주 5건 이내 · 자동 반려 룰 · Phase 2 모더레이터 승격 |
| 주소·프라이버시 노출 | 🟠 높음 | 시군 단위 공개 · DB는 별도 · EXIF 제거 · 프로필 시군 비공개 옵션 |
| Cloudflare 터널 의존 | 🟡 중간 | 폴백 DDNS 경로 사전 설정 |
| 50 CCU 스케일 한계 | 🟡 중간 | VPS 이관 런북 · 미디어 R2 분리 · 읽기 복제본 |
| 법적 분쟁 (시공사) | 🟡 중간 | 신고 절차 명시 · 표현 가이드 · 반론권 보장 |
| 1인 개발 번아웃·스코프 크립 | 🟡 중간 | Phase 게이트 엄격 준수 · 오프-로드맵 방어 · 주간 범위 점검 |

---

## 13. 테스트 전략

| 유형 | 도구 | 적용 |
|---|---|---|
| Unit | pytest · factory-boy · freezegun | services · repositories · utils · 커버리지 70%+ |
| Integration | FastAPI TestClient + Docker Postgres | 페이지 · HTMX 파샬 · API · 인증 가드 |
| E2E (Phase 2+) | Playwright | 핵심 플로우: 가입→후기 작성, 배지 신청→승인, Q&A |
| 부하 | locust · k6 | Phase 1 말 허브 페이지 50 CCU · Phase 3 지도 API |
| 보안 | bandit · trivy · ZAP | CI SAST · 릴리스 전 수동 ZAP |
| 수동 QA | 실기기 체크리스트 | Galaxy 중저가 · iPhone · 데스크톱 · 시니어 접근성 워크스루 |

---

## 14. KPI · 성공 지표

### 성장
- 월간 활성 사용자 (MAU)
- 신규 가입 / 로그인 전환율
- 실거주자 배지 보유자 수
- 월 신규 후기 · Journey 에피소드 수

### 품질
- 후기 평균 길이 · 사진 수
- Q&A 답변률 · 첫 답변 소요시간
- 신고 처리 시간 p50/p95
- 배지 승인 소요시간 (목표: 48h 이내)

### 참여
- 주간 재방문율 (WAU/MAU)
- 스크랩 · 팔로우 · Journey 팔로우
- Journey 완독률

### 기술
- 페이지 TTFB p50/p95
- 이미지 처리 대기열 길이
- 에러율 (목표 < 0.5%)
- 업타임 (목표 99%)

### 수익 (Phase 3+)
- 시공사 온보딩 수
- 월 리드 수 · 유료 전환율

### 14.5 [v1.1 · C4] 이벤트 카탈로그 (분석 트래킹)

KPI를 측정 가능하게 만드는 명시적 이벤트 enum. **`app/services/analytics.py` 의 `EventName` enum 으로 강제** (자유 문자열 이벤트 금지 → 데이터 정합성 유지). **트래킹 도구는 PostHog Cloud free** (OI-14, 2026-05-06 확정) — 익명 모드 사용, `posthog-js` 또는 `posthog-python` SDK로 발송, `distinct_id` 는 사용자 ID의 SHA-256 해시로만 식별.

**가입·인증 깔때기**:
- `signup_started` (provider: email|kakao)
- `signup_completed`
- `login_succeeded` (provider)
- `region_match_wizard_started`
- `region_match_wizard_completed` (top_regions: [int])

**콘텐츠 발견**:
- `hub_viewed` (sigungu)
- `post_viewed` (post_id, post_type, region_id)
- `post_scrapped` / `post_unscrapped`
- `journey_followed` / `unfollowed`
- `search_executed` (query_len, result_count, has_filter)

**콘텐츠 생성**:
- `write_started` (post_type)
- `write_published` (post_type, has_images, body_length_band)
- `plan_published` (interest_region_count) — [B1]
- `regret_item_added` (category, cost_band) — Pillar C 데이터 누적 추적

**신뢰·검증**:
- `badge_application_submitted` (requested_level, evidence_types)
- `badge_application_approved` / `rejected` (latency_hours)
- `peer_validation_voted` (vote: confirm|dispute) — Pillar V
- `revalidation_responded` (response_days_after_prompt) — [B3]

**Pillar T (시계열 회고)**:
- `timelapse_review_prompt_sent` (channel: alimtalk|email|inapp)
- `timelapse_review_completed` (year_offset, days_after_prompt)
- `timelapse_view_opened` (parent_review_id)

**알림·도달**:
- `notification_sent` (channel, kind)
- `notification_opened` (channel, kind)
- `notification_failed` (channel, error_type)

**모더레이션**:
- `report_submitted` (target_type, reason)
- `report_resolved` (resolution, latency_hours)

이벤트 페이로드는 PII 미포함 원칙 — `user_id`는 익명 해시로만, IP·이메일·실주소 절대 포함 금지. 코드 리뷰 체크리스트 항목.

---

## 15. 오픈 아이템 (미결정)

| 번호 | 결정 필요 | 결정 시점 |
|---|---|---|
| OI-1 | 파일럿 5개 시군 정확 선정 (예: 양평·가평·남양주·춘천·홍천) | Phase 0 |
| OI-2 | 지역 연고 · 초기 콘텐츠 시딩 전략 | Phase 0 |
| OI-3 | 실거주자 증빙 허용 유형 최종 조합 | Phase 1 초 |
| OI-4 | CSS 프레임워크 (Tailwind CDN · Build · 순수 · DaisyUI) | Phase 0 |
| OI-5 | 첫 관리자 (본인 · 별도 모집 · 지인) | Phase 0 |
| OI-6 | 네이버 카페 등 기존 커뮤니티 관계 | Phase 1 |
| OI-7 | 예산 (도메인 · Sentry 유료 · Kakao 비즈 · 백업 스토리지) | Phase 0 |
| OI-8 | 팀 구성 (1인 · 2–3인 · 외주 일부) | Phase 0 |
| OI-9 | 브랜드 · 로고 · 톤앤매너 · 컬러 팔레트 | Phase 0 |
| OI-10 | 도메인 · SNS 계정 등록 (nestory.kr? 동명 체크) | Phase 0 |
| OI-11 | Post metadata 템플릿 필드 최종 (파일럿 거주자 인터뷰) | Phase 1 초 |
| **OI-12 [v1.1]** | **카카오 알림톡 도입 결정** — 비즈메시지 채널 등록·심사 기간·템플릿 등록·발신 비용 (건당 ~9–15원). 미도입 시 이메일+앱 내 배너로 대체 (Pillar T 응답률 영향 큼) | Phase 1 말 (Phase 2 출시 전) |
| **OI-13 [v1.1]** | **한국어 검색 엔진 업그레이드 시점** — Phase 1은 `pg_trgm` + `simple` FTS 병행. Phase 2에 mecab-ko (Postgres extension) 도입 여부. RPi 빌드 부담 vs 검색 정밀도. | Phase 1 말 |
| **OI-14 [v1.1]** ✅ **결정 2026-05-06** | **PostHog Cloud free 채택** (1M 이벤트/월 무료, 익명 모드 쿠키리스). 미국 데이터 저장은 §11 외부 위탁 처리방침에 PostHog Inc. 명시로 해결. Plausible self-host·Umami는 §14.5의 가입 깔때기·Pillar T 응답률 퍼널 분석 부족으로 제외. | ~~Phase 0 말~~ → **확정** |
| **OI-15 [v1.1]** | **PWA 정도** — manifest+오프라인 fallback 만 (Phase 1) vs 푸시 알림 포함 (Phase 2 — iOS 16.4+ Web Push 가능, 시니어 권한 동의율 미지) | Phase 1 |
| **OI-16 [v1.1]** | **Cross-validation (Pillar V) 어뷰징 방어 정책** — 동일 시군 거주자 ≥ N 명일 때만 메트릭 노출 (현재 N=3 잠정). 작은 시군 익명성 vs 데이터 가시성 트레이드오프 | Phase 2 초 |

---

## 부록 A · 레퍼런스 리서치 요약

브레인스토밍 중 분석한 10+ 레퍼런스. 자세한 분석은 브레인스토밍 전사 참조.

### A.1 국내 참조

- **호갱노노** — 지도 기반 아파트 후기·데이터 플랫폼. 벤치마크: 데이터 + 후기 결합, 환경 데이터 시각화. 회피: 투자·시세 프레임.
- **직방** — 매물 중개 + VR 홈투어. 벤치마크: VR 투어, 중개사 인증 배지. 회피: 거래 중심 프레임(커뮤니티 약함).
- **네이버 카페 (전원생활·전원주택 라이프)** — 레거시 커뮤니티. 벤치마크: 카테고리 구조, "집짓기 일지" 연재 포맷. 회피: 광고성 글·진입장벽.
- **오늘의집** — 홈 인테리어 UGC 슈퍼앱. **가장 중요한 벤치마크**: 집들이 포맷·사진 태그·스크랩·팔로우 루프. 회피: 커머스 과몰입.
- **당근** — 하이퍼로컬 커뮤니티. 벤치마크: 동네 인증, 매너온도, 비즈프로필. 회피: 도시 밀집 전제.

### A.2 해외 참조

- **Nextdoor** — 미국 동네 SNS. 벤치마크: 주소 인증 온보딩, Recommendations 탭. 회피: 부정적 민원 게시물 → 모더레이션 정책.
- **Zillow/Redfin** — 부동산 플랫폼. 벤치마크: "What Locals Say" · 데이터 투명성. 회피: AVM은 한국 전원주택에 부적합.
- **The Villages · 55places** — 미국 은퇴자 커뮤니티. 벤치마크: 은퇴자 UX · 라이프스타일 카테고리 · 동호회. 회피: 게이티드 전제(한국 정서 다름).

### A.3 추가 참조

- **미스터멘션/리브애니웨어** — 한 달 살기. 체험 입주 아이디어 (v3+ 검토).
- **Reddit r/homestead** — 실패담 공유 문화. AMA 시리즈 포맷 벤치마크.
- **삼쩜삼·뱅크샐러드** — 시니어 친화 UX (큰 폰트 · 단계별 위저드 · 대화식 입력).

### A.4 핵심 결론

- **시장 공백**: "전원주택 정착 전 과정(Pre-move → Move-in → Post-move)을 구조화된 후기로 아카이빙하는 모바일 커뮤니티"
- **Must-have Top 3**: 구조화된 입주 후기 템플릿 · 지역 기반 실거주 인증 · 타임라인형 정착 일지
- **안티패턴 Top 2**: 커머스·거래 중개 과몰입 · 투자·시세 프레임

---

## 부록 B · 용어집

- **Nest + Story**: 제품명 (둥지 + 이야기)
- **Prospect**: 예비 은퇴자 (검토자) — v1.1부터 `type=plan` 으로 보조 콘텐츠 공급도 가능
- **Resident**: 실거주 은퇴자 (콘텐츠 공급자)
- **Ex-resident** [v1.1]: 이주·탈거로 더이상 거주하지 않는 이전 거주자. 작성 권한 박탈, 기존 콘텐츠는 유지
- **Journey**: 터잡기→건축→입주→N년차로 이어지는 여정형 연작 콘텐츠 컨테이너
- **Post**: 모든 콘텐츠 단위 (type 필드로 review/episode/question/answer/**plan** 구분)
- **Plan** [v1.1]: 예비자가 작성하는 정착 계획 (관심 시군·예산·우려·필수 조건)
- **Hub**: 시군 단위 지역 허브 페이지 (`/hub/{slug}`)
- **Badge**: 신뢰 인증 시스템 (관심자 🌱 / 지역인증 📍 / 실거주자 🏡 / N년차 🌳 / 3년차 회고 🌳 [v1.1])
- **Evidence**: 배지 신청 증빙 파일 (승인 30일 후 자동 삭제)
- **Pillar T/C/R/V** [v1.1]: 차별화 4축 — Time-lag review, Regret Cost, Region match wizard, **Peer Validation** (cross-validation)
- **Cross-validation / Peer Validation** [v1.1]: 같은 시군 거주자가 후기에 "정확함/이의" 표시하는 자정 메커니즘
- **`jobs` 큐** [v1.1]: PostgreSQL 기반 영속화 작업 큐 (이미지 변환·알림 발송·재검증 등)
- **OI**: Open Item — 브레인스토밍 중 미결정 사항

---

**끝**
