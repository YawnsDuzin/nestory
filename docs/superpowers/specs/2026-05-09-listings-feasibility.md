# 매물(전원주택·토지·경매) 노출 타당성 검토

| Status | Draft v0.1 — 채택 검토용 |
|---|---|
| Author | Nestory dev (yawnsduzin) |
| Created | 2026-05-09 |
| 관련 PRD | `docs/superpowers/specs/2026-04-17-nestory-design.md` (v1.1.1) |
| 관련 메모 | `_docs/prompts/20260508_prompt.md` (사용자 아이디어 큐) |
| 결정 필요 | OI-17 ~ OI-20 신규 등록 (본 문서 §4) |

> **요약(TL;DR)**: 네이버 부동산·경매 매물을 Nestory에 노출하는 모든 "데이터 수집·재배포" 패턴은 야놀자 민사·잡코리아 판례에 비추어 **법적 위험 큼**. 사용자가 제시한 **"링크 리다이렉트 + 사용자 브라우저 직접 접근"** 패턴이 합법 영역 내 유일한 안전 경로. 단, **이는 PRD §1.3 비교표·부록 A.1·A.4의 "거래 중개 회피" 포지셔닝과 충돌하므로 도입은 OI-17 결정 후로 보류**. 한편 **공공 API 5종(국토부 실거래가 4개 + R-ONE 1개) + V월드는 즉시 합법 사용 가능**하며, 시군 허브의 "지역 정보 컨텍스트" 강화에 활용 가능 — 매물 노출 없이도 정착 의사결정 지원 가치 제공.

---

## §0 배경 및 PRD 정합성 분석

### 0.1 사용자 의도 인용

`_docs/prompts/20260508_prompt.md` 라인 151:

> "네이버 부동산과 경매 정보의 전원주택이나 토지매물을 보여주고 싶어. 합법적으로 데이터를 수집이나 보여주는 방법과 현재의 프로젝트 구조에서 어떤 구조와 방식으로 보여주는게 효율적일지 검토해서 제안해줘."

후속 답변에서 좁힌 구체 방향:

- **A. 링크 기반 서비스** — 검색만 제공, 상세는 네이버로 이동
- **B. 사용자 브라우저 직접 접근** — 서버에 DB 저장 없이 UI만 제공

→ 본 문서는 이 두 방향의 합법성·기술적 실현성·PRD 적합성을 검증한다.

### 0.2 PRD 포지셔닝 충돌 (가장 중요)

PRD는 매물 거래·중개 기능을 **명시적 회피 대상**으로 기재:

- `2026-04-17-nestory-design.md:65-69` — §1.3 경쟁 비교표:
  > "직방 · Zillow | 거래 중개 | Nestory는 **커뮤니티 · 콘텐츠 아카이브**"
  > "호갱노노 | 도시 아파트 · 투자 | Nestory는 **전원주택 · 정착·삶의 질**"
- `2026-04-17-nestory-design.md:1270-1271` — 부록 A.1:
  > "호갱노노 — 회피: 투자·시세 프레임."
  > "직방 — 회피: 거래 중심 프레임(커뮤니티 약함)."
- `2026-04-17-nestory-design.md:1292` — 부록 A.4:
  > "**안티패턴 Top 2**: 커머스·거래 중개 과몰입 · 투자·시세 프레임"

→ 매물 노출은 사용자가 의도한 "링크 리다이렉트" 형태라도, "거래 중개 메타포" 진입은 위 안티패턴과 직접 충돌. **신규 OI-17로 등록하여 사업적 의사결정 받기 전엔 도입 금지** 권장.

### 0.3 Pillar 매핑 — 정직한 평가

| Pillar | 매물 기능과의 연관성 | 정직한 매핑 |
|---|---|---|
| T (Time-lag) | 무관 | ✗ |
| C (Regret Cost) | 무관 | ✗ |
| **R (Region Match)** | 약함 | △ — Region Match는 라이프스타일 5문항·관리자 수기 가중치 시스템(`2026-04-17-nestory-design.md:140-141`)이지 매물 데이터 기반이 아님. **매물로 R을 강화한다는 직접 매핑은 PRD와 부정합**. |
| V (Peer Validation) | 무관 | ✗ |

