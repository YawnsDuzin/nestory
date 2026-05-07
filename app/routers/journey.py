"""Journey routes — create journey + write episode + detail pages."""
from datetime import date as date_type
from typing import Literal

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session, selectinload

from app.deps import get_db, require_badge
from app.models import Journey, Post, Region, User
from app.models._enums import PostStatus, PostType
from app.models.user import BadgeLevel
from app.schemas.post_metadata import JourneyEpisodeMetadata, JourneyEpMeta
from app.services import posts as posts_service
from app.templating import templates

router = APIRouter(tags=["journey"])


def _all_regions(db: Session) -> list[Region]:
    return db.query(Region).order_by(Region.sigungu).all()


@router.get("/write/journey", response_class=HTMLResponse)
def write_journey_form(
    request: Request,
    user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/write/journey_create.html",
        {"user": user, "regions": _all_regions(db)},
    )


@router.post("/write/journey")
def submit_journey(
    user: User = Depends(require_badge(BadgeLevel.RESIDENT)),
    db: Session = Depends(get_db),
    title: str = Form(...),
    description: str = Form(""),
    region_id: int = Form(...),
    start_date: str = Form(""),
) -> RedirectResponse:
    region = db.get(Region, region_id)
    if region is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid region")
    parsed_start: date_type | None = None
    if start_date:
        try:
            parsed_start = date_type.fromisoformat(start_date)
        except ValueError as e:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid start_date") from e
    j = posts_service.create_journey(db, user, region, title, description or None, parsed_start)
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
            "user": user, "journey": journey,
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
) -> HTMLResponse:
    journey = db.get(Journey, journey_id)
    if journey is None or journey.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    author = db.get(User, journey.author_id)
    region = db.get(Region, journey.region_id)
    episodes = (
        db.query(Post)
        .options(selectinload(Post.author))
        .filter(
            Post.journey_id == journey_id,
            Post.type == PostType.JOURNEY_EPISODE,
            Post.deleted_at.is_(None),
            Post.status == PostStatus.PUBLISHED,
        )
        .order_by(Post.episode_no.asc())
        .all()
    )
    return templates.TemplateResponse(
        request, "pages/detail/journey.html",
        {"journey": journey, "author": author, "region": region, "episodes": episodes},
    )


@router.get("/journey/{journey_id}/ep/{ep_no}", response_class=HTMLResponse)
def journey_episode_detail(
    request: Request,
    journey_id: int,
    ep_no: int,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    journey = db.get(Journey, journey_id)
    if journey is None or journey.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    post = (
        db.query(Post)
        .options(selectinload(Post.author), selectinload(Post.region))
        .filter(
            Post.journey_id == journey_id,
            Post.episode_no == ep_no,
            Post.type == PostType.JOURNEY_EPISODE,
            Post.deleted_at.is_(None),
            Post.status == PostStatus.PUBLISHED,
        )
        .first()
    )
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)
    posts_service.increment_view_count(db, post)
    db.commit()
    db.refresh(post)
    prev_ep = (
        db.query(Post)
        .filter(
            Post.journey_id == journey_id,
            Post.episode_no < ep_no,
            Post.type == PostType.JOURNEY_EPISODE,
            Post.deleted_at.is_(None),
        )
        .order_by(Post.episode_no.desc())
        .first()
    )
    next_ep = (
        db.query(Post)
        .filter(
            Post.journey_id == journey_id,
            Post.episode_no > ep_no,
            Post.type == PostType.JOURNEY_EPISODE,
            Post.deleted_at.is_(None),
        )
        .order_by(Post.episode_no.asc())
        .first()
    )
    return templates.TemplateResponse(
        request, "pages/detail/journey_episode.html",
        {"journey": journey, "post": post, "prev_ep": prev_ep, "next_ep": next_ep},
    )
