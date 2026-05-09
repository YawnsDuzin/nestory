"""Region Match Wizard — deterministic Top 3 scoring + LLM-driven explanations.

PRD §1.5.3 [v1.1·B3] Pillar R 핵심 차별화. 점수는 deterministic dot product,
AI는 자연어 설명만 (fallback 정적 텍스트).
"""
import logging
from dataclasses import dataclass
from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as _pg_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Region, RegionScoringWeight, User, UserInterestRegion

log = logging.getLogger(__name__)


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
    weights = list(db.scalars(select(RegionScoringWeight)).all())
    if not weights:
        return []
    user_vec = _user_weight_vector(answers)
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
    """Anthropic 클라이언트 — process 단위 캐시. OAuth 토큰은 default_headers Bearer로 주입."""
    import anthropic

    settings = get_settings()
    return anthropic.Anthropic(
        default_headers={"Authorization": f"Bearer {settings.anthropic_oauth_token}"}
    )


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


def save_wizard_top3(
    db: Session, user: User, matches: list[RegionMatch]
) -> None:
    """Wizard 결과 Top 3를 user_interest_regions에 ON CONFLICT UPSERT.

    composite PK (user_id, region_id) 충돌 시 priority만 갱신 — 사용자가 수동으로
    추가한 priority>=4 region은 그대로 보존됨. wizard 재실행 시 동일 region은
    priority 갱신만, 다른 region은 그대로.
    """
    for m in matches:
        stmt = _pg_insert(UserInterestRegion).values(
            user_id=user.id,
            region_id=m.region.id,
            priority=m.rank,
        ).on_conflict_do_update(
            index_elements=["user_id", "region_id"],
            set_={"priority": m.rank},
        )
        db.execute(stmt)
    db.commit()


__all__ = [
    "RegionMatch",
    "USER_WEIGHTS",
    "compute_top_regions",
    "generate_explanations",
    "save_wizard_top3",
]
