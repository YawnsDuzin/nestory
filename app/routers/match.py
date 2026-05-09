"""Region Match Wizard — 5문항 → Top 3 + AI 설명. PRD §1.5.3."""
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import User
from app.services.analytics import EventName, emit
from app.services.match import (
    VALID_OPTIONS,
    compute_top_regions,
    generate_explanations,
    save_wizard_top3,
)
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


@router.post("/match/wizard/submit", response_class=HTMLResponse)
def wizard_submit(
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


def _parse_answers_from_query(qs: dict[str, str]) -> dict[int, str] | None:
    """Return parsed {1..5: 'A'..'D'} or None if any missing/invalid."""
    out: dict[int, str] = {}
    for n in range(1, TOTAL_QUESTIONS + 1):
        v = qs.get(f"a{n}")
        if v not in VALID_OPTIONS:
            return None
        out[n] = v
    return out


@router.get("/match/result", response_class=HTMLResponse, response_model=None)
def wizard_result(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse | RedirectResponse:
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
        save_wizard_top3(db, current_user, matches)

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
