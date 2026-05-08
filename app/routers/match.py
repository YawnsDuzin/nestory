"""Region Match Wizard — 5문항 → Top 3 + AI 설명. PRD §1.5.3."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.deps import get_current_user
from app.models import User
from app.services.analytics import EventName, emit
from app.templating import templates

router = APIRouter(tags=["match"])

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
