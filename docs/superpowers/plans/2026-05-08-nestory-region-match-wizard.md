# Region Match Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** PRD §1.5.3 [v1.1·B3] Pillar R — 시니어 친화 5문항 wizard로 Top 3 시군 추천 + AI 자연어 설명. P1.4 surface(hub/discover) 위에 결과 페이지가 흘러들어가는 진입 매트릭.

**Architecture:** Deterministic 점수(`RegionScoringWeight` 시드 × user_weight dot product) + AI는 1-2문장 설명만 (claude-haiku-4-5, fallback 정적 텍스트). 비로그인은 URL params, 로그인은 `user_interest_regions` UPSERT. SSR + HTMX (P1.4 패턴 재사용).

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2.x `Mapped[T]` / Alembic / Jinja2 SSR / HTMX / Anthropic Python SDK (`anthropic` 패키지 — OAuth Bearer token 사용) / pytest + factory-boy.

**Spec reference:** `docs/superpowers/specs/2026-05-08-nestory-region-match-wizard-design.md`

**Migration head 기준:** `e1ad6f3c4a92` (P1.4 search indexes). 새 마이그레이션의 `down_revision` 으로 사용.

---

## File Structure

| Path | Role | Status |
|---|---|---|
| `app/models/region_scoring.py` | `RegionScoringWeight` ORM (composite PK = region_id, 5 score cols, notes, updated_at, updated_by_user_id) | Create |
| `app/models/__init__.py` | Re-export `RegionScoringWeight` (alphabetical) | Modify |
| `app/db/migrations/versions/<rev>_add_region_scoring_weights.py` | DDL + 4 pilot region × 5축 = 20 row seed (UPSERT) | Create |
| `app/services/match.py` | `compute_top_regions(answers)` deterministic + `generate_explanations(matches, answers)` LLM + `RegionMatch` dataclass + `USER_WEIGHTS` constant + `_static_explanation` fallback | Create |
| `app/services/analytics.py` | Add 3 events (`MATCH_WIZARD_STARTED`, `MATCH_WIZARD_SUBMITTED`, `MATCH_RESULT_VIEWED`) | Modify |
| `app/config.py` | Add `anthropic_oauth_token: str = ""` setting | Modify |
| `.env.example` | Add OAuth placeholder | Modify |
| `app/routers/match.py` | 4 routes (wizard start / question partial / submit / result) | Create |
| `app/main.py` | `include_router(match_router.router)` + alphabetical import | Modify |
| `app/templates/pages/match/wizard.html` | Start screen — 시작 버튼 + 문항 1 swap target | Create |
| `app/templates/pages/match/_question_partial.html` | 1문항 partial — 큰 라디오 버튼 + 단계 인디케이터 + Next 버튼 | Create |
| `app/templates/pages/match/result.html` | Top 3 카드 + AI 설명 + hub 링크 + (로그인) 팔로우 버튼 | Create |
| `app/templates/components/nav.html` | "🎯 시군 매칭" 링크 추가 (비로그인 visible) | Modify |
| `app/templates/pages/home.html` | 비로그인 hero 하단 CTA 박스 ("나에게 맞는 시군 찾기") 추가 | Modify |
| `app/tests/factories/region_scoring.py` | `RegionScoringWeightFactory` | Create |
| `app/tests/factories/__init__.py` | Re-export factory | Modify |
| `app/tests/integration/test_region_scoring_model.py` | Model + seed migration sanity | Create |
| `app/tests/integration/test_match_service_scoring.py` | `compute_top_regions` deterministic | Create |
| `app/tests/integration/test_match_service_llm.py` | `generate_explanations` mock + fallback | Create |
| `app/tests/integration/test_match_routes.py` | 4 라우트 200/302/400 + URL params round-trip | Create |
| `app/tests/integration/test_match_wizard_e2e.py` | 5문항 흐름 → result → user_interest_regions UPSERT | Create |
| `app/tests/unit/test_factories.py` | Sanity test for new factory | Modify |

---

## Task 1: `RegionScoringWeight` model + factory + unit test

**Files:**
- Create: `app/models/region_scoring.py`
- Modify: `app/models/__init__.py`
- Create: `app/tests/factories/region_scoring.py`
- Modify: `app/tests/factories/__init__.py`
- Modify: `app/tests/unit/test_factories.py`

- [ ] **Step 1: Write `RegionScoringWeight` model**

```python
# app/models/region_scoring.py
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RegionScoringWeight(Base):
    __tablename__ = "region_scoring_weights"

    region_id: Mapped[int] = mapped_column(
        ForeignKey("regions.id", ondelete="CASCADE"), primary_key=True
    )
    activity_score: Mapped[int] = mapped_column(Integer)
    medical_score: Mapped[int] = mapped_column(Integer)
    family_visit_score: Mapped[int] = mapped_column(Integer)
    farming_score: Mapped[int] = mapped_column(Integer)
    budget_score: Mapped[int] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
```

- [ ] **Step 2: Re-export from `app/models/__init__.py` (alphabetical)**

`from app.models.region_scoring import RegionScoringWeight` placed after `from app.models.region import Region`. Add `"RegionScoringWeight"` to `__all__` (alphabetical, after `"Region"`).

- [ ] **Step 3: Write factory**

```python
# app/tests/factories/region_scoring.py
"""RegionScoringWeight factory."""
import factory

from app.models import RegionScoringWeight
from app.tests.factories._base import BaseFactory
from app.tests.factories.region import RegionFactory


class RegionScoringWeightFactory(BaseFactory):
    class Meta:
        model = RegionScoringWeight
        exclude = ("region",)

    region = factory.SubFactory(RegionFactory)
    region_id = factory.SelfAttribute("region.id")

    activity_score = 5
    medical_score = 5
    family_visit_score = 5
    farming_score = 5
    budget_score = 5
    notes = None
```

- [ ] **Step 4: Re-export factory from `app/tests/factories/__init__.py`**

Add `from app.tests.factories.region_scoring import RegionScoringWeightFactory` (after `from app.tests.factories.region import ...`). Add `"RegionScoringWeightFactory"` to `__all__` (alphabetical).

- [ ] **Step 5: Write factory sanity test**

Open `app/tests/unit/test_factories.py` and append:

```python
def test_region_scoring_weight_factory_creates_row(db: Session) -> None:
    from app.tests.factories import RegionScoringWeightFactory

    w = RegionScoringWeightFactory()
    assert w.region_id is not None
    assert 0 <= w.activity_score <= 10
    assert 0 <= w.budget_score <= 10
```

