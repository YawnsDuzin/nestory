"""Content routes — write/* and detail pages for non-Journey types."""
from typing import Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_current_user, get_db, require_badge, require_user
from app.models import Post, Region, User
from app.models._enums import PostStatus, PostType
from app.models.user import BadgeLevel
from app.schemas.post_metadata import PlanMetadata, QuestionMetadata, ReviewMetadata
from app.services import comments as comments_service
from app.services import images as images_service
from app.services import interactions as interactions_service
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
            "current_user": user,
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
    posts_service.validate_body_length(body)
    images_service.validate_image_ownership(db, body, user)
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
            "current_user": user,
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
    posts_service.validate_body_length(body)
    images_service.validate_image_ownership(db, body, user)
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
            "current_user": user,
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
    posts_service.validate_body_length(body)
    images_service.validate_image_ownership(db, body, user)
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


@router.post("/question/{question_id}/answer")
def submit_answer(
    question_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
    body: str = Form(...),
) -> RedirectResponse:
    question = db.get(Post, question_id)
    if (
        question is None
        or question.type != PostType.QUESTION
        or question.deleted_at is not None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    posts_service.validate_body_length(body)
    images_service.validate_image_ownership(db, body, user)
    posts_service.create_answer(db, user, question, body)
    db.commit()
    return RedirectResponse(
        f"/question/{question_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/post/{post_id}", response_class=HTMLResponse)
def post_detail(
    request: Request,
    post_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    post = (
        db.query(Post)
        .options(selectinload(Post.author), selectinload(Post.region))
        .filter(Post.id == post_id)
        .first()
    )
    if (
        post is None
        or post.deleted_at is not None
        or post.status != PostStatus.PUBLISHED
        or post.type in (PostType.JOURNEY_EPISODE, PostType.ANSWER)
        # JOURNEY_EPISODE uses /journey/.../ep/.., ANSWER renders inside /question/{id}
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    posts_service.increment_view_count(db, post)
    db.commit()
    db.refresh(post)
    liked = (
        interactions_service.is_liked_by(db, post.id, current_user.id)
        if current_user
        else False
    )
    scrapped = (
        interactions_service.is_scrapped_by(db, post.id, current_user.id)
        if current_user
        else False
    )
    comments = comments_service.list_comments(db, post)
    author_ids = {c.author_id for c in comments}
    comment_authors = (
        {u.id: u for u in db.scalars(select(User).where(User.id.in_(author_ids))).all()}
        if author_ids
        else {}
    )
    return templates.TemplateResponse(
        request,
        "pages/detail/post.html",
        {
            "post": post,
            "author": post.author,
            "region": post.region,
            "current_user": current_user,
            "liked": liked,
            "like_count": interactions_service.like_count(db, post.id),
            "scrapped": scrapped,
            "scrap_count": interactions_service.scrap_count(db, post.id),
            "comments": comments,
            "comment_authors": comment_authors,
        },
    )


@router.get("/question/{question_id}", response_class=HTMLResponse)
def question_detail(
    request: Request,
    question_id: int,
    user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    question = (
        db.query(Post)
        .options(selectinload(Post.author), selectinload(Post.region))
        .filter(Post.id == question_id)
        .first()
    )
    if (
        question is None
        or question.deleted_at is not None
        or question.type != PostType.QUESTION
        or question.status != PostStatus.PUBLISHED
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    posts_service.increment_view_count(db, question)
    db.commit()
    db.refresh(question)
    answers = (
        db.query(Post)
        .options(selectinload(Post.author))
        .filter(
            Post.parent_post_id == question.id,
            Post.type == PostType.ANSWER,
            Post.deleted_at.is_(None),
        )
        .order_by(Post.published_at.asc())
        .all()
    )
    liked = (
        interactions_service.is_liked_by(db, question.id, user.id) if user else False
    )
    scrapped = (
        interactions_service.is_scrapped_by(db, question.id, user.id) if user else False
    )
    comments = comments_service.list_comments(db, question)
    author_ids = {c.author_id for c in comments}
    comment_authors = (
        {u.id: u for u in db.scalars(select(User).where(User.id.in_(author_ids))).all()}
        if author_ids
        else {}
    )
    return templates.TemplateResponse(
        request,
        "pages/detail/question.html",
        {
            "question": question,
            "author": question.author,
            "region": question.region,
            "answers": answers,
            "user": user,
            "current_user": user,
            "liked": liked,
            "like_count": interactions_service.like_count(db, question.id),
            "scrapped": scrapped,
            "scrap_count": interactions_service.scrap_count(db, question.id),
            "comments": comments,
            "comment_authors": comment_authors,
        },
    )
