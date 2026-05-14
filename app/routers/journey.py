"""Journey routes — create journey + write episode + detail pages."""
from datetime import date as date_type
from typing import Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db, require_badge
from app.models import Journey, Region, User
from app.models.user import BadgeLevel
from app.schemas.post_metadata import JourneyEpisodeMetadata, JourneyEpMeta
from app.services import comments as comments_service
from app.services import images as images_service
from app.services import interactions as interactions_service
from app.services import posts as posts_service
from app.services import regions as regions_service
from app.templating import templates

router = APIRouter(tags=["journey"])


@router.get("/write/journey", response_class=HTMLResponse)
def write_journey_form(
    request: Request,
    user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/write/journey_create.html",
        {
            "user": user, "current_user": user,
            "page_title": "Journey 시작",
            "page_subtitle": "정착 과정을 시리즈로 기록합니다. 첫 에피소드는 생성 후 작성.",
            "form_action": "/write/journey",
            "submit_label": "Journey 시작",
            "body_required": False,
            "body_placeholder": "시리즈 소개 (선택, 마크다운 지원)",
            "regions": regions_service.list_all_for_dropdown(db),
            "form": None,
        },
    )


@router.post("/write/journey")
def submit_journey(
    user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    db: Session = Depends(get_db),
    title: str = Form(...),
    body: str = Form(""),
    region_id: int = Form(...),
    start_date: str = Form(""),
    cover_image_id: str = Form(""),
) -> RedirectResponse:
    description = body  # composer body == journey description
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid region")
    parsed_start: date_type | None = None
    if start_date:
        try:
            parsed_start = date_type.fromisoformat(start_date)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid start_date") from e
    parsed_cover: int | None = None
    if cover_image_id:
        try:
            parsed_cover = int(cover_image_id)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid cover_image_id") from e
    images_service.validate_cover_image(db, parsed_cover, user)
    images_service.validate_image_ownership(db, description, user)
    j = posts_service.create_journey(
        db, user, region, title, description or None, parsed_start,
        cover_image_id=parsed_cover,
    )
    db.commit()
    return RedirectResponse(f"/journey/{j.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/write/journey/{journey_id}/ep", response_class=HTMLResponse)
def write_episode_form(
    request: Request,
    journey_id: int,
    user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    journey = db.get(Journey, journey_id)
    if journey is None or journey.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if journey.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your journey")
    return templates.TemplateResponse(
        request, "pages/write/journey_episode.html",
        {
            "user": user, "current_user": user, "journey": journey,
            "page_title": f"새 에피소드 — {journey.title}",
            "page_subtitle": "이번 단계의 진행 상황을 기록하세요.",
            "form_action": f"/write/journey/{journey_id}/ep",
        },
    )


@router.post("/write/journey/{journey_id}/ep")
def submit_episode(
    journey_id: int,
    user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    db: Session = Depends(get_db),
    title: str = Form(...),
    body: str = Form(...),
    phase: Literal["터", "건축", "입주", "1년차", "3년차"] = Form(...),
    period_label: str = Form(...),
) -> RedirectResponse:
    journey = db.get(Journey, journey_id)
    if journey is None or journey.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    if journey.author_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your journey")
    posts_service.validate_body_length(body)
    images_service.validate_image_ownership(db, body, user)
    try:
        meta = JourneyEpisodeMetadata(
            journey_ep_meta=JourneyEpMeta(phase=phase, period_label=period_label)
        )
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    post = posts_service.create_journey_episode(db, user, journey, meta, title, body)
    db.commit()
    return RedirectResponse(
        f"/journey/{journey_id}/ep/{post.episode_no}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/journey/{journey_id}", response_class=HTMLResponse)
def journey_detail(
    request: Request,
    journey_id: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    journey = db.get(Journey, journey_id)
    if journey is None or journey.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    author = db.get(User, journey.author_id)
    region = db.get(Region, journey.region_id)
    episodes = posts_service.list_journey_episodes(db, journey_id)
    return templates.TemplateResponse(
        request, "pages/detail/journey.html",
        {
            "journey": journey,
            "author": author,
            "region": region,
            "episodes": episodes,
            "current_user": current_user,
        },
    )


@router.get("/journey/{journey_id}/ep/{ep_no}", response_class=HTMLResponse)
def journey_episode_detail(
    request: Request,
    journey_id: int,
    ep_no: int,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    journey = db.get(Journey, journey_id)
    if journey is None or journey.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    post = posts_service.get_journey_episode(db, journey_id, ep_no)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    posts_service.increment_view_count(db, post)
    db.commit()
    db.refresh(post)
    prev_ep = posts_service.prev_journey_episode(db, journey_id, ep_no)
    next_ep = posts_service.next_journey_episode(db, journey_id, ep_no)
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
        "pages/detail/journey_episode.html",
        {
            "journey": journey,
            "post": post,
            "prev_ep": prev_ep,
            "next_ep": next_ep,
            "current_user": current_user,
            "liked": liked,
            "like_count": interactions_service.like_count(db, post.id),
            "scrapped": scrapped,
            "scrap_count": interactions_service.scrap_count(db, post.id),
            "comments": comments,
            "comment_authors": comment_authors,
        },
    )