(Imports may need `Session` from `sqlalchemy.orm`; copy the file's existing import style — do not duplicate imports.)

- [ ] **Step 6: Run unit tests (Docker-up PC only — skip if no Docker)**

Run: `uv run pytest app/tests/unit/test_factories.py::test_region_scoring_weight_factory_creates_row -v`
Expected: PASS. (If no Docker: skip, run after migration applied.)

- [ ] **Step 7: Lint**

Run: `uv run ruff check app/models/ app/tests/factories/`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add app/models/region_scoring.py app/models/__init__.py \
  app/tests/factories/region_scoring.py app/tests/factories/__init__.py \
  app/tests/unit/test_factories.py
git commit -m "feat(models): add RegionScoringWeight (Pillar R wizard)

Composite PK (region_id) + 5 score axes + notes + updated_at/by.
Phase 0 user.py 패턴 동일. Factory + sanity 테스트 포함.

Refs: docs/superpowers/specs/2026-05-08-nestory-region-match-wizard-design.md §4.1"
```

---

## Task 2: Migration — DDL + 20-row pilot seed

**Files:**
- Create: `app/db/migrations/versions/<rev>_add_region_scoring_weights.py` (rev은 autogenerate가 결정)

- [ ] **Step 1: Generate migration**

Run: `uv run alembic revision --autogenerate -m "add region scoring weights"`
Expected: 새 파일이 `app/db/migrations/versions/` 에 생성. `down_revision = 'e1ad6f3c4a92'` 확인.

- [ ] **Step 2: Verify upgrade body**

생성된 파일을 열어 확인:
- `def upgrade()` 본문이 `pass` 가 아님 (`op.create_table('region_scoring_weights', ...)` 포함)
- `import sqlalchemy as sa` 존재
- composite PK (`region_id` only) — `PrimaryKeyConstraint('region_id')`
- ForeignKeyConstraint to regions(CASCADE) + users(SET NULL)

이상이면 다음 단계.

- [ ] **Step 3: Add 4×5=20 row seed at end of `upgrade()`**

`op.create_table(...)` 다음 줄 (함수 닫는 괄호 직전)에 삽입. **slug 기반 region 조회 + INSERT** — pilot region들의 id가 환경별로 다르므로 raw SQL UPSERT 패턴 사용. pilot region이 미존재하면 0 row가 들어가고 마이그레이션은 성공함 (의도된 동작 — seed_demo 또는 별도 region 시드 책임).

```python
    op.execute(
        """
        INSERT INTO region_scoring_weights
            (region_id, activity_score, medical_score, family_visit_score,
             farming_score, budget_score, notes, updated_at)
        SELECT r.id, v.activity, v.medical, v.family_visit,
               v.farming, v.budget, v.notes, now()
        FROM regions r
        JOIN (VALUES
            ('yangpyeong', 8, 7, 9, 7, 6,
             '양평군: 한강·산림 활동 풍부, 의료 양호, 자녀 1시간 거리, 텃밭 적합, 시세 중상.'),
            ('yeongwol',   7, 4, 4, 8, 9,
             '영월군: 자연·산림 활동 풍부, 의료 약함, 수도권 멀음, 농지 좋음, 시세 매우 저렴.'),
            ('hongcheon',  8, 6, 7, 8, 7,
             '홍천군: 자연 활동 강함, 의료 보통, 수도권 1.5시간, 농지 풍부, 시세 중간.'),
            ('gokseong',   6, 5, 4, 9, 9,
             '곡성군: 농사 환경 최상, 시세 저렴, 자녀 방문 약함, 의료 보통.')
        ) AS v(slug, activity, medical, family_visit, farming, budget, notes)
            ON r.slug = v.slug
        ON CONFLICT (region_id) DO UPDATE SET
            activity_score = EXCLUDED.activity_score,
            medical_score = EXCLUDED.medical_score,
            family_visit_score = EXCLUDED.family_visit_score,
            farming_score = EXCLUDED.farming_score,
            budget_score = EXCLUDED.budget_score,
            notes = EXCLUDED.notes,
            updated_at = now()
        """
    )
```

(slug은 seed_demo의 4 pilot region — `yangpyeong`, `yeongwol`, `hongcheon`, `gokseong` — 와 일치. 다른 slug 사용 시 LEFT JOIN 결과가 0 row → 시드 비어있음.)

- [ ] **Step 4: Add downgrade body**

```python
def downgrade() -> None:
    """Downgrade schema."""
    # autogenerate가 생성한 op.drop_table 등을 그대로 유지
    op.drop_table("region_scoring_weights")
```

(autogenerate가 이미 `drop_table` 작성했을 수 있음 — 그 경우 이미 OK.)

- [ ] **Step 5: Lint migration file**

Run: `uv run ruff check --fix app/db/migrations/versions/`
Expected: clean (UP007 자동 변환 적용).

- [ ] **Step 6: Apply migration (Docker-up PC only)**

Run: `uv run alembic upgrade head`
Expected: revision applied. 검증:
```powershell
docker exec nestory-postgres-local psql -U nestory -d nestory -c "SELECT count(*) FROM region_scoring_weights"
```
**주의**: 4 pilot region이 미리 시드되어 있어야 20 row 생성. seed_demo에서 4 pilot 생성 안 했으면 0 row일 수 있음 — 이 경우 다음 단계의 통합 테스트가 fail. seed_demo 1회 실행 또는 통합 테스트가 직접 region을 생성하도록 작성.

- [ ] **Step 7: Verify alembic history is linear**

Run: `uv run alembic history --verbose | head -10`
Expected: 새 revision이 `e1ad6f3c4a92` 다음. branch 없음.

- [ ] **Step 8: Commit**

```bash
git add app/db/migrations/versions/
git commit -m "feat(db): add region_scoring_weights table + 4 pilot seed

DDL + idempotent UPSERT seed (yangpyeong/gapyeong/chuncheon/hongseong × 5축).
seed는 regions 테이블 slug join — pilot region 미존재 시 0 row.

Refs: docs/superpowers/specs/2026-05-08-nestory-region-match-wizard-design.md §4.1, §6"
```

---

## Task 3: `match` service — deterministic scoring (skeleton + tests first)

**Files:**
- Create: `app/services/match.py`
- Create: `app/tests/integration/test_match_service_scoring.py`

- [ ] **Step 1: Write failing test for `compute_top_regions`**

```python
# app/tests/integration/test_match_service_scoring.py
"""Integration tests for `compute_top_regions` deterministic scoring.

Tests:
- test_compute_returns_top_3_in_score_order
- test_same_input_yields_same_output
- test_invalid_answer_code_raises
- test_returns_at_most_3_even_with_more_regions
- test_resolves_ties_by_region_id_for_determinism

NOTE: Requires running Postgres (factory-boy uses test session).
"""
from sqlalchemy.orm import Session

from app.services.match import compute_top_regions
from app.tests.factories import PilotRegionFactory, RegionScoringWeightFactory


def _seed_region(slug: str, sigungu: str, **scores) -> object:
    region = PilotRegionFactory(slug=slug, sigungu=sigungu)
    RegionScoringWeightFactory(region=region, **scores)
    return region


def test_compute_returns_top_3_in_score_order(db: Session) -> None:
    high = _seed_region(
        "high", "최고시",
        activity_score=10, medical_score=10, family_visit_score=10,
        farming_score=10, budget_score=10,
    )
    mid = _seed_region(
        "mid", "중간시",
        activity_score=5, medical_score=5, family_visit_score=5,
        farming_score=5, budget_score=5,
    )
    low = _seed_region(
        "low", "낮음시",
        activity_score=1, medical_score=1, family_visit_score=1,
        farming_score=1, budget_score=1,
    )
    answers = {1: "A", 2: "A", 3: "A", 4: "A", 5: "A"}
    matches = compute_top_regions(db, answers)
    assert [m.region.slug for m in matches] == ["high", "mid", "low"]
    assert matches[0].total_score > matches[1].total_score > matches[2].total_score


def test_same_input_yields_same_output(db: Session) -> None:
    _seed_region("a", "에이시", activity_score=5, medical_score=5,
                 family_visit_score=5, farming_score=5, budget_score=5)
    _seed_region("b", "비이시", activity_score=6, medical_score=6,
                 family_visit_score=6, farming_score=6, budget_score=6)
    answers = {1: "B", 2: "C", 3: "B", 4: "B", 5: "C"}
    r1 = compute_top_regions(db, answers)
    r2 = compute_top_regions(db, answers)
    assert [m.region.slug for m in r1] == [m.region.slug for m in r2]
    assert [m.total_score for m in r1] == [m.total_score for m in r2]


def test_invalid_answer_code_raises(db: Session) -> None:
    import pytest

    with pytest.raises(ValueError, match="invalid answer"):
        compute_top_regions(db, {1: "A", 2: "A", 3: "A", 4: "A", 5: "Z"})


def test_returns_at_most_3_even_with_more_regions(db: Session) -> None:
    for i in range(5):
        _seed_region(f"r{i}", f"리전{i}",
                     activity_score=i, medical_score=i, family_visit_score=i,
                     farming_score=i, budget_score=i)
    matches = compute_top_regions(db, {1: "A", 2: "A", 3: "A", 4: "A", 5: "A"})
    assert len(matches) == 3


def test_resolves_ties_by_region_id_for_determinism(db: Session) -> None:
    a = _seed_region("aa", "에이에이시", activity_score=5, medical_score=5,
                     family_visit_score=5, farming_score=5, budget_score=5)
    b = _seed_region("bb", "비비시", activity_score=5, medical_score=5,
                     family_visit_score=5, farming_score=5, budget_score=5)
    matches = compute_top_regions(db, {1: "A", 2: "A", 3: "A", 4: "A", 5: "A"})
    # 동점 — region_id 오름차순 (a 먼저 생성 → id 작음)
    assert matches[0].region.id < matches[1].region.id
    assert matches[0].region.id == a.id
    assert matches[1].region.id == b.id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest app/tests/integration/test_match_service_scoring.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.match'` or `ImportError: cannot import name 'compute_top_regions'`.

(Docker 미가용 시 import 검증만: `uv run python -c "from app.services.match import compute_top_regions"` — 동일하게 실패해야 함.)

- [ ] **Step 3: Write `app/services/match.py`**

```python
"""Region Match Wizard — deterministic Top 3 scoring + LLM-driven explanations.

PRD §1.5.3 [v1.1·B3] Pillar R 핵심 차별화. 점수는 deterministic dot product,
AI는 자연어 설명만 (fallback 정적 텍스트).
"""
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Region, RegionScoringWeight


# ---------------------------------------------------------------------------
# Domain types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegionMatch:
    region: Region
    weight: RegionScoringWeight
    total_score: int
    rank: int  # 1-based


# 5축 → user weight per option (A/B/C/D)
# 각 옵션이 얼마나 그 축에 강조를 두는지 (0~10 정수).
USER_WEIGHTS: dict[int, dict[str, dict[str, int]]] = {
    # Q1: 활동 — A 텃밭/B 산책/C 예술/D 휴식
    1: {
        "A": {"activity": 8, "medical": 3, "family_visit": 3, "farming": 7, "budget": 5},
        "B": {"activity": 9, "medical": 4, "family_visit": 4, "farming": 3, "budget": 5},
        "C": {"activity": 5, "medical": 6, "family_visit": 5, "farming": 1, "budget": 5},
        "D": {"activity": 3, "medical": 7, "family_visit": 4, "farming": 1, "budget": 5},
    },
    # Q2: 의료 — A 매우중요/B 중요/C 보통/D 낮음
    2: {
        "A": {"activity": 3, "medical": 10, "family_visit": 5, "farming": 3, "budget": 4},
        "B": {"activity": 4, "medical": 7,  "family_visit": 5, "farming": 4, "budget": 5},
        "C": {"activity": 5, "medical": 5,  "family_visit": 5, "farming": 5, "budget": 6},
        "D": {"activity": 6, "medical": 3,  "family_visit": 5, "farming": 6, "budget": 7},
    },
    # Q3: 자녀방문 — A 주1회+/B 월2-3/C 분기1/D 거의없음
    3: {
        "A": {"activity": 4, "medical": 5, "family_visit": 10, "farming": 4, "budget": 4},
        "B": {"activity": 5, "medical": 5, "family_visit": 8,  "farming": 5, "budget": 5},
        "C": {"activity": 6, "medical": 5, "family_visit": 5,  "farming": 6, "budget": 6},
        "D": {"activity": 7, "medical": 5, "family_visit": 3,  "farming": 7, "budget": 7},
    },
    # Q4: 농사 — A 본격/B 텃밭/C 마당/D 안함
    4: {
        "A": {"activity": 7, "medical": 4, "family_visit": 4, "farming": 10, "budget": 6},
        "B": {"activity": 6, "medical": 5, "family_visit": 5, "farming": 7,  "budget": 5},
        "C": {"activity": 5, "medical": 5, "family_visit": 5, "farming": 3,  "budget": 5},
        "D": {"activity": 5, "medical": 6, "family_visit": 5, "farming": 0,  "budget": 5},
    },
    # Q5: 예산 — A ~3억/B 3-5/C 5-8/D 8억+
    5: {
        "A": {"activity": 4, "medical": 4, "family_visit": 4, "farming": 5, "budget": 10},
        "B": {"activity": 5, "medical": 5, "family_visit": 5, "farming": 5, "budget": 7},
        "C": {"activity": 5, "medical": 5, "family_visit": 5, "farming": 5, "budget": 5},
        "D": {"activity": 6, "medical": 6, "family_visit": 6, "farming": 5, "budget": 3},
    },
}

VALID_OPTIONS = frozenset({"A", "B", "C", "D"})
QUESTION_NUMBERS = (1, 2, 3, 4, 5)


def _validate_answers(answers: dict[int, str]) -> None:
    for q in QUESTION_NUMBERS:
        if q not in answers:
            raise ValueError(f"missing answer for Q{q}")
    for q, opt in answers.items():
        if q not in QUESTION_NUMBERS:
            raise ValueError(f"invalid question {q}")
        if opt not in VALID_OPTIONS:
            raise ValueError(f"invalid answer '{opt}' for Q{q}")


def _user_weight_vector(answers: dict[int, str]) -> dict[str, int]:
    """5문항 답변 → 5축 합산 가중치 벡터."""
    vec = {"activity": 0, "medical": 0, "family_visit": 0, "farming": 0, "budget": 0}
    for q in QUESTION_NUMBERS:
        for axis, w in USER_WEIGHTS[q][answers[q]].items():
            vec[axis] += w
    return vec


def _score(weight: RegionScoringWeight, user_vec: dict[str, int]) -> int:
    return (
        weight.activity_score * user_vec["activity"]
        + weight.medical_score * user_vec["medical"]
        + weight.family_visit_score * user_vec["family_visit"]
        + weight.farming_score * user_vec["farming"]
        + weight.budget_score * user_vec["budget"]
    )


def compute_top_regions(db: Session, answers: dict[int, str]) -> list[RegionMatch]:
    """Top 3 매칭 region을 score 내림차순으로 반환. 동점은 region_id 오름차순.

    Raises:
        ValueError: 답변 누락 또는 옵션 코드 부정.
    """
    _validate_answers(answers)
    user_vec = _user_weight_vector(answers)
    weights = list(db.scalars(select(RegionScoringWeight)).all())
    region_ids = [w.region_id for w in weights]
    region_map = {
        r.id: r
        for r in db.scalars(select(Region).where(Region.id.in_(region_ids))).all()
    }
    scored = [(w, _score(w, user_vec), region_map[w.region_id]) for w in weights]
    scored.sort(key=lambda t: (-t[1], t[2].id))
    top = scored[:3]
    return [
        RegionMatch(region=region, weight=w, total_score=score, rank=idx + 1)
        for idx, (w, score, region) in enumerate(top)
    ]


__all__ = ["RegionMatch", "USER_WEIGHTS", "compute_top_regions"]
```

(N+1: 4 pilot region 규모면 무시 가능. relationship 정의 안 함 — 모델은 단순 유지.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest app/tests/integration/test_match_service_scoring.py -v`
Expected: 5 PASS.

(Docker 미가용 시 — Task 9 이후 Docker-up PC에서 묶어 검증.)

- [ ] **Step 5: Lint**

Run: `uv run ruff check app/services/match.py app/tests/integration/test_match_service_scoring.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add app/services/match.py app/tests/integration/test_match_service_scoring.py
git commit -m "feat(services): add match.compute_top_regions deterministic scoring

5축 dot product + 동점 region_id 오름차순. USER_WEIGHTS 5×4×5 상수.
LLM 설명은 별도 함수(다음 task).

Refs: docs/superpowers/specs/2026-05-08-nestory-region-match-wizard-design.md §3, §6"
```

---

## Task 4: Anthropic SDK dependency + OAuth config

**Files:**
- Modify: `pyproject.toml`
- Modify: `app/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Add `anthropic` to deps**

Edit `pyproject.toml` — `[project] dependencies` 배열에 `markdown>=3.6` 다음 줄 추가:

```toml
  "anthropic>=0.40",
```

(공식 Anthropic Python SDK. Spec의 "Claude Agent SDK"는 이 SDK를 의미 — 별도 `claude-agent-sdk` 패키지는 agent 루프용으로 본 use case 부적합. 단순 `messages.create` 1회 호출이라 표준 SDK 사용.)

**중요 — 인증 파라미터 사전 검증**: SDK 버전에 따라 OAuth Bearer 토큰 전달 방식이 다름. impl 시점에 다음 중 하나를 SDK 문서/Tool 검증 후 결정:
- `anthropic.Anthropic(auth_token="Bearer xxx")` — 일부 버전 지원
- `anthropic.Anthropic(api_key="sk-ant-...")` — 정적 API key
- `anthropic.Anthropic(default_headers={"Authorization": "Bearer xxx"})` — 헤더 직접 주입
빠른 SDK 문서 확인은 `claude-code-guide` 스킬 또는 `mcp__plugin_context7_context7__resolve-library-id` 사용. 결정한 방식으로 Task 5 Step 3의 `_get_sdk_client` 수정.

- [ ] **Step 2: Run sync**

Run: `uv sync`
Expected: `anthropic` 설치 + `uv.lock` 업데이트.

- [ ] **Step 3: Add OAuth setting**

Edit `app/config.py` — `Settings` 클래스 안 `image_max_dimension` 다음 줄에 추가:

```python
    anthropic_oauth_token: str = ""
```

- [ ] **Step 4: Add `.env.example` placeholder**

Read first: `app/.env.example` 또는 프로젝트 루트 `.env.example` 위치 확인 (`Glob`).

`Write` 또는 `Edit`로 가장 자연스러운 위치(섹션이 있다면 마지막에)에 다음 줄 추가:

```
# Anthropic OAuth (Region Match Wizard explanations) — empty 시 fallback 정적 텍스트
ANTHROPIC_OAUTH_TOKEN=
```

(파일이 없으면 새 `.env.example` 생성하지 말 것 — 이 경우 README의 환경 변수 섹션에만 메모 추가.)

- [ ] **Step 5: Lint**

Run: `uv run ruff check app/config.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock app/config.py .env.example
git commit -m "feat(deps): add anthropic SDK + OAuth token setting

Region Match Wizard AI explanation용. OAuth 토큰 빈 값이면 fallback 정적 텍스트.

Refs: docs/superpowers/specs/2026-05-08-nestory-region-match-wizard-design.md §7"
```

---

## Task 5: `generate_explanations` LLM call + fallback + tests

**Files:**
- Modify: `app/services/match.py`
- Create: `app/tests/integration/test_match_service_llm.py`

- [ ] **Step 1: Write failing test**

```python
# app/tests/integration/test_match_service_llm.py
"""Tests for match.generate_explanations — SDK mock + fallback.

Tests:
- test_returns_static_when_oauth_empty
- test_calls_sdk_per_match_and_returns_text
- test_falls_back_on_sdk_exception
- test_falls_back_on_timeout

NOTE: Requires running Postgres for factory rows.
"""
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from app.services.match import (
    RegionMatch,
    generate_explanations,
)
from app.tests.factories import PilotRegionFactory, RegionScoringWeightFactory


def _make_match(db: Session, slug: str = "yang", rank: int = 1) -> RegionMatch:
    region = PilotRegionFactory(slug=slug, sigungu="양평군")
    weight = RegionScoringWeightFactory(region=region)
    return RegionMatch(region=region, weight=weight, total_score=200, rank=rank)


_ANSWERS = {1: "A", 2: "A", 3: "B", 4: "B", 5: "C"}


def test_returns_static_when_oauth_empty(db: Session) -> None:
    m = _make_match(db, "yang", 1)
    with patch("app.services.match.get_settings") as gs:
        gs.return_value = MagicMock(anthropic_oauth_token="")
        result = generate_explanations([m], _ANSWERS)
    assert len(result) == 1
    assert "양평" in result[0]
    assert "1" in result[0] or "추천" in result[0]


def test_calls_sdk_per_match_and_returns_text(db: Session) -> None:
    m1 = _make_match(db, "yang1", 1)
    m2 = _make_match(db, "yang2", 2)
    fake_msg = MagicMock()
    fake_msg.content = [MagicMock(text="이곳이 잘 맞습니다.")]
    fake_client = MagicMock()
    fake_client.messages.create.return_value = fake_msg
    with patch("app.services.match.get_settings") as gs, patch(
        "app.services.match._get_sdk_client"
    ) as get_client:
        gs.return_value = MagicMock(anthropic_oauth_token="tok")
        get_client.return_value = fake_client
        result = generate_explanations([m1, m2], _ANSWERS)
    assert result == ["이곳이 잘 맞습니다.", "이곳이 잘 맞습니다."]
    assert fake_client.messages.create.call_count == 2


def test_falls_back_on_sdk_exception(db: Session) -> None:
    m = _make_match(db, "yang", 1)
    fake_client = MagicMock()
    fake_client.messages.create.side_effect = RuntimeError("API down")
    with patch("app.services.match.get_settings") as gs, patch(
        "app.services.match._get_sdk_client"
    ) as get_client:
        gs.return_value = MagicMock(anthropic_oauth_token="tok")
        get_client.return_value = fake_client
        result = generate_explanations([m], _ANSWERS)
    assert len(result) == 1
    assert "양평" in result[0]  # static fallback contains region name
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest app/tests/integration/test_match_service_llm.py -v`
Expected: FAIL with `ImportError: cannot import name 'generate_explanations'`.

- [ ] **Step 3: Append LLM functions to `app/services/match.py`**

Add at the bottom (before `__all__`):

```python
import logging
from functools import lru_cache

from app.config import get_settings

log = logging.getLogger(__name__)

_ANSWER_LABELS: dict[int, dict[str, str]] = {
    1: {"A": "텃밭·정원", "B": "등산·산책", "C": "예술·취미", "D": "조용한 휴식"},
    2: {"A": "매우 중요(만성질환)", "B": "중요", "C": "보통", "D": "낮음"},
    3: {"A": "주 1회 이상", "B": "월 2-3회", "C": "분기 1회", "D": "거의 없음"},
    4: {"A": "본격 농업", "B": "텃밭 정도", "C": "마당만", "D": "안 함"},
    5: {"A": "3억 이하", "B": "3-5억", "C": "5-8억", "D": "8억 이상"},
}

_SYSTEM_PROMPT = (
    "당신은 한국 전원생활 정착 추천 도우미입니다. "
    "시니어 사용자의 라이프스타일 답변과 시군 점수를 보고, "
    "왜 이 시군이 추천되었는지 1-2문장으로 친절하게 설명합니다. "
    "존댓말 사용. 시군 이름과 핵심 매칭 이유 2-3개를 자연스럽게 엮으세요. "
    "절대 점수 자체나 숫자를 본문에 노출하지 마세요."
)


@lru_cache(maxsize=1)
def _get_sdk_client():  # type: ignore[no-untyped-def]
    """Anthropic 클라이언트 — process 단위 캐시."""
    import anthropic

    settings = get_settings()
    return anthropic.Anthropic(auth_token=settings.anthropic_oauth_token)


def _user_prompt(match: "RegionMatch", answers: dict[int, str]) -> str:
    lines = [
        f"시군: {match.region.sigungu} ({match.region.sido})",
        "사용자 라이프스타일:",
        f"- 활동: {_ANSWER_LABELS[1][answers[1]]}",
        f"- 의료: {_ANSWER_LABELS[2][answers[2]]}",
        f"- 자녀 방문: {_ANSWER_LABELS[3][answers[3]]}",
        f"- 농사: {_ANSWER_LABELS[4][answers[4]]}",
        f"- 예산: {_ANSWER_LABELS[5][answers[5]]}",
        "",
        "매칭 점수 분포 (참고용, 본문에 직접 노출 금지):",
        f"- 활동 {match.weight.activity_score}/10, "
        f"의료 {match.weight.medical_score}/10, "
        f"자녀방문 {match.weight.family_visit_score}/10, "
        f"농사 {match.weight.farming_score}/10, "
        f"예산 {match.weight.budget_score}/10",
        "",
        "설명을 1-2문장으로:",
    ]
    return "\n".join(lines)


def _static_explanation(match: "RegionMatch") -> str:
    return (
        f"{match.region.sigungu}이(가) Top {match.rank}로 추천되었습니다. "
        f"5개 항목 매칭 점수 합계 {match.total_score}점."
    )


def generate_explanations(
    matches: list["RegionMatch"], answers: dict[int, str]
) -> list[str]:
    """각 match에 1-2문장 자연어 설명. OAuth 미설정/실패 시 fallback."""
    settings = get_settings()
    if not settings.anthropic_oauth_token:
        return [_static_explanation(m) for m in matches]

    client = _get_sdk_client()
    out: list[str] = []
    for m in matches:
        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=200,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": _user_prompt(m, answers)}],
                timeout=5.0,
            )
            out.append(resp.content[0].text.strip())
        except Exception as e:  # noqa: BLE001
            log.warning("match_llm.failed region_id=%s error=%s", m.region.id, e)
            out.append(_static_explanation(m))
    return out
```

Update `__all__` at bottom of `match.py`:

```python
__all__ = [
    "RegionMatch",
    "USER_WEIGHTS",
    "compute_top_regions",
    "generate_explanations",
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest app/tests/integration/test_match_service_llm.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Lint**

Run: `uv run ruff check app/services/match.py app/tests/integration/test_match_service_llm.py`
Expected: clean.

- [ ] **Step 6: Commit**

```bash
git add app/services/match.py app/tests/integration/test_match_service_llm.py
git commit -m "feat(services): add generate_explanations (LLM + fallback)

claude-haiku-4-5 1-2문장 설명. OAuth 토큰 빈 값/예외 시 정적 fallback.
시니어 존댓말 system prompt + 5문항 user prompt.

Refs: docs/superpowers/specs/2026-05-08-nestory-region-match-wizard-design.md §3, §7"
```

---

## Task 6: Analytics events for wizard

**Files:**
- Modify: `app/services/analytics.py`

- [ ] **Step 1: Add 3 events to `EventName` enum**

Edit `app/services/analytics.py` — `PROFILE_VIEWED` 다음 줄에 추가:

```python

    # P1.5 / P1.4b — Region Match Wizard
    MATCH_WIZARD_STARTED = "match_wizard_started"
    MATCH_WIZARD_SUBMITTED = "match_wizard_submitted"
    MATCH_RESULT_VIEWED = "match_result_viewed"
```

(emit은 여전히 no-op stub — P1.5에서 PostHog wiring.)

- [ ] **Step 2: Lint**

Run: `uv run ruff check app/services/analytics.py`
Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add app/services/analytics.py
git commit -m "feat(analytics): add 3 match wizard events

MATCH_WIZARD_STARTED · MATCH_WIZARD_SUBMITTED · MATCH_RESULT_VIEWED.
emit은 no-op stub 그대로 — PostHog wiring P1.5.

Refs: docs/superpowers/specs/2026-05-08-nestory-region-match-wizard-design.md"
```

---

## Task 7: Routes — wizard start + question partial

**Files:**
- Create: `app/routers/match.py`
- Create: `app/templates/pages/match/wizard.html`
- Create: `app/templates/pages/match/_question_partial.html`
- Modify: `app/main.py`

- [ ] **Step 1: Create empty package directory if needed**

Run: `Glob app/templates/pages/match/*` to confirm. If empty, no action — `Write` will create.

- [ ] **Step 2: Write router skeleton with start + question routes**

```python
# app/routers/match.py
"""Region Match Wizard — 5문항 → Top 3 + AI 설명. PRD §1.5.3."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import User
from app.services.analytics import EventName, emit
from app.templating import templates

router = APIRouter(tags=["match"])

# 5문항 정의 — services/match.py의 USER_WEIGHTS 5축과 일치해야 함.
QUESTIONS: list[dict] = [
    {
        "n": 1,
        "title": "은퇴 후 어떤 활동을 가장 즐기시고 싶으신가요?",
        "options": [
            ("A", "텃밭·정원 가꾸기"),
            ("B", "등산·자연 산책"),
            ("C", "예술·취미 활동"),
            ("D", "조용한 휴식"),
        ],
    },
    {
        "n": 2,
        "title": "의료 시설 접근성은 얼마나 중요하신가요?",
        "options": [
            ("A", "매우 중요 (만성질환 관리 등)"),
            ("B", "중요"),
            ("C", "보통"),
            ("D", "낮음"),
        ],
    },
    {
        "n": 3,
        "title": "자녀나 가족 방문은 얼마나 자주 예상하시나요?",
        "options": [
            ("A", "주 1회 이상"),
            ("B", "월 2-3회"),
            ("C", "분기 1회"),
            ("D", "거의 없음"),
        ],
    },
    {
        "n": 4,
        "title": "농사나 텃밭에 얼마나 시간을 들일 의향이세요?",
        "options": [
            ("A", "본격 농업"),
            ("B", "텃밭 정도"),
            ("C", "마당만 가꾸기"),
            ("D", "안 함"),
        ],
    },
    {
        "n": 5,
        "title": "부지+건축 예산은 어느 범위를 생각하시나요?",
        "options": [
            ("A", "3억 이하"),
            ("B", "3-5억"),
            ("C", "5-8억"),
            ("D", "8억 이상"),
        ],
    },
]
TOTAL_QUESTIONS = 5


def _question_or_404(n: int) -> dict:
    if n < 1 or n > TOTAL_QUESTIONS:
        raise HTTPException(404, "문항 번호가 올바르지 않습니다")
    return QUESTIONS[n - 1]


@router.get("/match/wizard", response_class=HTMLResponse)
def wizard_start(
    request: Request,
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    emit(EventName.MATCH_WIZARD_STARTED)
    return templates.TemplateResponse(
        request,
        "pages/match/wizard.html",
        {"current_user": current_user, "total": TOTAL_QUESTIONS},
    )


@router.get("/match/wizard/q/{n}", response_class=HTMLResponse)
def wizard_question(
    n: int,
    request: Request,
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    q = _question_or_404(n)
    return templates.TemplateResponse(
        request,
        "pages/match/_question_partial.html",
        {
            "q": q,
            "n": n,
            "total": TOTAL_QUESTIONS,
            "current_user": current_user,
        },
    )
```

- [ ] **Step 3: Register router in `app/main.py`**

Edit `app/main.py`:

1. Add import alphabetically (after `from app.routers import journey as journey_router`):

```python
from app.routers import match as match_router
```

2. Add `app.include_router(match_router.router)` (alphabetical — between `journey_router` and `me_router`).

- [ ] **Step 4: Write start screen template**

```html
<!-- app/templates/pages/match/wizard.html -->
{% extends "base.html" %}
{% block title %}나에게 맞는 시군 찾기 · Nestory{% endblock %}
{% block content %}
<section class="space-y-6">
  <header class="text-center space-y-3">
    <h1 class="text-3xl font-bold text-slate-900">🎯 나에게 맞는 시군 찾기</h1>
    <p class="text-lg text-slate-600">
      5개 질문에 답하시면 Top 3 시군을 추천해드립니다.
    </p>
  </header>

  <div class="rounded-lg border bg-white p-6 space-y-4">
    <p class="text-slate-700">
      라이프스타일·예산·의료·자녀 방문 등을 종합해 가장 잘 맞는 시군을 알려드립니다.
      답변은 저장되지 않으며, 결과 페이지의 URL을 저장/공유할 수 있습니다.
    </p>
    <ul class="text-sm text-slate-600 space-y-1 list-disc pl-5">
      <li>1-2분 소요</li>
      <li>비로그인도 사용 가능 (결과는 URL로 공유)</li>
      <li>로그인 사용자는 Top 3가 관심 시군으로 자동 저장</li>
    </ul>
    <div class="pt-4">
      <a href="/match/wizard/q/1"
         class="inline-block rounded-md bg-emerald-600 px-6 py-3 text-lg font-semibold text-white hover:bg-emerald-700">
        시작하기 →
      </a>
    </div>
  </div>
</section>
{% endblock %}
```

- [ ] **Step 5: Write question partial template**

```html
<!-- app/templates/pages/match/_question_partial.html -->
{% extends "base.html" %}
{% block title %}질문 {{ n }}/{{ total }} · Nestory{% endblock %}
{% block content %}
<section class="space-y-6">
  <div class="text-sm text-slate-500 text-center">
    <span class="font-semibold text-emerald-700">{{ n }}</span> / {{ total }}
  </div>
  <div class="h-2 w-full rounded-full bg-slate-200">
    <div class="h-2 rounded-full bg-emerald-600"
         style="width: {{ (n / total * 100) | round }}%"></div>
  </div>

  <h2 class="text-2xl font-bold text-slate-900 text-center">{{ q.title }}</h2>

  <form method="post"
        action="/match/wizard/submit"
        class="space-y-3"
        x-data="{ selected: null }">
    {# 이전 답변 유지 — URL 쿼리스트링 ?a1=A&a2=B... 가 있으면 hidden 으로 보존 #}
    {% for prev in range(1, n) %}
      {% set key = 'a' ~ prev %}
      {% if request.query_params.get(key) %}
        <input type="hidden" name="{{ key }}"
               value="{{ request.query_params.get(key) }}">
      {% endif %}
    {% endfor %}

    {% for code, label in q.options %}
      <label class="block rounded-lg border-2 bg-white p-4 cursor-pointer
                    min-h-12 hover:border-emerald-500 has-[:checked]:border-emerald-600
                    has-[:checked]:bg-emerald-50 transition">
        <input type="radio" name="a{{ n }}" value="{{ code }}"
               class="mr-3 h-5 w-5 align-middle accent-emerald-600"
               x-on:change="selected = '{{ code }}'"
               required>
        <span class="text-lg align-middle">{{ label }}</span>
      </label>
    {% endfor %}

    <div class="flex justify-between gap-3 pt-4">
      {% if n > 1 %}
        <a href="/match/wizard/q/{{ n - 1 }}{% if request.query_params %}?{{ request.query_params }}{% endif %}"
           class="rounded-md bg-slate-200 px-5 py-3 text-lg text-slate-800 hover:bg-slate-300">
          ← 이전
        </a>
      {% else %}
        <span></span>
      {% endif %}

      {% if n < total %}
        {# 중간 문항: 다음 문항 GET. 답변은 query string에 누적. #}
        <button type="button"
                x-bind:disabled="!selected"
                x-on:click="
                  if (!selected) return;
                  const params = new URLSearchParams(window.location.search);
                  params.set('a{{ n }}', selected);
                  window.location.href = '/match/wizard/q/{{ n + 1 }}?' + params.toString();
                "
                class="rounded-md bg-emerald-600 px-5 py-3 text-lg font-semibold text-white
                       hover:bg-emerald-700 disabled:bg-slate-300 disabled:cursor-not-allowed">
          다음 →
        </button>
      {% else %}
        <button type="submit"
                x-bind:disabled="!selected"
                class="rounded-md bg-emerald-600 px-5 py-3 text-lg font-semibold text-white
                       hover:bg-emerald-700 disabled:bg-slate-300 disabled:cursor-not-allowed">
          결과 보기 →
        </button>
      {% endif %}
    </div>
  </form>
</section>
{% endblock %}
```

(Alpine.js로 라디오 선택 상태 관리. 마지막 문항만 form POST submit, 그 외는 GET redirect로 query string 누적. 이전 답변은 hidden input + ULRSearchParams 양쪽에서 보존.)

- [ ] **Step 6: Smoke test**

Docker-up PC에서:
```bash
uv run uvicorn app.main:app --reload &
curl -s http://localhost:8000/match/wizard | grep "시군 찾기"
curl -s http://localhost:8000/match/wizard/q/1 | grep "텃밭"
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/match/wizard/q/99
# Expected: 404
```

(Docker 미가용 시 — Task 12 묶음에서.)

- [ ] **Step 7: Lint**

Run: `uv run ruff check app/routers/match.py app/main.py`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add app/routers/match.py app/main.py app/templates/pages/match/
git commit -m "feat(routers): add match wizard start + question routes

GET /match/wizard 시작 + GET /match/wizard/q/{n} 5문항 partial.
Alpine.js로 라디오 선택 상태, query string 답변 누적.

Refs: docs/superpowers/specs/2026-05-08-nestory-region-match-wizard-design.md §5"
```

---

## Task 8: POST /match/wizard/submit + GET /match/result

**Files:**
- Modify: `app/routers/match.py`
- Create: `app/templates/pages/match/result.html`

- [ ] **Step 1: Add submit + result handlers to `app/routers/match.py`**

Append to `app/routers/match.py` (after `wizard_question` function):

```python
from fastapi import Form
from fastapi.responses import RedirectResponse
from urllib.parse import urlencode

from sqlalchemy import delete

from app.models import UserInterestRegion
from app.services.match import (
    VALID_OPTIONS,
    compute_top_regions,
    generate_explanations,
)


def _parse_answers_from_query(qs: dict[str, str]) -> dict[int, str] | None:
    """Return parsed {1..5: 'A'..'D'} or None if any missing/invalid."""
    out: dict[int, str] = {}
    for n in range(1, TOTAL_QUESTIONS + 1):
        v = qs.get(f"a{n}")
        if v not in VALID_OPTIONS:
            return None
        out[n] = v
    return out


@router.post("/match/wizard/submit", response_class=HTMLResponse)
def wizard_submit(
    request: Request,
    a1: str = Form(...),
    a2: str = Form(...),
    a3: str = Form(...),
    a4: str = Form(...),
    a5: str = Form(...),
) -> RedirectResponse:
    answers = {1: a1, 2: a2, 3: a3, 4: a4, 5: a5}
    for q, opt in answers.items():
        if opt not in VALID_OPTIONS:
            raise HTTPException(400, f"답변 형식이 올바르지 않습니다 (Q{q})")
    emit(EventName.MATCH_WIZARD_SUBMITTED)
    qs = urlencode({f"a{n}": answers[n] for n in range(1, TOTAL_QUESTIONS + 1)})
    return RedirectResponse(url=f"/match/result?{qs}", status_code=303)


@router.get("/match/result", response_class=HTMLResponse)
def wizard_result(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    answers = _parse_answers_from_query(dict(request.query_params))
    if answers is None:
        return RedirectResponse(url="/match/wizard", status_code=303)

    matches = compute_top_regions(db, answers)
    if len(matches) < 3:
        raise HTTPException(
            500, "추천에 필요한 시군 데이터가 부족합니다. 운영자에게 문의해주세요."
        )

    explanations = generate_explanations(matches, answers)
    cards = [
        {"match": m, "explanation": exp}
        for m, exp in zip(matches, explanations, strict=True)
    ]

    if current_user is not None:
        # 기존 wizard 결과 row 3개를 덮어쓰기 (priority 1~3 — 사용자가 수동으로 추가한
        # 다른 region은 priority>=4 가정. wizard는 1~3을 점유.)
        db.execute(
            delete(UserInterestRegion).where(
                UserInterestRegion.user_id == current_user.id,
                UserInterestRegion.priority.in_([1, 2, 3]),
            )
        )
        for m in matches:
            db.add(
                UserInterestRegion(
                    user_id=current_user.id,
                    region_id=m.region.id,
                    priority=m.rank,
                )
            )
        db.commit()

    emit(EventName.MATCH_RESULT_VIEWED)
    return templates.TemplateResponse(
        request,
        "pages/match/result.html",
        {
            "cards": cards,
            "answers": answers,
            "current_user": current_user,
        },
    )
```

(Imports를 정리: `from fastapi import APIRouter, Depends, Form, HTTPException, Request`, `from fastapi.responses import HTMLResponse, RedirectResponse`, `from urllib.parse import urlencode`. 기존 import 라인 위에 합치기 — 두 import 블록을 분산하지 말 것.)

- [ ] **Step 2: Write result template**

```html
<!-- app/templates/pages/match/result.html -->
{% extends "base.html" %}
{% block title %}추천 시군 Top 3 · Nestory{% endblock %}
{% block content %}
<section class="space-y-6">
  <header class="text-center space-y-2">
    <h1 class="text-3xl font-bold text-slate-900">🎯 추천 시군 Top 3</h1>
    <p class="text-slate-600">
      라이프스타일에 가장 잘 맞는 시군을 모았습니다.
    </p>
    {% if not current_user %}
      <p class="text-sm">
        결과를 저장하시려면
        <a href="/auth/login?next={{ request.url.path }}?{{ request.url.query }}"
           class="text-emerald-700 hover:underline font-semibold">로그인</a>
        하세요.
      </p>
    {% endif %}
  </header>

  <div class="space-y-4">
    {% for card in cards %}
      {% set m = card.match %}
      <article class="rounded-lg border bg-white p-6 space-y-3">
        <div class="flex items-start justify-between gap-3">
          <div class="space-y-1">
            <p class="text-sm text-slate-500">Top {{ m.rank }}</p>
            <h2 class="text-2xl font-bold text-slate-900">
              {{ m.region.sigungu }}
            </h2>
            <p class="text-sm text-slate-600">{{ m.region.sido }}</p>
          </div>
          {% if m.region.cover_image %}
            <img src="{{ m.region.cover_image }}"
                 alt="{{ m.region.sigungu }} 이미지"
                 class="h-20 w-20 rounded object-cover">
          {% endif %}
        </div>
        <p class="text-base text-slate-800 leading-relaxed">
          {{ card.explanation }}
        </p>
        <div class="flex flex-wrap gap-2 pt-2">
          <a href="/hub/{{ m.region.slug }}"
             class="rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-700">
            🏘️ {{ m.region.sigungu }} 허브 보기 →
          </a>
          <a href="/search?q={{ m.region.sigungu }}"
             class="rounded-md border bg-white px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
            관련 후기 검색
          </a>
        </div>
      </article>
    {% endfor %}
  </div>

  <div class="text-center pt-6 border-t border-slate-200">
    <a href="/match/wizard"
       class="text-emerald-700 hover:underline">
      ↻ 다른 답변으로 다시 시도
    </a>
  </div>
</section>
{% endblock %}
```

- [ ] **Step 3: Lint**

Run: `uv run ruff check app/routers/match.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add app/routers/match.py app/templates/pages/match/result.html
git commit -m "feat(routers): add match submit + result + UPSERT user_interest_regions

POST submit → 303 redirect to /match/result?a1=...
GET result → 점수 재계산 + LLM 설명 + Top 3 카드.
로그인 사용자는 priority 1-3 row 덮어쓰기.

Refs: docs/superpowers/specs/2026-05-08-nestory-region-match-wizard-design.md §5, §8"
```

---

## Task 9: Route integration tests

**Files:**
- Create: `app/tests/integration/test_match_routes.py`

- [ ] **Step 1: Write tests**

```python
# app/tests/integration/test_match_routes.py
"""Integration tests for /match/* routes.

Tests:
- test_wizard_start_returns_200
- test_wizard_question_n_returns_partial
- test_wizard_question_invalid_n_returns_404
- test_submit_redirects_to_result_with_query_string
- test_submit_invalid_answer_returns_400
- test_result_with_full_answers_returns_200
- test_result_missing_answers_redirects_to_wizard
- test_result_logged_in_upserts_user_interest_regions
- test_result_logged_in_overwrites_previous_priority_1_3
"""
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UserInterestRegion
from app.tests.factories import (
    PilotRegionFactory,
    RegionScoringWeightFactory,
    UserFactory,
)


def _seed_4_regions(db: Session) -> None:
    """4 pilot region with weights — required for result page (>=3)."""
    for slug, sigungu, scores in [
        ("yang", "양평군", (8, 7, 9, 7, 6)),
        ("gap",  "가평군", (8, 5, 8, 8, 7)),
        ("chu",  "춘천시", (7, 8, 6, 6, 7)),
        ("hong", "홍성군", (6, 6, 5, 9, 9)),
    ]:
        region = PilotRegionFactory(slug=slug, sigungu=sigungu)
        a, m, fv, fa, b = scores
        RegionScoringWeightFactory(
            region=region,
            activity_score=a, medical_score=m, family_visit_score=fv,
            farming_score=fa, budget_score=b,
        )


def test_wizard_start_returns_200(client: TestClient) -> None:
    r = client.get("/match/wizard")
    assert r.status_code == 200
    assert "시군 찾기" in r.text


def test_wizard_question_n_returns_partial(client: TestClient) -> None:
    r = client.get("/match/wizard/q/1")
    assert r.status_code == 200
    assert "텃밭" in r.text  # Q1 옵션 A


def test_wizard_question_invalid_n_returns_404(client: TestClient) -> None:
    assert client.get("/match/wizard/q/0").status_code == 404
    assert client.get("/match/wizard/q/6").status_code == 404


def test_submit_redirects_to_result_with_query_string(client: TestClient) -> None:
    r = client.post(
        "/match/wizard/submit",
        data={"a1": "A", "a2": "A", "a3": "A", "a4": "A", "a5": "A"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"].startswith("/match/result?")
    for n in range(1, 6):
        assert f"a{n}=A" in r.headers["location"]


def test_submit_invalid_answer_returns_400(client: TestClient) -> None:
    r = client.post(
        "/match/wizard/submit",
        data={"a1": "Z", "a2": "A", "a3": "A", "a4": "A", "a5": "A"},
    )
    assert r.status_code == 400


def _patch_oauth_empty():
    """patch ctx — `match.get_settings()`가 OAuth 빈값 객체 반환. fallback 강제."""
    return patch(
        "app.services.match.get_settings",
        return_value=MagicMock(anthropic_oauth_token=""),
    )


def test_result_with_full_answers_returns_200(
    client: TestClient, db: Session
) -> None:
    _seed_4_regions(db)
    with _patch_oauth_empty():
        r = client.get("/match/result?a1=A&a2=A&a3=A&a4=A&a5=A")
    assert r.status_code == 200
    assert any(s in r.text for s in ("양평", "가평", "춘천", "홍성"))


def test_result_missing_answers_redirects_to_wizard(client: TestClient) -> None:
    r = client.get("/match/result?a1=A&a2=A", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/match/wizard"


def test_result_logged_in_upserts_user_interest_regions(
    client: TestClient, db: Session, login
) -> None:
    _seed_4_regions(db)
    user = UserFactory()
    login(user.id)
    with _patch_oauth_empty():
        r = client.get("/match/result?a1=A&a2=A&a3=A&a4=A&a5=A")
    assert r.status_code == 200
    rows = list(
        db.scalars(
            select(UserInterestRegion).where(UserInterestRegion.user_id == user.id)
        ).all()
    )
    assert len(rows) == 3
    assert {r.priority for r in rows} == {1, 2, 3}


def test_result_logged_in_overwrites_previous_priority_1_3(
    client: TestClient, db: Session, login
) -> None:
    _seed_4_regions(db)
    user = UserFactory()
    other = PilotRegionFactory(slug="other", sigungu="아더시")
    db.add(UserInterestRegion(user_id=user.id, region_id=other.id, priority=1))
    db.commit()
    login(user.id)
    with _patch_oauth_empty():
        r = client.get("/match/result?a1=A&a2=A&a3=A&a4=A&a5=A")
    assert r.status_code == 200
    rows = list(
        db.scalars(
            select(UserInterestRegion).where(UserInterestRegion.user_id == user.id)
        ).all()
    )
    assert len(rows) == 3
    assert other.id not in {r.region_id for r in rows}
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest app/tests/integration/test_match_routes.py -v`
Expected: 9 PASS.

- [ ] **Step 3: Lint**

Run: `uv run ruff check app/tests/integration/test_match_routes.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add app/tests/integration/test_match_routes.py
git commit -m "test: add /match route integration tests (9 cases)

start·question·submit·result + URL params round-trip + UPSERT 검증.
LLM은 OAuth 빈값 fallback 으로 우회 — 결정적.

Refs: docs/superpowers/specs/2026-05-08-nestory-region-match-wizard-design.md §11"
```

---

## Task 10: Wire wizard from home + nav

**Files:**
- Modify: `app/templates/components/nav.html`
- Modify: `app/templates/pages/home.html`

- [ ] **Step 1: Add nav link**

Edit `app/templates/components/nav.html` — `<a href="/discover" class="hover:text-slate-900">탐색</a>` 다음 줄에 추가:

```html
      <a href="/match/wizard" class="hover:text-slate-900">🎯 시군 매칭</a>
```

- [ ] **Step 2: Add CTA section to home page (비로그인 hero 하단)**

Edit `app/templates/pages/home.html` — 비로그인 분기 안의 `{# 4a. 지금 활발한 시군 (dynamic) #}` 직전에 새 섹션 추가:

```html
  {# 3.5. Region Match Wizard CTA #}
  <section class="py-12 border-t border-slate-200">
    <div class="rounded-lg bg-emerald-50 p-8 text-center space-y-4">
      <p class="text-3xl">🎯</p>
      <h2 class="text-2xl font-bold text-slate-900">
        나에게 맞는 시군 찾기
      </h2>
      <p class="text-slate-600 max-w-lg mx-auto">
        라이프스타일·예산·의료·자녀 방문 등을 종합해 5개 질문으로 Top 3 시군을 알려드립니다.
        비로그인도 사용 가능합니다.
      </p>
      <a href="/match/wizard"
         class="inline-block rounded-md bg-emerald-600 px-6 py-3 font-semibold text-white hover:bg-emerald-700">
        시작하기 →
      </a>
    </div>
  </section>
```

- [ ] **Step 3: Add CTA card to logged-in home dashboard**

Edit `app/templates/pages/home.html` — 로그인 분기 안 `{# Dynamic: recommended region hubs #}` 섹션 직전에 추가:

```html
    {# Region Match Wizard 진입 — 신규 사용자가 관심 시군 발견 안 했을 때 #}
    <section class="space-y-3 border-t border-slate-200 pt-6">
      <h2 class="text-lg font-semibold">🎯 나에게 맞는 시군 찾기</h2>
      <a href="/match/wizard"
         class="block rounded border bg-emerald-50 p-4 hover:bg-emerald-100">
        <p class="font-semibold text-slate-900">5개 질문으로 Top 3 추천</p>
        <p class="text-sm text-slate-700 mt-1">
          라이프스타일을 분석해 가장 잘 맞는 시군을 알려드립니다.
        </p>
      </a>
    </section>
```

- [ ] **Step 4: Manual smoke (Docker-up PC)**

서버 실행 후 브라우저에서:
- `/` → CTA 박스 보임 (로그아웃 상태)
- 로그인 후 `/` → "🎯 나에게 맞는 시군 찾기" 카드 보임
- nav의 "🎯 시군 매칭" 클릭 → `/match/wizard` 진입

- [ ] **Step 5: Commit**

```bash
git add app/templates/components/nav.html app/templates/pages/home.html
git commit -m "feat(ui): add wizard entry from home + nav

비로그인 hero 하단 CTA + 로그인 dashboard 카드 + nav 링크.

Refs: docs/superpowers/specs/2026-05-08-nestory-region-match-wizard-design.md §8"
```

---

## Task 11: E2E test — full flow

**Files:**
- Create: `app/tests/integration/test_match_wizard_e2e.py`

- [ ] **Step 1: Write E2E test**

```python
# app/tests/integration/test_match_wizard_e2e.py
"""E2E flow: 5문항 → submit → result. UPSERT 검증.

비로그인 + 로그인 두 시나리오. LLM은 OAuth 빈값 fallback 사용.
"""
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import UserInterestRegion
from app.tests.factories import (
    PilotRegionFactory,
    RegionScoringWeightFactory,
    UserFactory,
)


def _seed_4(db: Session) -> None:
    for slug, sigungu, scores in [
        ("yang2", "양평군", (8, 7, 9, 7, 6)),
        ("gap2",  "가평군", (8, 5, 8, 8, 7)),
        ("chu2",  "춘천시", (7, 8, 6, 6, 7)),
        ("hong2", "홍성군", (6, 6, 5, 9, 9)),
    ]:
        r = PilotRegionFactory(slug=slug, sigungu=sigungu)
        a, m, fv, fa, b = scores
        RegionScoringWeightFactory(
            region=r, activity_score=a, medical_score=m,
            family_visit_score=fv, farming_score=fa, budget_score=b,
        )


def test_full_anonymous_flow(client: TestClient, db: Session) -> None:
    _seed_4(db)
    # 1. start
    assert client.get("/match/wizard").status_code == 200
    # 2. q1~5 화면 — partial 모두 200
    for n in range(1, 6):
        assert client.get(f"/match/wizard/q/{n}").status_code == 200
    # 3. submit
    r = client.post(
        "/match/wizard/submit",
        data={"a1": "A", "a2": "A", "a3": "A", "a4": "A", "a5": "A"},
        follow_redirects=True,
    )
    # 4. result — Top 3 region sigungu 모두 표시
    assert r.status_code == 200
    visible = sum(1 for s in ("양평군", "가평군", "춘천시", "홍성군") if s in r.text)
    assert visible >= 3


def test_full_logged_in_flow_persists_top_3(
    client: TestClient, db: Session, login
) -> None:
    _seed_4(db)
    user = UserFactory()
    login(user.id)
    r = client.post(
        "/match/wizard/submit",
        data={"a1": "B", "a2": "B", "a3": "B", "a4": "B", "a5": "B"},
        follow_redirects=True,
    )
    assert r.status_code == 200
    rows = list(
        db.scalars(
            select(UserInterestRegion)
            .where(UserInterestRegion.user_id == user.id)
            .order_by(UserInterestRegion.priority)
        ).all()
    )
    assert [row.priority for row in rows] == [1, 2, 3]
```

- [ ] **Step 2: Run test**

Run: `uv run pytest app/tests/integration/test_match_wizard_e2e.py -v`
Expected: 2 PASS.

- [ ] **Step 3: Lint**

Run: `uv run ruff check app/tests/integration/test_match_wizard_e2e.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add app/tests/integration/test_match_wizard_e2e.py
git commit -m "test: add match wizard E2E flow (anonymous + logged-in)

5문항 GET + submit POST + result GET → UPSERT priority 1/2/3 검증.

Refs: docs/superpowers/specs/2026-05-08-nestory-region-match-wizard-design.md §11"
```

---

## Task 12: Full regression sweep + DoD verification (Docker-up PC)

**Files:** none (verification only)

- [ ] **Step 1: Full pytest run**

Run: `uv run pytest app/tests/ -q`
Expected: 모든 테스트 PASS (P1.4 baseline + 새 테스트 ~14개 추가). 회귀 발견 시 commit-by-commit bisect.

- [ ] **Step 2: Lint full tree**

Run: `uv run ruff check app/`
Expected: clean.

- [ ] **Step 3: Alembic head check**

Run: `uv run alembic current && uv run alembic history --verbose | head -15`
Expected: head = 새 wizard 마이그레이션 revision. linear chain 유지.

- [ ] **Step 4: Manual browser QA (golden path)**

서버 실행 후 다음 흐름을 한 번 통과:

1. 비로그인 `/` → 🎯 CTA 박스 → 클릭 → `/match/wizard` 진입
2. "시작하기" → Q1 화면 (1/5 인디케이터, 큰 라디오 버튼 4개)
3. 답변 선택 → "다음" 활성화 → Q2~Q5 진행 (이전 답변 query string 유지)
4. Q5 답변 → "결과 보기" → POST submit → `/match/result?a1=...&a5=...` 도달
5. Top 3 카드 + 설명 + 허브 링크 + "다시 시도" 링크
6. 로그인 후 같은 흐름 → DB에서 `SELECT * FROM user_interest_regions WHERE user_id=...` → 3 row priority 1/2/3
7. wizard 재실행 → 같은 user의 row 3개가 새 결과로 덮어써짐 (이전 row 사라짐)

- [ ] **Step 5: LLM 실호출 1회 (선택 — OAuth 토큰 있는 경우)**

`.env`에 `ANTHROPIC_OAUTH_TOKEN` 설정 후 위 5번 결과 페이지 재로드 → 정적 fallback 대신 자연스러운 한국어 1-2문장 설명 표시 확인.

비용 추정: 결과 1회 = 3 LLM 호출 ≈ $0.003. 운영 시 일 100회 = $9/월 (PRD 비용 추정 §10).

- [ ] **Step 6: Plan DoD 표 갱신 + 핸드오프 메모리 갱신**

이 plan 파일 마지막에 DoD 체크 표 추가 (§13 마지막에). 메모리 `project_nestory_handoff.md`에 다음 추가:
- "P1.4b Region Match Wizard 완료" 줄
- 다음 단계: P1.5 plan 작성 진입

- [ ] **Step 7: Commit DoD 검증 결과 (필요 시)**

핸드오프 갱신만 commit:

```bash
git add docs/superpowers/plans/2026-05-08-nestory-region-match-wizard.md
git commit -m "docs(plans): mark wizard DoD verified

pytest 풀런 + 마이그레이션 적용 + 브라우저 QA 통과.

Refs: docs/superpowers/specs/2026-05-08-nestory-region-match-wizard-design.md §12"
```

---

## DoD checklist (2026-05-08 코드 구현 완료 — Docker 미가용 PC)

- [x] 4 라우트 모두 정상 동작 (200/303/400/404 분기) — 코드 구현 완료, app.routes 확인 ✅. 실 라우트 검증은 docker-up PC 필요
- [x] 5문항 wizard UX 시니어 친화 (1문항 1화면, 큰 글씨 `text-2xl`/`text-lg`, 진행 인디케이터, `min-h-12` 라디오 버튼)
- [x] 4 pilot region × 5축 시드 마이그레이션 작성, slug 기반 idempotent UPSERT (yangpyeong/yeongwol/hongcheon/gokseong) — alembic head `7f8c2d4a6e91`. 정적 chain 검증 ✅
- [x] `compute_top_regions` 결정적 (같은 입력 → 같은 출력 + 동점 region_id 정렬). 5+ 단위 테스트 작성 ✅
- [x] LLM 실패 시 fallback 정적 설명, 페이지 항상 200 — `_static_explanation` + `noqa: BLE001` 광폭 catch 작성 ✅
- [x] 로그인 사용자 wizard ON CONFLICT UPSERT — manual priority>=4 region 보존, wizard Top 3만 덮어쓰기 (Issue 1 fix `6de6c5f`)
- [x] pytest baseline 회귀 없음 (2026-05-10) — wizard 관련 신규 테스트(scoring 8 + LLM 3 + routes 10 + e2e 2) 모두 PASS. 풀 pytest 508 PASS / 4 hang 파일 deferred (worker queue / image_upload — wizard 무관)
- [ ] ⏸ 브라우저 manual QA (golden path) — Docker 미가용. 다음 docker-up PC에서 1회 통과 검증
- [ ] ⏸ 비용 1주일 운영 < $1 — OAuth 토큰 미설정. 운영 후 PostHog (P1.5) emit 활성화 시점에 실측

**구현 commits**: `4450d44..100c951` (13 commits, 다음 P1.4 22 commits와 함께 dev → main PR 시 squash 권장).

---

## Out-of-scope (별도 plan / P2+)

- LLM 응답 캐시 (P2 비용·hit-rate 측정 후 결정)
- 사용자 후기 기반 점수 보정 (PRD §1.5.3 — Phase 3)
- 자유 입력 자연어 위저드
- 2축 조합 가중치 보정 (예: 농사 + 예산)
- 위저드 결과 통계 dashboard (관리자 콘솔에서 P1.5+ 검토)
- 재실행 시 이전 답변 prefill UI (URL share 흐름으로 충분)
- Q5 budget 역수 매핑 정교화 (시드 5축 정수 0-10로 단순 유지)
