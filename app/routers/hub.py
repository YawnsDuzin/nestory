"""Hub routes — /discover (region grid), /hub/{slug} (4-tab region hub)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_db
from app.models import Region, User
from app.models._enums import PostType
from app.services import hub as hub_service
from app.templating import templates

router = APIRouter(tags=["hub"])


@router.get("/discover", response_class=HTMLResponse)
def discover(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    regions = list(
        db.scalars(
            select(Region).order_by(Region.is_pilot.desc(), Region.sido, Region.sigungu)
        ).all()
    )
    return templates.TemplateResponse(
        request,
        "pages/discover.html",
        {"regions": regions, "current_user": current_user},
    )


def _region_or_404(db: Session, slug: str) -> Region:
    region = hub_service.get_region_by_slug(db, slug)
    if region is None:
        raise HTTPException(404, "지역을 찾을 수 없습니다")
    return region


@router.get("/hub/{slug}", response_class=HTMLResponse)
def hub_home(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    region = _region_or_404(db, slug)
    overview = hub_service.hub_overview(db, region)
    return templates.TemplateResponse(
        request,
        "pages/hub/home.html",
        {"region": region, "overview": overview, "current_user": current_user},
    )


@router.get("/hub/{slug}/reviews", response_class=HTMLResponse)
def hub_reviews(
    slug: str,
    request: Request,
    page: int = 1,
    sort: str = "latest",
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    region = _region_or_404(db, slug)
    posts, total = hub_service.hub_tab_posts(
        db, region, PostType.REVIEW, sort=sort, page=page
    )
    return templates.TemplateResponse(
        request,
        "pages/hub/reviews.html",
        {
            "region": region,
            "posts": posts,
            "total": total,
            "page": page,
            "sort": sort,
            "current_user": current_user,
        },
    )


@router.get("/hub/{slug}/journeys", response_class=HTMLResponse)
def hub_journeys(
    slug: str,
    request: Request,
    page: int = 1,
    sort: str = "latest",
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    region = _region_or_404(db, slug)
    posts, total = hub_service.hub_tab_posts(
        db, region, PostType.JOURNEY_EPISODE, sort=sort, page=page
    )
    return templates.TemplateResponse(
        request,
        "pages/hub/journeys.html",
        {
            "region": region,
            "posts": posts,
            "total": total,
            "page": page,
            "sort": sort,
            "current_user": current_user,
        },
    )


@router.get("/hub/{slug}/questions", response_class=HTMLResponse)
def hub_questions(
    slug: str,
    request: Request,
    page: int = 1,
    sort: str = "latest",
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    region = _region_or_404(db, slug)
    posts, total = hub_service.hub_tab_posts(
        db, region, PostType.QUESTION, sort=sort, page=page
    )
    return templates.TemplateResponse(
        request,
        "pages/hub/questions.html",
        {
            "region": region,
            "posts": posts,
            "total": total,
            "page": page,
            "sort": sort,
            "current_user": current_user,
        },
    )


@router.get("/hub/{slug}/neighbors", response_class=HTMLResponse)
def hub_neighbors(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
) -> HTMLResponse:
    region = _region_or_404(db, slug)
    neighbors = hub_service.region_neighbors(db, region)
    return templates.TemplateResponse(
        request,
        "pages/hub/neighbors.html",
        {"region": region, "neighbors": neighbors, "current_user": current_user},
    )