**대안 매핑** — "공공 API 통계 컨텍스트"는 Pillar R의 **결과 페이지 부속**(`/match/result`) 또는 시군 허브의 콘텐츠 컨텍스트 보강으로 가치 있음. "매물 매핑"이 아니라 "지역 사실 데이터 보강"으로 정직하게 표현.

### 0.4 의도된 산출

본 문서 단독으로 채택 여부 판단 가능. 채택 시 별도 plan(`docs/superpowers/plans/`) 작성 → subagent-driven-development로 실행.

---

## §1 합법성 비교표 (sources × access patterns)

### 1.1 매트릭스

| 소스 \ 패턴 | iframe 임베드 | 검색 폼 → 외부 딥링크 | 서버 캐싱·저장 | 사용자 브라우저 직접 fetch |
|---|---|---|---|---|
| **네이버 부동산** (new.land.naver.com) | ⚠️ X-Frame-Options 일반적 차단(직접 검증 차단으로 미실증) | ✅ **합법** — 사용자 능동 이동, 약관 §10 대상 외 | ❌ **위험** — 야놀자·잡코리아 판례 | ⚠️ CORS·약관 §10 회색지대 |
| **법원경매** (courtauction.go.kr) | 미확인 (직접 검증 차단) | ✅ **합법** — 사용자 능동 이동 | ⚠️ 정부 공식 OpenAPI **확인되지 않음** (인터넷 등기소 별도) | ⚠️ 자동화 회색지대 |
| **민간 경매** (옥션원·지지옥션 등) | ❌ 약관 위반 일반 | ⚠️ 검색결과 페이지 링크는 가능, 약관 확인 필요 | ⚠️ 무단 사용 ❌, B2B 제휴는 ✅ | ❌ 약관 위반 |
| **공공 API**: 국토부 실거래가, V월드, R-ONE | N/A (HTTP API) | N/A | ✅ **합법** — 공공누리 출처 표기 | ⚠️ 인증키 노출 위험 — 서버 프록시 권장 |

### 1.2 근거 (확인된 사실만)

#### A. 잡코리아 vs 사람인 (데이터베이스권 침해)

