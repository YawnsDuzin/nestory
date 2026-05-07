"""Content routes — write/* and detail pages for non-Journey types."""
from typing import Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.deps import get_db, require_badge, require_user
from app.models import Region, User
from app.models.user import BadgeLevel
from app.schemas.post_metadata import PlanMetadata, QuestionMetadata, ReviewMetadata
from app.services import posts as posts_service
from app.templating import templates

router = APIRouter(tags=["content"])


def _all_regions_options(db: Session) -> list[Region]:
    """All regions, sorted by sigungu. Used by all write/* forms."""
    return db.query(Region).order_by(Region.sigungu).all()


@router.get("/write/review", response_class=HTMLResponse)
def write_review_form(
    request: Request,
    user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/write/review.html",
        {
            "user": user,
            "page_title": "후기 작성",
            "page_subtitle": "정착 회고를 남겨주세요. Pillar C — 후회 비용을 데이터로.",
            "form_action": "/write/review",
            "regions": _all_regions_options(db),
            "form": None,
        },
    )


@router.post("/write/review")
def submit_review(
    user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    db: Session = Depends(get_db),
    title: str = Form(...),
    body: str = Form(...),
    region_id: int = Form(...),
    house_type: Literal["단독", "타운하우스", "듀플렉스"] = Form(...),
    size_pyeong: int = Form(...),
    satisfaction_overall: int = Form(...),
) -> RedirectResponse:
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid region")
    try:
        meta = ReviewMetadata(
            house_type=house_type, size_pyeong=size_pyeong,
            satisfaction_overall=satisfaction_overall,
        )
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e

    post = posts_service.create_review(db, user, region, meta, title, body)
    db.commit()
    return RedirectResponse(f"/post/{post.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/write/question", response_class=HTMLResponse)
def write_question_form(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/write/question.html",
        {
            "user": user,
            "page_title": "질문 작성",
            "page_subtitle": "지역에 사는 분들께 직접 물어보세요.",
            "form_action": "/write/question",
            "regions": _all_regions_options(db),
            "form": None,
        },
    )


@router.post("/write/question")
def submit_question(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    title: str = Form(...),
    body: str = Form(...),
    region_id: int = Form(...),
    tags: str = Form(""),
) -> RedirectResponse:
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid region")
    tag_list = [t.strip() for t in tags.split(",") if t.strip()][:10]
    try:
        meta = QuestionMetadata(tags=tag_list)
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    post = posts_service.create_question(db, user, region, meta, title, body)
    db.commit()
    return RedirectResponse(f"/question/{post.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/write/plan", response_class=HTMLResponse)
def write_plan_form(
    request: Request,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/write/plan.html",
        {
            "user": user,
            "page_title": "정착 계획 작성",
            "page_subtitle": "예비 입주자를 위한 콘텐츠. 다른 분들의 조언을 받아보세요.",
            "form_action": "/write/plan",
            "regions": _all_regions_options(db),
            "form": None,
        },
    )


@router.post("/write/plan")
def submit_plan(
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    title: str = Form(...),
    body: str = Form(...),
    region_id: int = Form(...),
    target_move_year: int = Form(...),
    budget_total_manwon_band: Literal[
        "<5000", "5000-10000", "10000-20000", "20000-40000", "40000+"
    ] = Form(...),
    construction_intent: Literal[
        "self_build", "buy_existing", "rent_first", "undecided"
    ] = Form(...),
) -> RedirectResponse:
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid region")
    try:
        meta = PlanMetadata(
            target_move_year=target_move_year,
            budget_total_manwon_band=budget_total_manwon_band,
            construction_intent=construction_intent,
        )
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    post = posts_service.create_plan(db, user, region, meta, title, body)
    db.commit()
    return RedirectResponse(f"/post/{post.id}", status_code=status.HTTP_303_SEE_OTHER)