- **사건번호**: 서울고법 2016나2019365 항소심 → 대법원 심리불속행 기각으로 잡코리아 승소 확정. ([법률신문 98844](https://www.lawtimes.co.kr/news/98844), [ZDNet Korea 2017-09-27](https://zdnet.co.kr/view/?no=20170927180839))
- **결과**: 항소심에서 데이터베이스 제작자권 침해 인정 → 손해배상 2.5억 원 + 조정조서 위반 간접강제금 2억 원 = **총 4.5억 원 배상**.
- **시사**: 경쟁사 웹사이트의 채용 DB 무단 크롤링 → 공개 데이터라도 데이터베이스제작자의 권리(저작권법 §93) 침해.

#### B. 야놀자 vs 여기어때

**형사 (대법원 2022.5.12. 2021도1533)**: **무죄 확정**.
- 정보통신망법 §48(1) 침입 부정. 서버에 명시적 접근차단 조치 없었고 일반 이용자도 앱 가입 없이 접근 가능했던 점 근거. ([법률신문 178683](https://www.lawtimes.co.kr/news/articleView.html?idxno=178683), [casenote.kr 2021도1533](https://casenote.kr/대법원/2021도1533))

**민사 (서울고법 민사4부, 2021.8.)**: **여기어때 패소, 10억 원 배상**.
- 부정경쟁방지법 §2(1)카목 **성과도용** 인정. ([한경 2021-08-23](https://www.hankyung.com/it/article/202108230529Y), [뉴스1](https://www.news1.kr/society/court-prosecution/4410402))

**시사**: 형사 무죄에도 **민사 손해배상 10억 — 자동 데이터 수집·재배포는 비록 정보통신망 침입이 부정되더라도 부정경쟁행위로 인정될 수 있음**. 규모가 큰 대규모·반복적 무단 수집은 위험.

#### C. 공공 API (✅ 활용 가능)

- **국토교통부 부동산 실거래가 자료** (공공데이터포털, 인증키 발급 필수, 공공누리):
  - [15126469 아파트 매매](https://www.data.go.kr/data/15126469/openapi.do)
  - [15126465 단독/다가구 매매](https://www.data.go.kr/data/15126465/openapi.do) — **단독/다가구는 지번 일부만 제공 (정부 측 PII 마스킹)**
  - [15126466 토지 매매](https://www.data.go.kr/data/15126466/openapi.do) — **전원주택 부지 관련성 가장 큼**
  - [15126463 상업업무용 매매](https://www.data.go.kr/data/15126463/openapi.do)
  - 갱신 주기: 부동산 거래신고 후 익월 공개 (월 단위).
- **한국부동산원 부동산통계 R-ONE** ([data.go.kr 15134761](https://www.data.go.kr/data/15134761/openapi.do), [R-ONE OpenAPI 소개](https://www.reb.or.kr/r-one/portal/openapi/openApiIntroPage.do)):
  - 매매·전세지수, 지가변동률, 거래현황 등 **통계** (개별 매물 아님).
- **V월드** ([vworld.kr/dev](https://www.vworld.kr/dev/v4dv_search2_s001.do)):
  - 회원가입 + API 키 발급. 토지·필지·주소·행정구역 검색. 공공누리 명시.
- **법원경매 공식 OpenAPI**: 부동산경매 매물 단위 OpenAPI는 **공공데이터포털·courtauction.go.kr 양쪽에서 확인되지 않음** (등기 OpenAPI는 별도). → 공공 채널만으로는 경매 매물 노출 불가.

---

## §2 권장 전략 + 대안

### 2.1 권장 (Tier 1) — "공공 API 통계 컨텍스트" 단독, 매물 보류

> 매물 기능은 OI-17 결정 전까지 **보류**. 합법·PRD 정합·즉시 가치를 모두 만족하는 경로만 선택.

**구성**:
- 시군 허브(`/hub/{slug}`) 또는 Region Match 결과(`/match/result`)에 "지역 사실 데이터" 위젯 추가:
  - 최근 12개월 토지 매매 실거래가 평균·중위값 (출처: 국토부 실거래가, 공공누리 표기)
  - 시군 매매가격지수 추이 (출처: R-ONE)
  - 토지 용도지역 분포 (출처: V월드, 시군 단위 집계)
- **외부 매물·경매 노출 0건**.
- 공공 API 데이터는 서버 캐시(스냅샷 테이블)에 저장. 일배치 갱신.

**T·C·R·V 매핑** (정직):

| 축 | 매핑 | 강도 |
|---|---|---|
| R (Region Match) | 결과 페이지 컨텍스트 보강 (라이프스타일 매칭과 별개의 사실 기반 정보) | ⚪ 약 |
| C (Regret Cost) | 시군 매매가 분포 = 후회비용 통계와 시너지(예산 결정 컨텍스트) | ⚪ 약 |
| T·V | 무관 | ✗ |

**MVP**: Phase 2 (Pillar V·C와 같은 시점). Phase 1 머지 완료(dev → main) 후 진입.

**비용**:
- 공공 API 4종 무료 (인증키만). V월드 기본 무료(트래픽 한도 별도).
- 운영 부담: 인증키 환경변수 4-5개, 일배치 워커, 캐시 테이블 1개.

**위험·회피**:
| 위험 | 회피 |
|---|---|
| 인증키 만료·로테이션 | 환경변수 분리 + 401 응답 시 알림 워커 (OI-20) |
| 일일 호출 한도 초과 | 시군 단위 batch + ETag/last-modified 캐시 |
| 공공누리 표기 누락 → 라이선스 위반 | 모든 통계 위젯 하단에 "출처: ○○ (공공누리 1유형)" 의무화 |
| 단독/다가구 PII 마스킹 데이터를 추가 식별 시도 | 절대 금지 — code review 체크리스트 |

### 2.2 대안 (Tier 2) — "외부 검색 폼 + 딥링크 리다이렉트" — 사용자 의도 직답

> 사용자가 명시한 "링크/브라우저 직접 접근" 방식 그대로. 단, **PRD §1.3·부록 A 회피 정책 충돌 명시**. 채택은 OI-17 결정 후.

**구성**:
- Nestory 내 검색 폼: (시군 선택, 매물 유형, 가격대 밴드)
- 결과는 외부 사이트 검색 URL 카드 리스트:
  - 네이버 부동산 검색 URL (예시 — 비공식, §3에서 OI-18로 추적)
  - 법원경매 검색 URL (`courtauction.go.kr/pgj/...`)
- 카드 클릭 시 **외부 사이트로 이동 모달** ("Nestory를 떠나 ○○로 이동합니다" 명시) — 사용자 능동 이동 보장
- 서버 DB 저장 0건, fetch 0건.

**T·C·R·V 매핑**: 직접 매핑 없음. "도구적 편의" 수준.

**MVP**: Phase 4 후보. PRD 신규 절(§9.6 등) 신설 필요.

**비용**: 외부 의존성 비용 0. 운영 부담 작음. 단, 외부 URL 패턴 변경 시 빌더 코드 수정 필요.

**위험·회피**:
| 위험 | 회피 |
|---|---|
| 네이버 부동산 URL 파라미터 변경 | URL 빌더는 단일 service 함수에 격리 (`app/services/listings_redirect.py`). 회귀 모니터 (OI-18) |
| 사용자가 외부 사이트 콘텐츠 전제로 신뢰 → 약관 미동의 클레임 | 모달에 "외부 사이트 약관 별도 적용" 고지 |
| **PRD 포지셔닝 충돌** | OI-17로 사업·마케팅 톤 결정 후 도입 |

### 2.3 권장 외 (이유 명시)

- **회원 직접 등록형 매물** — 외부 데이터 의존 0이지만 콜드 스타트 위험 큼, 거주자 배지 보유 회원 수 부족, 매물 검증 모더레이션 부담 추가. Phase 4+ 검토 가능하나 **현재 팀 규모(1인)로 운영 부담 큼** → 권장 외.
- **네이버 부동산·경매 자동 수집·재배포** — ❌ 잡코리아·야놀자 민사 판례에 비추어 **법적 위험 명백**. 어떠한 형태든 권장 안 함.

---

## §3 통합 설계 (Tier 1 권장안 기준)

> Tier 2는 OI-17 결정 후 별도 spec. 본 §3은 권장안인 **공공 API 통계 컨텍스트**만 다룸.

### 3.1 데이터 모델

**매물 테이블 없음**. 통계 스냅샷 캐시 테이블 1개.

#### 3.1.1 신규 enum (`app/models/_enums.py`에 추가)

```python
class RegionStatSource(str, enum.Enum):
    MOLIT_LAND = "molit_land"               # 국토부 토지 실거래가 (15126466)
    MOLIT_HOUSE = "molit_house"             # 국토부 단독/다가구 실거래가 (15126465)
    REB_PRICE_INDEX = "reb_price_index"     # R-ONE 매매가격지수 (15134761)
    VWORLD_LAND_USE = "vworld_land_use"     # V월드 토지 용도지역
```

기존 `JobKind` enum에 추가:
```python
class JobKind(str, enum.Enum):
    # ... 기존
    REGION_STAT_SYNC = "region_stat_sync"   # 신규
```

#### 3.1.2 신규 모델 `app/models/region_stat_snapshot.py`

`app/models/post.py:26-78` 패턴 그대로 복제:

```python
class RegionStatSnapshot(Base):
    __tablename__ = "region_stat_snapshots"
    __table_args__ = (
        UniqueConstraint("region_id", "source", "metric_key", "period",
                         name="uq_region_stat_snapshots_period"),
        Index("ix_region_stat_snapshots_region_source", "region_id", "source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="CASCADE")
    )
    source: Mapped[RegionStatSource] = mapped_column(
        Enum(RegionStatSource, name="region_stat_source",
             values_callable=lambda x: [e.value for e in x])
    )
    metric_key: Mapped[str] = mapped_column(String(64))    # 예: "land_avg_krw_per_pyeong"
    period: Mapped[str] = mapped_column(String(16))         # "2026-04" 또는 "2026"
    value: Mapped[dict[str, Any]] = mapped_column(JSONB)    # 통계 객체 (avg/median/count 등)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # soft delete 불필요 (스냅샷은 영구 보존, 갱신 시 새 row)
```

**FK·인덱스 결정 근거**:
- `region_id` ondelete=CASCADE: 시군 삭제(거의 없음)는 모든 스냅샷 동시 정리.
- `(region_id, source, metric_key, period)` UNIQUE: 동일 기간 중복 방지.
- soft delete 없음: 시계열 분석을 위한 영구 보존. CLAUDE.md "모델·마이그레이션 패턴" 예외 — 본 spec에 사유 명시.

마이그레이션 autogenerate 후 enum DROP 수동 추가 검증 (CLAUDE.md "Alembic autogenerate 후 즉시 검증" 항목).

### 3.2 워커 / 동기화

#### 3.2.1 신규 핸들러 `app/workers/handlers/region_stat_sync.py`

`app/workers/handlers/image_resize.py:36-74` 데코레이터·SessionLocal 패턴 복제:

```python
"""region_stat_sync — 공공 API에서 시군별 통계 fetch 후 스냅샷 upsert."""
import structlog
import httpx
from typing import Any
from app.config import get_settings
from app.db.session import SessionLocal
from app.models import Region, RegionStatSnapshot
from app.models._enums import JobKind, RegionStatSource
from app.workers.handlers import register

log = structlog.get_logger(__name__)


@register(JobKind.REGION_STAT_SYNC)
def handle_region_stat_sync(payload: dict[str, Any]) -> None:
    region_id = payload["region_id"]
    source = RegionStatSource(payload["source"])

    with SessionLocal() as db:
        region = db.get(Region, region_id)
        if region is None:
            log.warning("region_stat_sync.region_missing", region_id=region_id)
            return
        try:
            stats = _fetch_stats(source, region)  # source별 분기
            for metric_key, period, value in stats:
                _upsert_snapshot(db, region_id, source, metric_key, period, value)
            db.commit()
            log.info("region_stat_sync.complete", region_id=region_id, source=source.value)
        except Exception as e:
            log.error("region_stat_sync.failed", region_id=region_id, error=str(e))
            raise
```

`app/workers/handlers/__init__.py:39-46` `import_handlers()` 내 import 추가:
```python
from app.workers.handlers import (  # noqa: F401
    evidence_cleanup,
    image_resize,
    notification,
    region_stat_sync,  # 신규
)
```

#### 3.2.2 정기 실행 (스케줄러)

현재 `app/workers/queue.py`는 이벤트 주도(NOTIFY) — 정기 실행 메커니즘 없음. 옵션:

| 옵션 | 장점 | 단점 |
|---|---|---|
| systemd timer (호스트) | 단순, 운영 가시성 | RPi 외 환경 종속 |
| APScheduler (앱 내 별도 프로세스) | 환경 독립 | 의존성 추가, 단일 leader 락 필요 |
| `cron` 컨테이너 (`docker-compose.local.yml`에 추가) | 환경 일관 | 새 서비스 추가 |

→ **OI-19로 등록**, 결정 후 별도 plan에서 구현.

일배치 enqueue 흐름 (스케줄러 확정 후):
```python
# 매일 02:00 KST 호출
for region in db.query(Region).all():
    for src in (RegionStatSource.MOLIT_LAND, RegionStatSource.REB_PRICE_INDEX, ...):
        enqueue(db, JobKind.REGION_STAT_SYNC,
                {"region_id": region.id, "source": src.value})
db.commit()
```

### 3.3 서비스 레이어

#### 3.3.1 신규 `app/services/region_stats.py`

`app/services/posts.py:1-60` 패턴(라우트→service→ORM 책임 분리) 복제:

```python
"""Region stat service — 공공 API 통계 캐시 조회·갱신.

CLAUDE.md "네이티브 확장 대비" 4원칙 준수:
- 라우트는 입력 검증 + service 호출만
- service는 User·Region 객체를 인자로 받음 (request 직접 접근 금지)
- 응답은 Pydantic Read 스키마와 일치
- 권한 판단은 service/guard에서, 템플릿은 표시만
"""
from sqlalchemy.orm import Session
from app.models import Region, RegionStatSnapshot
from app.models._enums import RegionStatSource


def get_latest_snapshots(
    db: Session, region: Region, source: RegionStatSource
) -> list[RegionStatSnapshot]:
    """캐시 조회만. 미스 시 enqueue는 라우트가 결정 (lazy)."""
    ...


def get_land_price_summary(db: Session, region: Region) -> dict | None:
    """시군 토지 실거래가 12개월 요약. 캐시 미스 시 None 반환 → 위젯 미노출."""
    ...
```

#### 3.3.2 외부 API 클라이언트 격리

`app/services/external/molit_realestate.py`, `vworld.py`, `r_one.py` — fetch·파싱 책임만. service는 이를 호출하여 도메인 객체 변환. CLAUDE.md "ORM 직접 쿼리 금지" 안티패턴 회피.

### 3.4 라우트 / UI

#### 3.4.1 라우트 변경

신규 라우트 **불필요**. 기존 `app/routers/hub.py:43-56` `hub_home`이 통계 위젯 데이터를 컨텍스트로 추가 전달:

```python
# app/routers/hub.py
@router.get("/hub/{slug}", response_class=HTMLResponse)
def hub_home(slug: str, request: Request, ...):
    region = _region_or_404(db, slug)
    overview = hub_service.hub_overview(db, region)
    stats = region_stats.get_hub_stat_widgets(db, region)  # 신규
    return templates.TemplateResponse(
        request, "pages/hub/home.html",
        {"region": region, "overview": overview, "stats": stats, ...}
    )
```

#### 3.4.2 템플릿

기존 `app/templates/pages/hub/home.html`에 새 partial `partials/region_stat_widget.html` 1개 include. 권한: 비회원도 노출(공공 데이터, 정착 의사결정 컨텍스트).

위젯 구성 (PRD 안티패턴 회피):
- 토지 평균 거래가 (12개월) — **밴드형 표기** ("3,000만~5,000만/평") — 정확액 노출 회피, Pillar C 후회비용 정량화 정책과 일관
- 매매가격지수 추이 (간단한 sparkline)
- "출처: 국토교통부 실거래가 (공공누리 1유형) / R-ONE / V월드" 의무 footer

### 3.5 분석 이벤트

`app/services/analytics.py:20-48` `EventName` enum에 추가:

```python
# P2 — region context
REGION_STAT_VIEWED = "region_stat_viewed"
```

PII 미포함 — props는 `{"region_id": int, "source": str}` 만. 검색 키워드·예산 입력값은 미기록.

### 3.6 PRD 매핑 / OI 등록

#### 3.6.1 PRD 추가 위치

PRD §6.5 Hub 섹션 또는 §1.5.3 (Pillar R) 직후에 다음 내용 추가 (인라인 `[v1.2]` 라벨):

> **[v1.2] §6.5 Hub 통계 위젯 (지역 사실 데이터 컨텍스트)**: 시군 허브에 공공 API 4종(국토부 실거래가·R-ONE·V월드) 기반 통계 위젯 노출. 매물·시세 정확액은 노출하지 않음(Pillar C 정책 일관). 갱신 주기 일배치, 인증키 환경변수 분리. **본 위젯은 Pillar R 결과 페이지 컨텍스트 보강이지 매물 거래·중개 진입점이 아님** (부록 A.4 안티패턴 Top 2 일관).

#### 3.6.2 신규 OI 후보 (PRD §15에 추가)

| 번호 | 결정 필요 | 결정 시점 |
|---|---|---|
| **OI-17 [v1.2]** | **외부 매물(네이버 부동산·경매) 노출 도입 여부**. PRD §1.3·부록 A.1·A.4의 "거래 중개 회피" 정책과 충돌. 마케팅 톤·UX 메타포 영향 큼. 도입 시 Tier 2 전략(딥링크 리다이렉트만)로 한정. | Phase 3 말 |
| **OI-18 [v1.2]** | **외부 사이트 검색 URL 패턴 안정성**. 네이버 부동산 URL 파라미터(rletTypeCd·tradeTypeCd·cortarNo)는 비공식 — 변경 모니터링 책임. OI-17 ✓ 시에만 결정. | OI-17 종속 |
| **OI-19 [v1.2]** | **정기 동기화 스케줄러**: systemd timer vs APScheduler vs docker cron. RPi·VPS 운영 환경 일관성. | Phase 2 초 |
| **OI-20 [v1.2]** | **공공 API 인증키 관리**: 4종 API 키 환경변수 + 호출 한도 모니터링·알림. 401·429 응답 시 워커 backoff 전략. | Phase 2 초 |

---

## §4 다음 단계

채택 시:

1. ✅ 본 spec을 `docs/superpowers/specs/2026-05-09-listings-feasibility.md` 에 저장 (완료)
2. PRD `2026-04-17-nestory-design.md`에 다음 추가:
   - §15에 OI-17~20 추가 (인라인 `[v1.2]` 라벨)
   - §6.5 또는 §1.5.3 직후에 통계 위젯 절 추가 (3.6.1 인용문)
3. Phase 1 dev → main 머지 완료 후, plan 작성: `docs/superpowers/plans/2026-05-09-region-stat-context-mvp.md`
   - Task 단위 분할: enum + 모델 + 마이그레이션 → 외부 API 클라이언트 → 워커 핸들러 → 서비스 → 라우트 컨텍스트 + 템플릿 partial → 분석 이벤트 → 통합 테스트
   - 각 task 독립 실행 가능, subagent-driven-development 적용
4. **OI-17 결정 전엔 Tier 2(매물 딥링크) 진입 금지** — 본 spec이 보류 결정의 1차 근거

---

## §5 검증 결과 (이 spec 작성 시 완료)

| Verification | 결과 | 출처 |
|---|---|---|
| 잡코리아 vs 사람인 사건번호 | ✅ 서울고법 2016나2019365, 대법원 심리불속행 기각, 4.5억 손배 | [법률신문 98844](https://www.lawtimes.co.kr/news/98844) |
| 야놀자 vs 여기어때 형사 | ✅ 대법원 2022.5.12. 2021도1533 무죄 확정 | [casenote.kr 2021도1533](https://casenote.kr/대법원/2021도1533) |
| 야놀자 vs 여기어때 민사 | ✅ 서울고법 부정경쟁 §2(1)카목 성과도용, 10억 원 손배 (2021.8.) | [한경 2021-08-23](https://www.hankyung.com/it/article/202108230529Y) |
| 국토부 실거래가 OpenAPI 4종 | ✅ data.go.kr 15126463·65·66·69 모두 활성, 공공누리 | [data.go.kr 15126469](https://www.data.go.kr/data/15126469/openapi.do) 외 |
| R-ONE OpenAPI | ✅ data.go.kr 15134761 활성, 인증키 발급 후 사용 | [data.go.kr 15134761](https://www.data.go.kr/data/15134761/openapi.do) |
| V월드 검색 API 2.0 | ✅ 회원가입 + API 키, 공공누리 명시 | [vworld.kr/dev](https://www.vworld.kr/dev/v4dv_search2_s001.do) |
| 법원경매 OpenAPI | ⚠️ 부동산경매 매물 단위 정부 OpenAPI **확인되지 않음** | (검색 결과에 미발견) |
| 네이버 부동산 URL 파라미터 | ⚠️ 비공식 추출(rletTypeCd·tradeTypeCd·cortarNo) — 변경 가능성 | OI-18 추적 |
| 네이버 X-Frame-Options | ⚠️ 직접 검증 차단(WebFetch 차단) — 도입 시 수동 검증 필요 | OI-18 추적 |
| 코드 패턴 정합 (`region_stat_sync` 핸들러 시그니처) | ✅ `image_resize.py:36-74`와 동일 (`@register` + `SessionLocal`) | 본 §3.2.1 |
| PRD 회피 정책 인용 정확성 | ✅ §1.3:65-69, 부록 A.1:1270-71, 부록 A.4:1292 | `2026-04-17-nestory-design.md` |
| OI 신규 번호 | ✅ 현재 PRD OI-16까지, OI-17~20으로 등록 가능 | `2026-04-17-nestory-design.md:1241-1260` |

---

## §6 Out of Scope

본 spec에서 다루지 않음:

- 코드 구현 — 채택 시 별도 plan
- 네이버 부동산 비공식 API 분석 — 약관·법적 위험으로 의도적 배제
- 민간 경매 사업자(옥션원·지지옥션) B2B 제휴 협상 — 사업 의사결정으로 OI-17에 위임
- AVM(자동가치평가) 기능 — PRD 부록 A.2 "Zillow/Redfin 회피: AVM은 한국 전원주택에 부적합" 명시
- 회원 직접 등록형 매물(Tier 2 대안 외 변형) — 콜드 스타트·모더레이션 부담으로 권장 외
